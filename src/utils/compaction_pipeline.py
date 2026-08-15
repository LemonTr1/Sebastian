import typer
from src.logs.app_log import get_log
from pathlib import Path
import json
from src.utils.session_id_container import get_session_id_container
from src.config import MODEL, get_client
from src.utils.exceptions import CompactException

logger = get_log()

#API压缩阈值
CONTEXT_LIMIT = 500000
KEEP_RECENT = 3
#大结果落盘阈值
PERSIST_THRESHOLD = 50000
TOOL_RESULTS_DIR = Path.home() / ".sebastian" / ".task_outputs" / "tool-results"
TRANSCRIPTS_DIR = Path.home() / ".sebastian" / ".transcripts"

def tool_result_budget(messages: list) -> list:
    """第一层压缩：最后一批工具调用大结果落盘，减少上下文占用"""
    index = len(messages)-1
    while index >= 0:
        if "tool_calls" in messages[index].keys():
            break
        index -= 1
    if index == -1:
        return messages

    for i in range(index+1, len(messages)):
        if messages[i].get("role") == "tool" and len(messages[i].get("content", "")) > PERSIST_THRESHOLD:
            tool_call_id = messages[i]["tool_call_id"]
            file_path = TOOL_RESULTS_DIR / f"{tool_call_id}.txt"
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(messages[i]["content"])
                logger.info(f"工具响应 {tool_call_id} 结果已保存至 {file_path}")
            except PermissionError:
                logger.error(f"错误：没有权限写入：{file_path}")
                raise CompactException
            except OSError as e:
                logger.error(f"错误：无法写入文件 {file_path}：{e}")
                raise CompactException
            except Exception as e:
                logger.error(f"未知错误：保存 {file_path} 失败：{e}")
                raise CompactException
            messages[i]['content'] = f"<persisted-output>\nFull output: {file_path}\n Preview:\n{messages[i]['content'][:2000]}\n</persisted-output>"

    return messages

def snip_compact(messages: list, max_message: int = 50) -> list:
    """第二层压缩：保留前3条和最后47条上下文"""
    if len(messages) <= max_message:
        return messages

    keep_head, keep_tail = 3, max_message - 3
    head_end, tail_start = 3, len(messages) - keep_tail #head_end为开区间，tail_start为闭区间

    while head_end < len(messages) and messages[head_end].get("role") in ["assistant", "tool"]:
        head_end += 1

    while tail_start > 0 and messages[tail_start-1].get("role") in ["assistant", "tool"]:
        tail_start -= 1

    if head_end >= tail_start:
        return messages

    return messages[:head_end] + [{"role": "user", "content": f"<SYSTEM_REMINDER>snipped {tail_start-head_end} messages</SYSTEM_REMINDER>"}] + messages[tail_start:]

def micro_compact(messages: list)->list:
    """第三层：旧结果用占位符表示"""
    for i in range(len(messages)-KEEP_RECENT):
        if messages[i].get("role") == "tool" and not messages[i].get("content", "").startswith("<persisted-output>") and len(messages[i].get("content", "")) > 150:
            messages[i]["content"] = "<SYSTEM_REMINDER>Earlier tool result compacted. Re-run if needed.</SYSTEM_REMINDER>"
    return messages

def write_transcript(messages: list)->str | None:
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
    except PermissionError:
        logger.error(f"错误：没有权限写入：{transcript_path}")
        raise CompactException(f"错误：没有权限写入：{transcript_path}")
    except OSError as e:
        logger.error(f"错误：无法写入文件 {transcript_path}：{e}")
        raise CompactException(f"错误：无法写入文件 {transcript_path}：{e}")
    except Exception as e:
        logger.error(f"未知错误：保存 {transcript_path} 失败：{e}")
        raise CompactException(f"未知错误：保存 {transcript_path} 失败：{e}")

    return str(transcript_path)

def summerize_history(messages: list)->str:
    """调用API压缩会话"""
    conversation = json.dumps(messages, default=str)
    prompt = ("Summarize this coding-agent conversation so work can continue.\n"
              "Preserve: 1. current goal, 2. key findings/decisions, 3. files read/changed, "
              "4. remaining work, 5. user constraints.\nBe compact but concrete.\n\n" + conversation)
    try:
        response = get_client().chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=2000)
        summary = response.choices[0].message.content
        if summary is None:
            summary = "(empty summary)"
        return summary.strip()
    except Exception as e:
        raise CompactException(f"API压缩出错：{str(e)}")


def compact_history(messages: list)->list:
    """最后一层压缩：调用API总结"""
    try:
        transcript_path = write_transcript(messages)
        summary = summerize_history(messages)
    except CompactException as e:
        raise CompactException(str(e))
    return [{"role": "user", "content": f"<persisted-output>\n[Compacted]:\n {summary}\n [Reminder]:\n The original conversation history has been saved to {transcript_path}. The file is too large; do not read it in its entirety at once.\n</persisted-output>"}]

def reactive_compact(messages: list) -> list:
    """应急反应式压缩"""
    try:
        transcript_path = write_transcript(messages)
        summary = summerize_history(messages)
    except CompactException as e:
        raise CompactException(str(e))

    tail_start = max(0, len(messages)-5)
    while tail_start > 0 and messages[tail_start-1].get("role") in ["assistant", "tool"]:
        tail_start -= 1

    return [{"role": "user", "content": f"<persisted-output>\n[Reactive compacted]:\n {summary}\n [Reminder]:\n The original conversation history has been saved to {transcript_path}. The file is too large; do not read it in its entirety at once.\n</persisted-output>"}, *messages[tail_start:]]


class CompactionPipeline:
    @staticmethod
    def compact(messages: list) -> list:
        if not TOOL_RESULTS_DIR.is_dir():
            TOOL_RESULTS_DIR.mkdir(exist_ok=True, parents=True)
        messages = tool_result_budget(messages)
        messages = snip_compact(messages)
        messages = micro_compact(messages)

        if len(str(messages)) > CONTEXT_LIMIT:
            logger.info("Context size exceeds limit, applying micro compaction.")
            messages = compact_history(messages)
        return messages
