# 测 model_windows 的上下文窗口解析：settings 优先级、字典精确/前缀匹配、缓存与兜底
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
            self.assertEqual(model_windows.resolve_context_window("deepseek-chat"), 64_000_000)

    def test_settings_explicit_window_wins(self):
        settings = _write_settings(self.temp, {"context": {"window_tokens": 5000}})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-chat"), 5000)

    def test_zero_window_falls_through_to_dict(self):
        settings = _write_settings(self.temp, {"context": {"window_tokens": 0}})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-chat"), 64_000_000)

    def test_non_numeric_window_ignored(self):
        settings = _write_settings(self.temp, {"context": {"window_tokens": "abc"}})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-reasoner"), 64_000_000)

    def test_model_override_precedes_dict(self):
        settings = _write_settings(self.temp, {"context": {"model_overrides": {"deepseek-chat": 999}}})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-chat"), 999)

    def test_invalid_override_ignored(self):
        settings = _write_settings(self.temp, {"context": {"model_overrides": {"gpt-4": "bad"}}})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("gpt-4"), 8_000_000)

    def test_exact_match_beats_prefix(self):
        # 不存在 settings，用内置表：exact 应命中精确项而非前缀
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("gpt-4o-mini"), 128_000_000)

    def test_longest_prefix_match(self):
        # gpt-4o-mini-2024-07-18 应命中最长的 gpt-4o-mini，而非 gpt-4/gpt-4o
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("gpt-4o-mini-2024-07-18"), 128_000_000)

    def test_prefix_fallback_for_versioned_model(self):
        # 变体型号通过最长前缀回退
        settings = _write_settings(self.temp, {})
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("deepseek-v4-flash-x7"), 128_000_000)
            self.assertEqual(model_windows.resolve_context_window("claude-3-opus-20240229"), 200_000_000)

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
        self.assertEqual(first, 128_000_000)
        self.assertEqual(second, first)
        mock_load.assert_called_once()  # 缓存命中后不再重新加载

    def test_missing_settings_file_returns_default(self):
        # settings 不存在 → {} → 未知模型兜底
        settings = self.temp / "nope.json"
        with patch.object(model_windows, "SETTINGS", settings):
            self.assertEqual(model_windows.resolve_context_window("mystery-model"), model_windows.DEFAULT_WINDOW)


if __name__ == "__main__":
    unittest.main()