# 测 model_windows 的上下文窗口解析：settings 优先级、字典精确/前缀匹配、缓存与兜底
import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.utils import model_windows


def _write_settings(temp: Path, data: dict) -> None:
    settings_file = temp / "settings.json"
    settings_file.write_text(json.dumps(data), encoding="utf-8")
    return settings_file


class TestResolveContextWindow(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.temp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        # 清空进程级缓存，避免用例之间相互污染
        model_windows._CACHE.clear()

    def test_known_model_exact(self):
        # settings 无内容时命中内置字典
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-chat"), 128_000)

    def test_settings_explicit_window_wins(self):
        settings = _write_settings(self.temp, {"context": {"window_tokens": 5000}})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-chat"), 5000)

    def test_zero_window_falls_through_to_dict(self):
        settings = _write_settings(self.temp, {"context": {"window_tokens": 0}})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-chat"), 128_000)

    def test_non_numeric_window_ignored(self):
        settings = _write_settings(self.temp, {"context": {"window_tokens": "abc"}})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-reasoner"), 128_000)

    def test_model_override_precedes_dict(self):
        settings = _write_settings(self.temp, {"context": {"model_overrides": {"deepseek-chat": 999}}})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-chat"), 999)

    def test_invalid_override_ignored(self):
        settings = _write_settings(self.temp, {"context": {"model_overrides": {"gpt-4": "bad"}}})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("gpt-4"), 8_000)

    def test_exact_match_beats_prefix(self):
        # 不存在 settings，用内置表：exact 应命中精确项而非前缀
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("gpt-4o-mini"), 128_000)

    def test_longest_prefix_match(self):
        # gpt-4o-mini-2024-07-18 应命中最长的 gpt-4o-mini，而非 gpt-4/gpt-4o
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("gpt-4o-mini-2024-07-18"), 128_000)

    def test_prefix_fallback_for_versioned_model(self):
        # 变体型号通过最长前缀回退
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-v4-flash-x7"), 1_000_000)
            self.assertEqual(model_windows.resolve_context_window("claude-3-opus-20240229"), 200_000)

    def test_prefix_boundary_rejects_non_separator(self):
        # "gpt-4turbo" 不应误命中 "gpt-4"（缺少分隔符），落到默认窗口
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(
                model_windows.resolve_context_window("gpt-4turbo"),
                model_windows.DEFAULT_WINDOW,
            )
            # 带分隔符则正常命中
            self.assertEqual(model_windows.resolve_context_window("gpt-4-0613"), 8_000)

    def test_whitespace_normalized(self):
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("  deepseek-chat  "), 128_000)

    def test_unknown_model_logs_warning(self):
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings), \
                patch.object(model_windows.logger, "warning") as warn:
            model_windows.resolve_context_window("totally-unknown-xyz")
        self.assertTrue(any("未知模型" in str(c) for c in warn.call_args_list))

    def test_unknown_model_default(self):
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("totally-unknown-xyz"), model_windows.DEFAULT_WINDOW)

    def test_none_model_default(self):
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window(None), model_windows.DEFAULT_WINDOW)

    def test_result_is_cached(self):
        # 第二次调用不再读 settings，命中缓存
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings) as mock_settings:
            with patch.object(model_windows, "_load_context_settings", return_value={}) as mock_load:
                first = model_windows.resolve_context_window("qwen-plus")
                second = model_windows.resolve_context_window("qwen-plus")
        self.assertEqual(first, 128_000)
        self.assertEqual(second, first)
        mock_load.assert_called_once()  # 缓存命中后不再重新加载

    def test_missing_settings_file_returns_default(self):
        # settings 不存在 → {} → 未知模型兜底
        settings = self.temp / "nope.json"
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("mystery-model"), model_windows.DEFAULT_WINDOW)

    def test_env_default_model_deepseek_flash(self):
        # .env 实际使用的模型名必须有 1M 窗口，不能落到 128K 兜底
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-flash"), 1_000_000)

    def test_2026_flagship_windows(self):
        # 逐条核对本轮刷新过的机型窗口
        settings = _write_settings(self.temp, {})
        expected = {
            "deepseek-v4-flash": 1_000_000,
            "deepseek-v4-pro": 1_000_000,
            "glm-4.6": 200_000,
            "glm-4.7": 200_000,
            "glm-4.7-flash": 200_000,
            "glm-5.3": 1_000_000,
            "claude-sonnet-5": 1_000_000,
            "claude-haiku-4-5": 200_000,
            "gemini-3.1-pro": 1_000_000,
            # gpt-6-astra 走 gpt-6 前缀回退；gpt-5.4-mini 走精确命中
            "gpt-6-astra": 1_050_000,
            "gpt-5.4-mini": 400_000,
        }
        with patch.object(model_windows, "SETTINGS", settings):
            for name, window in expected.items():
                self.assertEqual(model_windows.resolve_context_window(name), window, f"{name} 窗口不符")


class TestTableIntegrity(unittest.TestCase):
    def test_no_duplicate_keys_in_table(self):
        # 字典字面量里的重复键在运行时会被静默去重，只能从源码 AST 核对
        source = Path(model_windows.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        # 定义带类型注解（MODEL_CONTEXT_WINDOWS: dict[str, int] = {...}），节点是 AnnAssign
        literal = next(
            (
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "MODEL_CONTEXT_WINDOWS"
            ),
            None,
        )
        if not isinstance(literal, ast.Dict):
            self.fail("未找到 MODEL_CONTEXT_WINDOWS 字面量定义")
        keys = [k.value for k in literal.keys if isinstance(k, ast.Constant)]
        duplicates = {k for k in keys if keys.count(k) > 1}
        self.assertEqual(duplicates, set(), f"字典存在重复键：{duplicates}")


if __name__ == "__main__":
    unittest.main()