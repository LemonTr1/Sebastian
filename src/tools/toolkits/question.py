import json

import typer

from src.logs.app_log import get_log
from src.tools.tools_registry import get_tools_registry
from src.utils.eval_flag import is_eval_mode
from src.utils.question_client import QuestionClient

MAX_OPTIONS = 20
MAX_OPTION_CHARS = 200
MAX_QUESTION_CHARS = 4000
DEFAULT_TIMEOUT = 300
MIN_TIMEOUT = 5
MAX_TIMEOUT = 3600

logger = get_log()

_QUESTION_CLIENT = QuestionClient(theme="dark")

# 失败 status → 给 LLM 的下一步指引（把"工具失败"转成可执行动作，避免反复弹窗）
_HINTS = {
    "timeout": "不要重复弹窗追问。请基于合理默认值继续，或在回复正文中说明你的假设并请用户确认。",
    "cancelled": "请在回复中简要说明待确认事项，结束本轮等待用户下一条消息。",
    "busy": "等待其结束或改为在正文中提问。",
    "unavailable": "请直接在回复正文中向用户提问，并以问句结束本轮。",
}

_MESSAGES = {
    "timeout": "用户在等待时间内未作答",
    "cancelled": "用户关闭了提问窗口，未作答",
    "busy": "已有另一个提问窗口正在等待回答",
    "unavailable": "当前环境无法弹出交互窗口",
}


def _result(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _error(message: str) -> str:
    return _result(
        {
            "success": False,
            "status": "error",
            "answer": None,
            "selected_option": None,
            "is_free_text": False,
            "error_message": message,
        }
    )


def _normalize_options(options) -> tuple[list, str | None]:
    """归一化选项，返回 (选项列表, 错误信息)。错误信息非空时列表为空。"""
    if options is None:
        return [], None

    # LLM 偶尔会把数组序列化成字符串
    if isinstance(options, str):
        if not options.strip().startswith("["):
            return [], "options 必须是字符串数组"
        try:
            options = json.loads(options)
        except json.JSONDecodeError:
            return [], "options 必须是字符串数组，且每个元素为字符串"

    if not isinstance(options, (list, tuple)):
        return [], "options 必须是字符串数组，且每个元素为字符串"

    normalized = []
    for item in options:
        text = str(item).strip()
        if not text:
            continue
        if len(text) > MAX_OPTION_CHARS:
            return [], f"选项过长（单个选项不超过 {MAX_OPTION_CHARS} 字）：{text[:30]}..."
        if text not in normalized:  # 保序去重
            normalized.append(text)

    if len(normalized) > MAX_OPTIONS:
        return [], f"选项过多（最多 {MAX_OPTIONS} 个，当前 {len(normalized)} 个）"
    return normalized, None


def _normalize_timeout(timeout) -> int:
    if timeout is None or isinstance(timeout, bool):
        return DEFAULT_TIMEOUT
    try:
        value = int(timeout)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT
    return max(MIN_TIMEOUT, min(value, MAX_TIMEOUT))


def question(question: str, options: list | None = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    """弹窗向用户提问并阻塞等待作答，返回 JSON 字符串。"""
    text = "" if question is None else str(question).strip()
    if not text:
        return _error("question 参数不能为空")
    if len(text) > MAX_QUESTION_CHARS:
        text = text[:MAX_QUESTION_CHARS] + "...(问题过长已截断)"

    normalized_options, err = _normalize_options(options)
    if err:
        return _error(err)

    wait_seconds = _normalize_timeout(timeout)

    # eval 模式无真人可回答，提前短路（窗口与终端降级都不走）
    if is_eval_mode():
        logger.info("[question] eval 模式，跳过弹窗")
        return _result(
            {
                "success": False,
                "status": "unavailable",
                "answer": None,
                "selected_option": None,
                "is_free_text": False,
                "error_message": "Eval 模式下无真人可回答问题",
                "hint": _HINTS["unavailable"],
            }
        )

    typer.echo(typer.style(
        f"\n> [question] 等待用户回答（最长 {wait_seconds}s）...",
        fg=typer.colors.CYAN, bold=True,
    ))

    try:
        res = _QUESTION_CLIENT.ask(
            question=text,
            options=normalized_options or None,
            timeout=wait_seconds,
        )
    except Exception as e:
        logger.error(f"[question] 弹窗调用异常: {e}")
        return _error(f"提问窗口调用失败：{e}")

    status = res.get("status", "error")
    answer = res.get("answer")
    # 只记元信息与答案长度，不记答案正文（可能含用户隐私）
    logger.info(
        f"[question] status={status} options={len(normalized_options)} "
        f"timeout={wait_seconds} q_len={len(text)} a_len={len(answer or '')}"
    )

    if status == "answered":
        return _result(
            {
                "success": True,
                "status": "answered",
                "answer": answer,
                "selected_option": res.get("selected_option"),
                "is_free_text": bool(res.get("is_free_text")),
            }
        )

    payload = {
        "success": False,
        "status": status,
        "answer": None,
        "selected_option": None,
        "is_free_text": False,
        "error_message": res.get("error") or _MESSAGES.get(status, "提问失败"),
    }
    if status == "timeout":
        payload["error_message"] = f"用户在 {wait_seconds} 秒内未作答"
    if status in _HINTS:
        payload["hint"] = _HINTS[status]
    return _result(payload)


QUESTION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "question",
        "description": (
            "向用户弹出一个交互窗口提问，并阻塞等待用户作答（用户可点选你给出的选项，也可自由输入文本）。"
            "当你缺少无法从上下文推断、且不同取值会显著改变结果的关键信息时使用，例如："
            "目标技术栈/命名方案的选择、删除或覆盖的范围确认、需求歧义澄清、用户偏好（语言/风格/格式）。"
            "能自行合理假设并继续的琐碎问题不要使用本工具。"
            "若答案可枚举，务必传 options（2-6 个互斥短选项，用户始终可以直接输入，无需额外添加'其他'选项）；"
            "开放式问题不要传 options。一次只问一个问题，不要在同一轮里连续提问；同一任务内最多提问 2 次。"
            "返回 status 为 timeout/cancelled/unavailable 时表示用户未作答，禁止立即重复调用，"
            "应改为基于合理默认值继续，或在回复正文中向用户提问并结束本轮。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "向用户提出的完整问题，需自带必要上下文，让用户无需回看前文即可回答",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选。2-6 个互斥的简短选项（每个不超过 200 字）",
                },
                "timeout": {
                    "type": "integer",
                    "description": "可选。等待用户回答的秒数，默认 300，范围 5-3600",
                },
            },
            "required": ["question"],
        },
    },
}

# 提问不是审批，必须为非 HITL：否则会先弹 HITL 审批窗、再弹提问窗
get_tools_registry().register_tool("question", question, QUESTION_SCHEMA, hitl=False, for_agent="Brain_Agent")