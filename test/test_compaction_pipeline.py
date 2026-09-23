"""上下文压缩管线回归测试（四层 + 应急 + 防重复读取 + 图片压缩 + 重试收敛）。

纯单元测试，不触发真实 API（摘要/对话调用全部使用 fake client）。
suite 期间持有 CRON_SCHEDULE.agent_lock，避免 cron 线程触发真实 API。
"""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.model_windows import resolve_context_window, _CACHE
from src.config import MODEL, CONTEXT_WINDOW
from src.utils.compaction_pipeline import (
    estimate_tokens, estimate_messages,
    tool_result_budget, snip_compact, micro_compact, compact_history,
    reactive_compact, CompactionPipeline, persist_content, TOOL_RESULT_CAP,
    PERSISTED_REGISTRY, _content_digest, build_persisted_placeholder, PERSISTED_PREFIX,
    compact_view_images, IMAGE_TOKEN_COST,
)
from src.tools.toolkits.cron_schedule import CRON_SCHEDULE

TOOL_RESULTS_DIR = Path.home() / ".sebastian" / ".task_outputs" / "tool-results"
TRANSCRIPTS_DIR = Path.home() / ".sebastian" / ".transcripts"


class FakeSummaryClient:
    def __init__(self):
        self.input_sizes = []
        self.prompts = []
        self.completions = self

    @property
    def chat(self):
        return self

    def create(self, **kwargs):
        prompt = kwargs["messages"][0]["content"]
        self.input_sizes.append(len(prompt))
        self.prompts.append(prompt)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="SUMMARY_OK"))])


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
            choices=[SimpleNamespace(message=SimpleNamespace(content="final answer", tool_calls=None))],
            usage=SimpleNamespace(total_tokens=100),
        )


def _image_tool_msg(kb: int) -> dict:
    b64 = "A" * (kb * 1024)
    return {
        "role": "tool",
        "tool_call_id": "img",
        "content": [
            {"type": "text", "text": "loaded image"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
        ],
    }


class TestCompactionPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CRON_SCHEDULE.agent_lock.acquire()
        cls._pre_tool_files = set(TOOL_RESULTS_DIR.glob("*.txt")) if TOOL_RESULTS_DIR.is_dir() else set()
        cls._pre_transcript_files = set(TRANSCRIPTS_DIR.glob("*")) if TRANSCRIPTS_DIR.is_dir() else set()

    @classmethod
    def tearDownClass(cls):
        for f in set(TOOL_RESULTS_DIR.glob("*.txt")) - cls._pre_tool_files:
            f.unlink(missing_ok=True)
        for f in set(TRANSCRIPTS_DIR.glob("*")) - cls._pre_transcript_files:
            f.unlink(missing_ok=True)
        CRON_SCHEDULE.agent_lock.release()

    # ---------- 1. 窗口解析 ----------
    def test_window_resolution(self):
        _CACHE.clear()
        self.assertEqual(resolve_context_window("deepseek-chat"), 128000)
        self.assertEqual(resolve_context_window("glm-4.7-flash"), 200000)
        self.assertEqual(resolve_context_window("gpt-4o-mini-2024-07-18"), 128000)
        self.assertEqual(resolve_context_window("my-custom-model"), 128000)
        self.assertEqual(resolve_context_window("my-custom-model"), 128000)

    # ---------- 2. token 估算 ----------
    def test_token_estimation(self):
        self.assertTrue(2900 <= estimate_tokens("a" * 12000) <= 3100)
        self.assertEqual(estimate_tokens("中" * 5000), 5000)
        self.assertEqual(estimate_tokens(""), 0)

    def test_image_token_estimation_bounded(self):
        # 图片按固定成本，不按 base64 长度（否则一张 300KB 图会被估成 ~77K token）
        est = estimate_messages([_image_tool_msg(300)])
        self.assertGreaterEqual(est, IMAGE_TOKEN_COST)
        self.assertLess(est, 5000, f"图片估算过高：{est}")

    def test_transcript_and_archive_strip_image_base64(self):
        from src.utils.compaction_pipeline import (
            message_without_images, write_transcript, _recent_tail_start,
        )
        msg = _image_tool_msg(50)
        stripped = json.dumps(message_without_images(msg), ensure_ascii=False)
        self.assertNotIn("base64", stripped)
        self.assertIn("<image omitted>", stripped)

        path = write_transcript([{"role": "system", "content": "s"}, msg])
        on_disk = Path(path).read_text(encoding="utf-8")
        self.assertNotIn("base64", on_disk)
        self.assertIn("<image omitted>", on_disk)

    def test_recent_tail_start_not_skewed_by_image_size(self):
        # 修复前 _recent_tail_start 对整条消息 json.dumps，base64 会虚高计时
        from src.utils.compaction_pipeline import _recent_tail_start

        def ctx(kb):
            return [
                {"role": "system", "content": "s"},
                {"role": "user", "content": "far"},
                {"role": "user", "content": "near"},
                _image_tool_msg(kb),
                {"role": "assistant", "content": "a"},
            ]

        with patch("src.utils.compaction_pipeline.KEEP_RECENT_TOKENS", 2000):
            small = _recent_tail_start(ctx(1))
            huge = _recent_tail_start(ctx(2000))
        self.assertEqual(small, huge)

    # ---------- 3. L1 落盘 ----------
    def test_l1_persist(self):
        huge = "x" * (TOOL_RESULT_CAP * 5)
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "read", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": huge},
            {"role": "user", "content": "q2"},
        ]
        out = tool_result_budget([dict(m) for m in msgs])
        self.assertTrue(out[3]["content"].startswith("<persisted-output>"))
        self.assertIn("Full output:", out[3]["content"])
        self.assertIn(huge[:1000], out[3]["content"])
        self.assertIn(huge[-1000:], out[3]["content"])
        self.assertLess(len(out[3]["content"]), len(huge) // 4)
        # 幂等
        self.assertEqual(tool_result_budget([dict(m) for m in out])[3]["content"], out[3]["content"])
        # 内容寻址去重：同内容同路径
        out2 = tool_result_budget([dict(m) for m in msgs])
        p1 = out[3]["content"].split("Full output: ")[1].split("\n")[0]
        p2 = out2[3]["content"].split("Full output: ")[1].split("\n")[0]
        self.assertEqual(p1, p2)
        # 小结果不动
        small = [dict(m) for m in msgs]
        small[3]["content"] = "short result"
        self.assertEqual(tool_result_budget(small)[3]["content"], "short result")

    # ---------- 4. L2 裁剪 ----------
    def test_l2_snip(self):
        long_msgs = [{"role": "system", "content": "sys"}]
        for i in range(60):
            long_msgs.append({"role": "user", "content": f"u{i}"})
            long_msgs.append({"role": "assistant", "content": f"a{i}"})
        snip = snip_compact([dict(m) for m in long_msgs])
        self.assertLessEqual(len(snip), 51)
        self.assertEqual(snip[0]["content"], "sys")
        self.assertEqual(snip[1]["content"], "u0")
        self.assertEqual(snip[-1]["content"], "a59")
        self.assertEqual(snip_compact(long_msgs[:40]), long_msgs[:40])

    def test_l2_tool_pairing_intact(self):
        pair_msgs = [{"role": "system", "content": "sys"}]
        for i in range(30):
            pair_msgs.append({"role": "user", "content": f"u{i}"})
            pair_msgs.append({"role": "assistant", "content": "a", "tool_calls": [{"id": f"c{i}", "type": "function", "function": {"name": "f", "arguments": "{}"}}]})
            pair_msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": "r"})
        pair_msgs.append({"role": "user", "content": "final"})
        pair_msgs.append({"role": "assistant", "content": "done"})
        snip2 = snip_compact(pair_msgs)
        for i, m in enumerate(snip2):
            if m.get("role") == "tool":
                prev = snip2[i - 1] if i > 0 else {}
                ids = [tc["id"] for tc in prev.get("tool_calls", [])] if prev.get("role") == "assistant" else []
                self.assertIn(m.get("tool_call_id"), ids)

    # ---------- 5. L3 微压缩 ----------
    def test_l3_micro(self):
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
        self.assertTrue(out3[3]["content"].startswith("<persisted-output>"))
        disk_path = out3[3]["content"].split("Full output: ")[1].split("\n")[0]
        self.assertEqual(Path(disk_path).read_text(encoding="utf-8"), "m" * 800)
        self.assertEqual(out3[8]["content"], "recent result keep me")
        self.assertEqual(out3[0]["content"], "sys")

    # ---------- 6. 短会话零动作 ----------
    def test_short_conversation_noop(self):
        short = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        self.assertEqual(CompactionPipeline.compact([dict(m) for m in short]), short)

    # ---------- 7. L4 摘要 ----------
    def test_l4_summary_system_preserved_and_bounded(self):
        fake = FakeSummaryClient()
        big_conv = [{"role": "system", "content": "sys"}]
        for i in range(20):
            big_conv.append({"role": "user", "content": f"user question {i} " + "x" * 8000})
            big_conv.append({"role": "assistant", "content": f"answer {i} " + "y" * 8000})
        with patch("src.utils.compaction_pipeline.get_client", return_value=fake):
            result = compact_history(big_conv)
        self.assertEqual(result[0].get("role"), "system")
        self.assertEqual(result[0]["content"], "sys")
        self.assertEqual(result[1].get("role"), "user")
        self.assertIn("SUMMARY_OK", result[1]["content"])
        self.assertTrue(all(s <= 62000 for s in fake.input_sizes), fake.input_sizes)

    def test_summary_excludes_system(self):
        fake = FakeSummaryClient()
        conv = [{"role": "system", "content": "SECRET_SYSTEM_PROMPT"}]
        for i in range(5):
            conv.append({"role": "user", "content": f"u{i} " + "x" * 3000})
            conv.append({"role": "assistant", "content": f"a{i} " + "y" * 3000})
        with patch("src.utils.compaction_pipeline.get_client", return_value=fake):
            compact_history([dict(m) for m in conv])
        joined = "".join(fake.prompts)
        self.assertNotIn("SECRET_SYSTEM_PROMPT", joined)

    # ---------- 8. 应急：超大工具结果 + 图片 ----------
    def test_reactive_persists_oversized_result(self):
        huge = "x" * (TOOL_RESULT_CAP * 5)
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "do it"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c9", "type": "function", "function": {"name": "bash", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c9", "content": huge},
        ]
        with patch("src.utils.compaction_pipeline.get_client", return_value=FakeSummaryClient()):
            r = reactive_compact(msgs)
        self.assertIn("Full output:", json.dumps(r, ensure_ascii=False))

    def test_reactive_compresses_all_images(self):
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "看这张图"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "view_image", "arguments": "{}"}}]},
            _image_tool_msg(50),  # 最近一轮图片
        ]
        with patch("src.utils.compaction_pipeline.get_client", return_value=FakeSummaryClient()):
            res = reactive_compact(msgs)
        # 所有图片都应被替换为文本占位符（不再有 list content）
        self.assertFalse(any(isinstance(m.get("content"), list) for m in res))
        self.assertTrue(any("view_image-placeholder" in (m.get("content") or "") for m in res))

    def test_compact_view_images_keeps_latest_by_default(self):
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "view_image", "arguments": "{}"}}]},
            _image_tool_msg(5),
            {"role": "user", "content": "再看一张"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c2", "type": "function", "function": {"name": "view_image", "arguments": "{}"}}]},
            _image_tool_msg(5),
        ]
        out = compact_view_images([dict(m) for m in msgs])
        # 最近一轮（末尾）仍为 list；更早的图片被替换为占位符
        self.assertIsInstance(out[-1]["content"], list)
        self.assertFalse(any(isinstance(m.get("content"), list) for m in out[:-1]))

    # ---------- 9. AgentRunner 应急重试收敛 ----------
    def test_retry_converges(self):
        from src.tools.tools_registry import get_tools_registry
        from src.agent_runner import AgentRunner

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
        self.assertEqual(result, "final answer")
        self.assertEqual(runner.client.count, 2)
        first, second = runner.client.calls
        self.assertIsNot(first["messages"], second["messages"])
        self.assertLess(runner.client.sizes[1], runner.client.sizes[0])
        self.assertEqual(second["messages"][0].get("role"), "system")

    # ---------- 10. todo 计划替换式 ----------
    def test_todo_plan_replacement(self):
        from src.tools.tools_registry import get_tools_registry
        from src.agent_runner import AgentRunner
        from src.tools.toolkits.todo_manager import todo, PlanItem

        self.addCleanup(lambda: setattr(todo().state, "items", []))
        runner = AgentRunner.create_runner("Brain_Agent", "base instructions", get_tools_registry())
        runner._ensure_system_prompt()
        # 设计变更：todo 计划不再随 system 自动注入（为命中输入缓存），仅由 _update_system_plan 写入
        self.assertNotIn("<当前任务计划>", runner.context[0]["content"])
        todo().state.items = [PlanItem(content="任务A", status="in_progress")]
        runner._update_system_plan()
        runner._update_system_plan()
        self.assertEqual(runner.context[0]["content"].count("<当前任务计划>"), 1)

    # ---------- 11. 后台通知上限 ----------
    def test_background_notification_cap(self):
        from src.tools.tools_registry import get_tools_registry
        from src.agent_runner import AgentRunner

        r2 = AgentRunner.create_runner("TestAgent", "instructions", get_tools_registry())
        big_out = "B" * 25000
        r2.background_tasks["bg1"] = {"tool_call_id": "x", "command": "bash: {}", "status": "completed"}
        r2.background_results["bg1"] = big_out
        notes = r2.collect_background_results()
        self.assertIn("<persisted-output>", notes[0])
        self.assertNotIn(big_out, notes[0])

    # ---------- 12. 上下文占用钩子 ----------
    def test_context_usage_hook(self):
        from src.hooks.stop.context_usage import show_context_usage
        self.assertIsNone(show_context_usage())

    # ---------- 13. 防重复读取防线 ----------
    def test_anti_reread_defenses(self):
        from src.tools.tools_registry import get_tools_registry
        from src.agent_runner import AgentRunner
        from src.tools.toolkits.todo_manager import todo, PlanItem

        PERSISTED_REGISTRY._entries.clear()
        PERSISTED_REGISTRY._order.clear()

        unique_content = "UNIQUE_" + "y" * 5000
        p, d, h1 = persist_content(unique_content)
        self.assertEqual(h1, 1)
        self.assertEqual(d, _content_digest(unique_content))
        p2, d2, h2 = persist_content(unique_content)
        self.assertEqual((p2, d2, h2), (p, d, 2))
        _, _, h3 = persist_content(unique_content)
        self.assertEqual(h3, 3)

        ph1 = build_persisted_placeholder(unique_content, p, d, h1)
        self.assertIn(f"sha256: {d}", ph1)
        self.assertIn("tokens", ph1)
        self.assertIn("请勿重复读取", ph1)
        self.assertNotIn("【注意】", ph1)
        self.assertNotIn("【熔断警告】", ph1)
        ph2 = build_persisted_placeholder(unique_content, p, d, h2)
        self.assertIn("【注意】", ph2)
        self.assertNotIn("【熔断警告】", ph2)
        ph3 = build_persisted_placeholder(unique_content, p, d, h3)
        self.assertIn("【熔断警告】", ph3)

        for i in range(30):
            persist_content(f"ring_test_{i}_" + "z" * 100)
        self.assertLessEqual(len(PERSISTED_REGISTRY._order), PERSISTED_REGISTRY.max_entries)
        persist_content(unique_content)
        desc = PERSISTED_REGISTRY.describe()
        self.assertTrue(desc)
        self.assertTrue(desc.splitlines()[2].startswith("- " + p))

        sub = AgentRunner.create_runner("TestAgent", "instructions", get_tools_registry())
        sub._ensure_system_prompt()
        self.assertIn("<已落盘文件清单>", sub.context[0]["content"])

        self.addCleanup(lambda: setattr(todo().state, "items", []))
        todo().state.items = [PlanItem(content="任务B", status="pending")]
        br2 = AgentRunner.create_runner("Brain_Agent", "base", get_tools_registry())
        br2._ensure_system_prompt()
        br2._update_system_plan()
        self.assertIn("<已落盘文件清单>", br2.context[0]["content"])
        self.assertEqual(br2.context[0]["content"].count("<当前任务计划>"), 1)

    # ---------- 14. L4/应急：连续 user 段边界 + 摘要护栏 ----------
    def test_consecutive_user_boundary_and_summary_guard(self):
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
        self.assertIn("TASK_MARKER", contents_l4)
        self.assertIn("CRON_MARKER_1", contents_l4)
        self.assertIn("CRON_MARKER_2", contents_l4)
        self.assertEqual(res_l4[0].get("role"), "system")
        self.assertTrue(any("[Compacted]" in c for c in contents_l4))

        with patch("src.utils.compaction_pipeline.get_client", return_value=FakeSummaryClient()):
            res_re = reactive_compact([dict(m) for m in consecutive])
        contents_re = [m.get("content", "") for m in res_re]
        self.assertIn("TASK_MARKER", contents_re)
        self.assertIn("CRON_MARKER_1", contents_re)
        self.assertIn("CRON_MARKER_2", contents_re)
        self.assertEqual(res_re[0].get("role"), "system")

        old_summary = {
            "role": "user",
            "content": f"{PERSISTED_PREFIX}\n[Compacted]:\n OLD_SUMMARY_BODY\n [Reminder]:\n saved\n</persisted-output>",
        }
        guard_conv = [
            {"role": "system", "content": "sys"},
            old_summary,
            {"role": "user", "content": "TASK2"},
            {"role": "user", "content": "CRON2"},
        ]
        with patch("src.utils.compaction_pipeline.get_client", return_value=FakeSummaryClient()):
            res_guard = compact_history([dict(m) for m in guard_conv])
        self.assertTrue(all("OLD_SUMMARY_BODY" not in m.get("content", "") for m in res_guard))
        self.assertTrue(any(m.get("content") == "TASK2" for m in res_guard))
        self.assertTrue(any(m.get("content") == "CRON2" for m in res_guard))


if __name__ == "__main__":
    unittest.main()
