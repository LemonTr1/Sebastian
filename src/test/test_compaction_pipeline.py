"""上下文压缩管线回归测试（四层 + 应急 + 防重复读取 + 窗口解析 + 重试收敛）。

不触发真实 API：摘要/对话调用全部使用 fake client。
"""
import sys
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


from src.utils.model_windows import resolve_context_window, _CACHE
from src.config import MODEL, CONTEXT_WINDOW
from src.utils.compaction_pipeline import (
    estimate_tokens, estimate_messages,
    tool_result_budget, snip_compact, micro_compact, compact_history,
    reactive_compact, CompactionPipeline, persist_content, TOOL_RESULT_CAP,
    PERSISTED_REGISTRY, _content_digest, build_persisted_placeholder, PERSISTED_PREFIX,
)
from src.tools.toolkits.cron_schedule import CRON_SCHEDULE

# 阻止定时任务在测试期间触发真实 API 调用
CRON_SCHEDULE.agent_lock.acquire()

# 记录测试前已有文件，测试结束清理新增产物
TOOL_RESULTS_DIR = Path.home() / ".sebastian" / ".task_outputs" / "tool-results"
TRANSCRIPTS_DIR = Path.home() / ".sebastian" / ".transcripts"
_pre_tool_files = set(TOOL_RESULTS_DIR.glob("*.txt")) if TOOL_RESULTS_DIR.is_dir() else set()
_pre_transcript_files = set(TRANSCRIPTS_DIR.glob("*")) if TRANSCRIPTS_DIR.is_dir() else set()


# ---------- 1. 窗口解析 ----------
_CACHE.clear()
check("window exact deepseek-chat", resolve_context_window("deepseek-chat") == 64000)
check("window exact glm-4.7-flash", resolve_context_window("glm-4.7-flash") == 128000)
check("window prefix gpt-4o-mini-2024-07-18", resolve_context_window("gpt-4o-mini-2024-07-18") == 128000)
check("window unknown fallback", resolve_context_window("my-custom-model") == 128000)
check("window cache hit", resolve_context_window("my-custom-model") == 128000)
print(f"  [env] MODEL={MODEL} -> CONTEXT_WINDOW={CONTEXT_WINDOW}")

# ---------- 2. token 估算 ----------
check("estimate english", 2900 <= estimate_tokens("a" * 12000) <= 3100, f"={estimate_tokens('a'*12000)}")
check("estimate chinese", estimate_tokens("中" * 5000) == 5000, f"={estimate_tokens('中'*5000)}")
check("estimate empty", estimate_tokens("") == 0)

# ---------- 3. L1 落盘 ----------
huge = "x" * (TOOL_RESULT_CAP * 5)
msgs = [
    {"role": "system", "content": "sys"},
    {"role": "user", "content": "q"},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "read", "arguments": "{}"}}]},
    {"role": "tool", "tool_call_id": "c1", "content": huge},
    {"role": "user", "content": "q2"},
]
out = tool_result_budget([dict(m) for m in msgs])
check("L1 huge persisted", out[3]["content"].startswith("<persisted-output>"))
check("L1 path in placeholder", "Full output:" in out[3]["content"])
check("L1 head preview", huge[:1000] in out[3]["content"])
check("L1 tail preview", huge[-1000:] in out[3]["content"])
check("L1 context shrunk", len(out[3]["content"]) < len(huge) // 4)
check("L1 idempotent", tool_result_budget([dict(m) for m in out])[3]["content"] == out[3]["content"])
out2 = tool_result_budget([dict(m) for m in msgs])
p1 = out[3]["content"].split("Full output: ")[1].split("\n")[0]
p2 = out2[3]["content"].split("Full output: ")[1].split("\n")[0]
check("L1 sha256 dedup same path", p1 == p2)
small_msgs = [dict(m) for m in msgs]
small_msgs[3]["content"] = "short result"
check("L1 small untouched", tool_result_budget(small_msgs)[3]["content"] == "short result")

# ---------- 4. L2 裁剪 ----------
long_msgs = [{"role": "system", "content": "sys"}]
for i in range(60):
    long_msgs.append({"role": "user", "content": f"u{i}"})
    long_msgs.append({"role": "assistant", "content": f"a{i}"})
snip = snip_compact([dict(m) for m in long_msgs])
check("L2 length bounded", len(snip) <= 51, f"len={len(snip)}")
check("L2 head kept", snip[0]["content"] == "sys" and snip[1]["content"] == "u0")
check("L2 tail kept", snip[-1]["content"] == "a59")
check("L2 under limit no-op", snip_compact(long_msgs[:40]) == long_msgs[:40])

pair_msgs = [{"role": "system", "content": "sys"}]
for i in range(30):
    pair_msgs.append({"role": "user", "content": f"u{i}"})
    pair_msgs.append({"role": "assistant", "content": "a", "tool_calls": [{"id": f"c{i}", "type": "function", "function": {"name": "f", "arguments": "{}"}}]})
    pair_msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": "r"})
pair_msgs.append({"role": "user", "content": "final"})
pair_msgs.append({"role": "assistant", "content": "done"})
snip2 = snip_compact(pair_msgs)
pair_ok = True
for i, m in enumerate(snip2):
    if m.get("role") == "tool":
        prev = snip2[i - 1] if i > 0 else {}
        ids = [tc["id"] for tc in prev.get("tool_calls", [])] if prev.get("role") == "assistant" else []
        if m.get("tool_call_id") not in ids:
            pair_ok = False
check("L2 tool pairing intact", pair_ok)

# ---------- 5. L3 微压缩 ----------
mid_msgs = [
    {"role": "system", "content": "sys"},
    {"role": "user", "content": "q1"},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "read", "arguments": "{}"}}]},
    {"role": "tool", "tool_call_id": "c1", "content": "m" * 800},
    {"role": "user", "content": "q2"},
    {"role": "assistant", "content": "a2"},
    {"role": "user", "content": "q3"},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "c2", "type": "function", "function": {"name": "read", "arguments": "{}"}}]},
    {"role": "tool", "tool_call_id": "c2", "content": "recent result keep me"},
]
out3 = micro_compact([dict(m) for m in mid_msgs])
check("L3 old tool persisted", out3[3]["content"].startswith("<persisted-output>"))
disk_path = out3[3]["content"].split("Full output: ")[1].split("\n")[0]
check("L3 content recoverable", Path(disk_path).read_text(encoding="utf-8") == "m" * 800)
check("L3 recent kept raw", out3[8]["content"] == "recent result keep me")
check("L3 system untouched", out3[0]["content"] == "sys")

# ---------- 6. 短会话零动作 ----------
short = [
    {"role": "system", "content": "sys"},
    {"role": "user", "content": "hello"},
    {"role": "assistant", "content": "hi"},
]
check("short conv compact no-op", CompactionPipeline.compact([dict(m) for m in short]) == short)


# ---------- 7. L4 分段摘要 + system 保留 ----------
class FakeSummaryClient:
    def __init__(self):
        self.input_sizes = []
        self.completions = self

    @property
    def chat(self):
        return self

    def create(self, **kwargs):
        prompt = kwargs["messages"][0]["content"]
        self.input_sizes.append(len(prompt))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="SUMMARY_OK"))])


fake = FakeSummaryClient()
with patch("src.utils.compaction_pipeline.get_client", return_value=fake):
    big_conv = [{"role": "system", "content": "sys"}]
    for i in range(20):
        big_conv.append({"role": "user", "content": f"user question {i} " + "x" * 8000})
        big_conv.append({"role": "assistant", "content": f"answer {i} " + "y" * 8000})
    result = compact_history(big_conv)
    check("L4 system preserved first", result[0].get("role") == "system" and result[0]["content"] == "sys")
    check("L4 summary message present", result[1].get("role") == "user" and "SUMMARY_OK" in result[1]["content"])
    check("L4 chunk inputs bounded", all(s <= 62000 for s in fake.input_sizes), f"sizes={fake.input_sizes}")

fake2 = FakeSummaryClient()
with patch("src.utils.compaction_pipeline.get_client", return_value=fake2):
    big_conv2 = [{"role": "system", "content": "sys"}] + [
        {"role": "user", "content": "z" * 15000} for _ in range(10)
    ]
    result2 = reactive_compact(big_conv2)
    check("L4 reactive system preserved", result2[0].get("role") == "system")
    check("L4 reactive all inputs bounded", all(s <= 62000 for s in fake2.input_sizes), f"sizes={fake2.input_sizes}")

# ---------- 8. 应急：超大工具结果先落盘再摘要 ----------
huge_result_msgs = [
    {"role": "system", "content": "sys"},
    {"role": "user", "content": "do it"},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "c9", "type": "function", "function": {"name": "bash", "arguments": "{}"}}]},
    {"role": "tool", "tool_call_id": "c9", "content": huge},
]
with patch("src.utils.compaction_pipeline.get_client", return_value=FakeSummaryClient()):
    r = reactive_compact(huge_result_msgs)
check("reactive huge persisted", "Full output:" in r[1]["content"] or "<persisted-output>" in json.dumps(r))


# ---------- 9. AgentRunner 应急重试收敛 ----------
from src.tools.tools_registry import get_tools_registry
from src.agent_runner import AgentRunner


class FakeRunnerClient:
    def __init__(self):
        self.calls = []
        self.sizes = []
        self.count = 0

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        self.sizes.append(len(json.dumps(kwargs["messages"], ensure_ascii=False, default=str)))
        self.count += 1
        if self.count == 1:
            raise Exception("context_length_exceeded: prompt too long")
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="final answer", tool_calls=None),
            )],
            usage=SimpleNamespace(total_tokens=100),
        )


runner = AgentRunner.create_runner("TestAgent", "You are a helpful assistant.", get_tools_registry())
runner.client = FakeRunnerClient()
big_history = [
    {"role": "system", "content": "sys"},
    {"role": "user", "content": "hello"},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "read", "arguments": "{}"}}]},
    {"role": "tool", "tool_call_id": "c1", "content": "x" * 50000},
]
runner.set_context(big_history)
with patch("src.utils.compaction_pipeline.get_client", return_value=FakeSummaryClient()):
    result = runner.run("hello")
check("retry returns answer", result == "final answer")
check("retry called twice", runner.client.count == 2)
first, second = runner.client.calls
check("retry messages replaced", first["messages"] is not second["messages"])
check("retry context smaller", runner.client.sizes[1] < runner.client.sizes[0], f"{runner.client.sizes[0]} -> {runner.client.sizes[1]}")
check("retry system first", second["messages"][0].get("role") == "system")

# ---------- 10. todo 替换式 + 跨轮保留 ----------
from src.tools.toolkits.todo_manager import todo, PlanItem
todo().state.items = [PlanItem(content="任务A", status="in_progress")]
br = AgentRunner.create_runner("Brain_Agent", "base instructions", get_tools_registry())
br._ensure_system_prompt()
check("todo injected cross-turn", "<当前任务计划>" in br.context[0]["content"])
br._update_system_plan()
br._update_system_plan()
check("todo no accumulation", br.context[0]["content"].count("<当前任务计划>") == 1)
todo().state.items = []

# ---------- 11. 后台通知上限 ----------
r2 = AgentRunner.create_runner("TestAgent", "instructions", get_tools_registry())
big_out = "B" * 25000
r2.background_tasks["bg1"] = {"tool_call_id": "x", "command": "bash: {}", "status": "completed"}
r2.background_results["bg1"] = big_out
notes = r2.collect_background_results()
check("bg notification capped", "<persisted-output>" in notes[0], notes[0][:80])
check("bg notification full text absent", big_out not in notes[0])

# ---------- 12. 上下文占用钩子 ----------
from src.hooks.stop.context_usage import show_context_usage
res = show_context_usage()
check("context hook returns None", res is None)

# ---------- 13. 防重复读取防线 ----------
unique_content = "UNIQUE_" + "y" * 5000
p, d, h1 = persist_content(unique_content)
check("persist returns (path, digest, hits)", isinstance(p, str) and isinstance(d, str) and h1 == 1)
check("digest matches", d == _content_digest(unique_content))
p2, d2, h2 = persist_content(unique_content)
check("re-persist same path", p2 == p and d2 == d)
check("re-persist hits=2", h2 == 2)
_, _, h3 = persist_content(unique_content)
check("third persist hits=3", h3 == 3)

ph1 = build_persisted_placeholder(unique_content, p, d, h1)
check("placeholder sha256", f"sha256: {d}" in ph1)
check("placeholder size", "tokens" in ph1)
check("placeholder guidance", "请勿重复读取" in ph1)
check("placeholder no warn at hits=1", "【注意】" not in ph1 and "【熔断警告】" not in ph1)
ph2 = build_persisted_placeholder(unique_content, p, d, h2)
check("warn at hits=2", "【注意】" in ph2 and "【熔断警告】" not in ph2)
ph3 = build_persisted_placeholder(unique_content, p, d, h3)
check("break at hits=3", "【熔断警告】" in ph3)

for i in range(30):
    persist_content(f"ring_test_{i}_" + "z" * 100)
check("registry ring eviction <=20", len(PERSISTED_REGISTRY._order) <= PERSISTED_REGISTRY.max_entries)
persist_content(unique_content)
desc = PERSISTED_REGISTRY.describe()
check("registry describe non-empty", desc != "")
check("registry most recent first", desc.splitlines()[2].startswith("- " + p))

sub = AgentRunner.create_runner("TestAgent", "instructions", get_tools_registry())
sub._ensure_system_prompt()
check("registry injected to subagent", "<已落盘文件清单>" in sub.context[0]["content"])

todo().state.items = [PlanItem(content="任务B", status="pending")]
br2 = AgentRunner.create_runner("Brain_Agent", "base", get_tools_registry())
br2._ensure_system_prompt()
br2._update_system_plan()
check("todo update keeps registry", "<已落盘文件清单>" in br2.context[0]["content"])
check("todo update keeps single plan", br2.context[0]["content"].count("<当前任务计划>") == 1)
todo().state.items = []

# ---------- 14. L4/应急：连续 user 段边界 + 摘要护栏 ----------
consecutive = [
    {"role": "system", "content": "sys"},
    {"role": "user", "content": "TASK_MARKER"},
    {"role": "user", "content": "CRON_MARKER_1"},
    {"role": "user", "content": "CRON_MARKER_2"},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "read", "arguments": "{}"}}]},
    {"role": "tool", "tool_call_id": "t1", "content": "r"},
]
with patch("src.utils.compaction_pipeline.get_client", return_value=FakeSummaryClient()):
    res_l4 = compact_history([dict(m) for m in consecutive])
contents_l4 = [m.get("content", "") for m in res_l4]
check("L4 keeps user task before cron", "TASK_MARKER" in contents_l4)
check("L4 keeps all trailing cron users", "CRON_MARKER_1" in contents_l4 and "CRON_MARKER_2" in contents_l4)
check("L4 system first", res_l4[0].get("role") == "system")
check("L4 summary present", any("[Compacted]" in c for c in contents_l4))

with patch("src.utils.compaction_pipeline.get_client", return_value=FakeSummaryClient()):
    res_re = reactive_compact([dict(m) for m in consecutive])
contents_re = [m.get("content", "") for m in res_re]
check("reactive keeps user task before cron", "TASK_MARKER" in contents_re)
check("reactive keeps all trailing cron users", "CRON_MARKER_1" in contents_re and "CRON_MARKER_2" in contents_re)
check("reactive system first", res_re[0].get("role") == "system")

old_summary = {
    "role": "user",
    "content": (
        f"{PERSISTED_PREFIX}\n[Compacted]:\n OLD_SUMMARY_BODY\n [Reminder]:\n saved\n</persisted-output>"
    ),
}
guard_conv = [
    {"role": "system", "content": "sys"},
    old_summary,
    {"role": "user", "content": "TASK2"},
    {"role": "user", "content": "CRON2"},
]
with patch("src.utils.compaction_pipeline.get_client", return_value=FakeSummaryClient()):
    res_guard = compact_history([dict(m) for m in guard_conv])
check("summary guard: old summary not re-kept raw", all("OLD_SUMMARY_BODY" not in m.get("content", "") for m in res_guard))
check("summary guard: task kept", any(m.get("content") == "TASK2" for m in res_guard))
check("summary guard: cron kept", any(m.get("content") == "CRON2" for m in res_guard))

CRON_SCHEDULE.agent_lock.release()

# 清理测试产物
for f in set(TOOL_RESULTS_DIR.glob("*.txt")) - _pre_tool_files:
    f.unlink(missing_ok=True)
for f in set(TRANSCRIPTS_DIR.glob("*")) - _pre_transcript_files:
    f.unlink(missing_ok=True)

print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
