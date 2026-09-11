import json
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path

import src.hooks  # noqa: F401 — register HITL / token hooks
import src.tools  # noqa: F401 — register toolkits

from src.agent_runner import AgentRunner
from src.agents.brain_agent import build_brain_instructions
from src.config import API_KEY
from src.eval.checkers import run_checkers
from src.tools.toolkits.todo_manager import todo
from src.tools.tools_registry import get_tools_registry
from src.utils.agent_mode import AGENT_MODE
from src.utils.memory_system import MEMORY_SYSTEM
from src.utils.tokens_caculator import get_total_session_tokens

CASES_DIR = Path(__file__).parent / "cases"


def load_cases(case_id: str | None = None, include_online: bool = False, tag: str | None = None) -> list[dict]:
    cases = []
    for path in sorted(CASES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("id", path.stem)
        cases.append(data)
    if case_id:
        cases = [c for c in cases if c["id"] == case_id]
    if tag:
        cases = [c for c in cases if tag in c.get("tags", [])]
    if not include_online:
        cases = [c for c in cases if "online" not in c.get("tags", [])]
    return cases


def _write_setup(workdir: Path, setup: list):
    for item in setup or []:
        dest = workdir / item["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(item.get("content", ""), encoding="utf-8")


def run_case(case: dict, keep: bool = False) -> dict:
    if not API_KEY:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，无法跑 Agent 评测")

    timeout = int(case.get("timeout_sec", 180))
    max_turns = int(case.get("max_turns", 20))
    ref_rounds = case.get("ref_tool_rounds")

    workdir = Path(tempfile.mkdtemp(prefix=".sebastian-eval-", dir=str(Path.home())))
    try:
        _write_setup(workdir, case.get("setup", []))
        prompt = case["prompt"].replace("{workdir}", str(workdir))

        AGENT_MODE.set(AGENT_MODE.BUILD)
        MEMORY_SYSTEM.IS_ALLOWED = False
        todo().reset()
        get_total_session_tokens().clear()

        runner = AgentRunner.create_runner(
            name="Brain_Agent",
            instructions=build_brain_instructions,
            registry=get_tools_registry(),
        )

        started = time.time()
        error = None
        reply = ""
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(runner.run, prompt, max_turns)
                reply = fut.result(timeout=timeout) or ""
        except FutureTimeout:
            error = f"timeout after {timeout}s"
        except Exception as e:
            error = str(e)
            reply = getattr(runner, "last_reply", "") or ""

        latency = round(time.time() - started, 2)
        metrics = dict(getattr(runner, "metrics", {}))
        tokens = get_total_session_tokens().accumulate_token()
        checks = []
        passed = error is None
        if passed:
            checks = run_checkers(workdir, case.get("expect", []), metrics, reply)
            passed = all(c["ok"] for c in checks)
        else:
            checks = [{"type": "exit_ok", "ok": False, "detail": error}]

        inefficient = False
        if passed and isinstance(ref_rounds, int) and metrics.get("tool_rounds", 0) > ref_rounds:
            inefficient = True

        return {
            "id": case["id"],
            "passed": passed,
            "inefficient": inefficient,
            "tool_rounds": metrics.get("tool_rounds", 0),
            "tool_calls": metrics.get("tool_calls", 0),
            "llm_turns": metrics.get("llm_turns", 0),
            "tools_called": metrics.get("tools_called", []),
            "tokens": tokens,
            "latency_sec": latency,
            "reply": reply,
            "checks": checks,
            "error": error,
            "workdir": str(workdir) if keep else None,
        }
    finally:
        if not keep:
            shutil.rmtree(workdir, ignore_errors=True)
