"""四层上下文压缩管线（预算驱动）。

设计原则：
- 每轮评估，逐层按预算触发，条件不满足零动作
- 无损降级：任何替换前先落盘，占位符带路径，信息可回溯
- 所有阈值相对模型上下文窗口（CONTEXT_WINDOW）计算
- 摘要分段进行，单次 API 输入恒有界，不可能溢出

四层：
  L1 落盘（persist）    单条工具结果超上限 → 落盘 + 头尾预览 (任何一条大结果都不能进上下文，防御性的)
  L2 裁剪（snip）       消息数超50条 → 保留前3+后47，user边界切割
  L3 微压缩（micro）    总 token > 50% 窗口 → 旧工具结果落盘后换占位符 (压缩阈值远小于L1，用于清理历史久远的工具调用结果，已有<persisted-output>前缀的不会重复替换)
  L4 摘要（summarize）  总 token > 75% 窗口 → 分段摘要，保留 system
  应急（reactive）        API 报 context_length_exceeded → 同上 + 最小尾部
"""
import hashlib
import json
from src.logs.app_log import get_log
from pathlib import Path
from src.utils.session_id_container import get_session_id_container
from src.config import CONTEXT_WINDOW, MODEL, get_client
from src.utils.exceptions import CompactException

logger = get_log()

# ---- 预算阈值（相对 CONTEXT_WINDOW）----
TOOL_RESULT_CAP = max(12000, int(CONTEXT_WINDOW * 0.05))   # L1：单条结果落盘线（token）
SNIP_MAX_MESSAGES = 50                                    # L2：消息数上限
MICRO_TRIGGER = int(CONTEXT_WINDOW * 0.50)                # L3：总 token 触发线
SUMMARY_TRIGGER = int(CONTEXT_WINDOW * 0.75)              # L4：总 token 触发线
KEEP_RECENT_TOKENS = int(CONTEXT_WINDOW * 0.08)           # L3：保留的近期原始消息预算
SUMMARY_CHUNK_CHARS = 60_000                              # 摘要分块大小（字符）
PREVIEW_CHARS = 1000                                      # 落盘预览头/尾字符数
NOTIFICATION_CAP = 20_000                                 # 后台通知落盘线（字符，agent_runner 使用）

TOOL_RESULTS_DIR = Path.home() / ".sebastian" / ".task_outputs" / "tool-results"
TRANSCRIPTS_DIR = Path.home() / ".sebastian" / ".transcripts"

PERSISTED_PREFIX = "<persisted-output>"

# 摘要消息识别（摘要本身也是 role="user"，边界处理时必须排除）
SUMMARY_PREFIXES = (
    f"{PERSISTED_PREFIX}\n[Compacted]",
    f"{PERSISTED_PREFIX}\n[Reactive compacted]",
)


def _is_summary_message(msg: dict) -> bool:
    content = msg.get("content", "")
    return isinstance(content, str) and content.startswith(SUMMARY_PREFIXES)


def _is_plain_user(msg: dict) -> bool:
    """普通用户消息（排除摘要消息）"""
    return msg.get("role") == "user" and not _is_summary_message(msg)


# ---- Token 估算（启发式，无外部依赖）----

def estimate_tokens(text: str) -> int:
    """CJK 字符 ≈1 token，其余 ≈0.25 token/字符"""
    if not text:
        return 0
    cjk = 0
    for ch in text:
        o = ord(ch)
        if (0x4E00 <= o <= 0x9FFF) or (0x3000 <= o <= 0x30FF) or (0xFF00 <= o <= 0xFFEF):
            cjk += 1
    other = len(text) - cjk
    return max(1, int(cjk + other / 4))


def estimate_messages(messages: list) -> int:
    return sum(estimate_tokens(json.dumps(m, ensure_ascii=False, default=str)) for m in messages)


# ---- 落盘工具 ----

REPEAT_PERSIST_WARN = 2      # 同内容落盘次数达到此值 → 重复落盘告警
REPEAT_PERSIST_BREAK = 3     # 同内容落盘次数达到此值 → 熔断警告

def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


class PersistedRegistry:
    """已落盘文件清单（最近 N 条环形淘汰）。

    注入 system 提示词而非消息流，压缩/摘要永远不会吃掉它，
    模型随时知道磁盘上已有什么，避免反复读取大文件。
    """

    def __init__(self, max_entries: int = 20):
        self.max_entries = max_entries
        self._entries: dict[str, dict] = {}
        self._order: list[str] = []

    def add(self, path: str, size_tokens: int, source: str) -> int:
        """登记一次落盘，返回该路径累计落盘次数"""
        if path in self._entries:
            self._entries[path]["size"] = size_tokens
            self._entries[path]["source"] = source
            self._entries[path]["hits"] += 1
            self._order.remove(path)
            self._order.append(path)
        else:
            self._entries[path] = {"size": size_tokens, "hits": 1, "source": source}
            self._order.append(path)
            while len(self._order) > self.max_entries:
                old = self._order.pop(0)
                del self._entries[old]
        return self._entries[path]["hits"]

    def describe(self) -> str:
        if not self._order:
            return ""
        lines = [
            "<已落盘文件清单>",
            "完整内容已持久化到磁盘，请勿重复读取整个文件；如需特定片段请用 read 的 offset/limit 分页；路径相同意味着内容相同。",
        ]
        for p in reversed(self._order):
            e = self._entries[p]
            lines.append(f"- {p} (约 {e['size']} tokens, 已落盘 {e['hits']} 次)")
        lines.append("</已落盘文件清单>")
        return "\n".join(lines)


PERSISTED_REGISTRY = PersistedRegistry()


def persist_content(content: str, source: str = "tool") -> tuple[str, str, int]:
    """内容寻址落盘（sha256 前缀），同内容重复落盘命中同一文件。
    返回 (路径, 摘要, 该路径累计落盘次数 hits)"""
    if not TOOL_RESULTS_DIR.is_dir():
        TOOL_RESULTS_DIR.mkdir(exist_ok=True, parents=True)
    digest = _content_digest(content)
    file_path = TOOL_RESULTS_DIR / f"{digest}.txt"
    try:
        if not file_path.exists():
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"内容已落盘至 {file_path}")
    except PermissionError as e:
        logger.error(f"错误：没有权限写入：{file_path}")
        raise CompactException(f"错误：没有权限写入：{file_path}") from e
    except OSError as e:
        logger.error(f"错误：无法写入文件 {file_path}：{e}")
        raise CompactException(f"错误：无法写入文件 {file_path}：{e}") from e
    except Exception as e:
        logger.error(f"未知错误：保存 {file_path} 失败：{e}")
        raise CompactException(f"未知错误：保存 {file_path} 失败：{e}") from e
    hits = PERSISTED_REGISTRY.add(str(file_path), estimate_tokens(content), source)
    return str(file_path), digest, hits


def _persist_notes(digest: str, size_tokens: int, hits: int) -> str:
    notes = (
        f"sha256: {digest}\n"
        f"size: 约 {size_tokens} tokens\n"
        "【已落盘提醒】完整内容已持久化，请勿重复读取整个文件；"
        "如需特定片段请用 read 的 offset/limit 分页；路径相同意味着内容相同。"
    )
    if hits >= REPEAT_PERSIST_BREAK:
        notes += (
            f"\n【熔断警告】同一内容已第 {hits} 次落盘，请立即停止重复读取整文件，"
            "改用 offset/limit 分页或直接使用已落盘路径。"
        )
    elif hits >= REPEAT_PERSIST_WARN:
        notes += "\n【注意】该内容此前已落盘（同一路径），你可能已读过，请勿重复读取。"
    return notes


def build_persisted_placeholder(content: str, file_path: str, digest: str, hits: int,
                                with_preview: bool = True) -> str:
    parts = [
        PERSISTED_PREFIX,
        f"Full output: {file_path}",
        _persist_notes(digest, estimate_tokens(content), hits),
    ]
    if with_preview:
        parts.append(f"Preview (head):\n{content[:PREVIEW_CHARS]}")
        parts.append(f"Preview (tail):\n{content[-PREVIEW_CHARS:]}")
    parts.append("</persisted-output>")
    return "\n".join(parts)


# ---- L1：大结果落盘 ----

def tool_result_budget(messages: list) -> list:
    """第一层：扫描全部工具结果，超限者落盘，上下文仅保留预览"""
    for i in range(len(messages)):
        msg = messages[i]
        content = msg.get("content", "")
        if msg.get("role") != "tool":
            continue
        if not isinstance(content, str) or content.startswith(PERSISTED_PREFIX):
            continue
        if estimate_tokens(content) <= TOOL_RESULT_CAP:
            continue
        file_path, digest, hits = persist_content(content)
        messages[i]["content"] = build_persisted_placeholder(content, file_path, digest, hits)
    return messages


# ---- L2：消息裁剪 ----

def snip_compact(messages: list, max_message: int = SNIP_MAX_MESSAGES) -> list:
    """第二层：保留前3条（包括系统提示词）和最后47条上下文，切割点对齐 user 消息边界"""
    if len(messages) <= max_message:
        return messages

    keep_head, keep_tail = 3, max_message - 3
    head_end, tail_start = keep_head, len(messages) - keep_tail

    while head_end < len(messages) and messages[head_end].get("role") in ["assistant", "tool"]:
        head_end += 1

    #OpenAI API契约没有对role=='assistant'前必须为role=='user'的约束，所以这里我设计允许切除role=='assistant'前的用户信息，只保证
    #role=='assistant'中的所有tool_calls都有相应的role=='tool'呼应
    while tail_start > 0 and messages[tail_start - 1].get("role") in ["assistant", "tool"]:
        tail_start -= 1

    if head_end >= tail_start:
        return messages

    return messages[:head_end] + [{"role": "user", "content": f"{PERSISTED_PREFIX}snipped {tail_start - head_end} messages, but they have not been persisted</persisted-output>"}] + messages[tail_start:]


# ---- L3：微压缩（先落盘再替换）----

def _recent_tail_start(messages: list) -> int:
    """从尾部向前累计 token，找到保留区的起始下标（对齐 user/system 边界）"""
    keep_tokens = 0
    tail_start = len(messages)
    for i in range(len(messages) - 1, -1, -1):
        keep_tokens += estimate_tokens(json.dumps(messages[i], ensure_ascii=False, default=str))
        if keep_tokens >= KEEP_RECENT_TOKENS and messages[i].get("role") in ["user", "system"]:
            tail_start = i
            break
    return max(1, tail_start)


def micro_compact(messages: list) -> list:
    """第三层：保留近期原始消息，更早的工具结果落盘后替换为占位符（无损）"""
    tail_start = _recent_tail_start(messages)
    for i in range(1, tail_start):
        msg = messages[i]
        content = msg.get("content", "")
        if msg.get("role") != "tool":
            continue
        if not isinstance(content, str) or content.startswith(PERSISTED_PREFIX):
            continue
        if len(content) <= 200:
            continue
        file_path, digest, hits = persist_content(content)
        messages[i]["content"] = build_persisted_placeholder(content, file_path, digest, hits, with_preview=False)
    return messages


# ---- L4：摘要 ----

def write_transcript(messages: list) -> str | None:
    """当前会话持久化到.transcript中"""
    if not TRANSCRIPTS_DIR.is_dir():
        TRANSCRIPTS_DIR.mkdir(exist_ok=True, parents=True)
    transcript_path = TRANSCRIPTS_DIR / f"transcript_{get_session_id_container().get_session_id()}.txt"
    try:
        with transcript_path.open("w", encoding="utf-8") as f:
            for msg in messages:
                if msg.get("role", "") == "system":
                    continue
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        logger.info(f"transcript saved: {transcript_path}")
    except PermissionError as e:
        logger.error(f"错误：没有权限写入：{transcript_path}")
        raise CompactException(f"错误：没有权限写入：{transcript_path}") from e
    except OSError as e:
        logger.error(f"错误：无法写入文件 {transcript_path}：{e}")
        raise CompactException(f"错误：无法写入文件 {transcript_path}：{e}") from e
    except Exception as e:
        logger.error(f"未知错误：保存 {transcript_path} 失败：{e}")
        raise CompactException(f"未知错误：保存 {transcript_path} 失败：{e}") from e

    return str(transcript_path)


SUMMARY_PROMPT = (
    "Summarize this coding-agent conversation so work can continue.\n"
    "Preserve: 1. current goal, 2. key findings/decisions, 3. files read/changed, "
    "4. remaining work, 5. user constraints.\n"
    "If any <persisted-output> block appears in the conversation, keep its file path "
    "verbatim in the summary. Be compact but concrete.\n\n"
)


def _api_summarize(text: str) -> str:
    """调用api对上下文进行浓缩概括"""
    try:
        response = get_client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": SUMMARY_PROMPT + text}],
            max_tokens=2000,
        )
        summary = response.choices[0].message.content
        if summary is None:
            summary = "(empty summary)"
        return summary.strip()
    except Exception as e:
        raise CompactException(f"API压缩出错：{str(e)}") from e


def _split_chunks(lines: list) -> list:
    """按 SUMMARY_CHUNK_CHARS 切块；单行超限则截取头尾"""
    chunks, cur, cur_len = [], [], 0
    for line in lines:
        if len(line) > SUMMARY_CHUNK_CHARS:
            line = line[:PREVIEW_CHARS] + "\n...(single message too large, truncated)...\n" + line[-PREVIEW_CHARS:]
        if cur and cur_len + len(line) > SUMMARY_CHUNK_CHARS:
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append(line)
        cur_len += len(line)
    if cur:
        chunks.append(cur)
    return chunks


def summerize_history(messages: list) -> str:
    """调用API分段摘要会话：逐块摘要、块间递归合并，单次输入恒有界"""
    lines = [json.dumps(m, ensure_ascii=False, default=str) for m in messages]
    parts = ["\n".join(c) for c in _split_chunks(lines)]
    parts = [_api_summarize(p) for p in parts]

    while len(parts) > 1:
        merged, cur, cur_len = [], [], 0
        for p in parts:
            if cur and cur_len + len(p) > SUMMARY_CHUNK_CHARS:
                merged.append(_api_summarize("\n\n".join(cur)))
                cur, cur_len = [], 0
            cur.append(p)
            cur_len += len(p)
        if cur:
            merged.append(_api_summarize("\n\n".join(cur)))
        parts = merged

    return parts[0]


def _tail_start_at_user_boundary(messages: list) -> int:
    """定位最近一轮对话的起点（保留尾部从该处开始，其余交给摘要）。

    连续多个 user 消息属于同一轮（用户任务后紧接着注入的 cron 任务等），
    必须整体保留，否则只保留最后一条会把用户任务压缩掉；
    摘要消息本身也是 user，遇到时必须停止吞并，避免旧摘要被原样保留。
    """
    last_user = -1
    for i in range(len(messages) - 1, -1, -1):
        if _is_plain_user(messages[i]):
            last_user = i
            break
    if last_user == -1:
        return len(messages)

    start = last_user
    while start > 0 and _is_plain_user(messages[start - 1]):
        start -= 1
    return start


def compact_history(messages: list) -> list:
    """最后一层压缩：分段摘要 + 保留 system + 最近一轮完整工具周期"""
    system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
    try:
        transcript_path = write_transcript(messages)
        summary = summerize_history(messages)
    except CompactException:
        raise
    tail_start = _tail_start_at_user_boundary(messages)
    result = [{
        "role": "user",
        "content": (
            f"{PERSISTED_PREFIX}\n[Compacted]:\n {summary}\n [Reminder]:\n "
            f"The original conversation history has been saved to {transcript_path}. "
            f"The file is too large; do not read it in its entirety at once.\n</persisted-output>"
        )
    }, *messages[tail_start:]]
    if system_msg is not None:
        result.insert(0, system_msg)
    return result


def reactive_compact(messages: list) -> list:
    """应急反应式压缩：先落盘超限结果，再分段摘要，保留最小尾部，仅在AgentLoop中API抛出上下文溢出异常时才会触发"""
    system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
    try:
        tool_result_budget(messages)
        transcript_path = write_transcript(messages)
        summary = summerize_history(messages)
    except CompactException:
        raise

    tail_start = _tail_start_at_user_boundary(messages)

    result = [{
        "role": "user",
        "content": (
            f"{PERSISTED_PREFIX}\n[Reactive compacted]:\n {summary}\n [Reminder]:\n "
            f"The original conversation history has been saved to {transcript_path}. "
            f"The file is too large; do not read it in its entirety at once.\n</persisted-output>"
        )
    }, *messages[tail_start:]]
    if system_msg is not None:
        result.insert(0, system_msg)
    return result


class CompactionPipeline:
    @staticmethod
    def compact(messages: list) -> list:
        """每轮评估：L1 恒执行（幂等），L2/L3/L4 按预算触发"""
        if not messages:
            return messages

        messages = tool_result_budget(messages)

        if len(messages) > SNIP_MAX_MESSAGES:
            messages = snip_compact(messages)

        if estimate_messages(messages) > MICRO_TRIGGER:
            logger.info(f"上下文超过 {MICRO_TRIGGER} tokens，触发微压缩")
            messages = micro_compact(messages)

        if estimate_messages(messages) > SUMMARY_TRIGGER:
            logger.info(f"上下文超过 {SUMMARY_TRIGGER} tokens，触发摘要压缩")
            messages = compact_history(messages)

        return messages
