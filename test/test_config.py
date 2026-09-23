"""测试 src/config.py：模型/env 读取、视野模型判断、上下文窗口与 get_client 构造的纯逻辑。"""
import os
import tempfile
import unittest
import importlib
from unittest import mock

# 隔离真实 ~/.sebastian 配置/日志：在导入 src 前把 HOME 指向临时目录
_TMP_HOME = tempfile.mkdtemp(prefix="seb-config-test-")
os.environ["HOME"] = _TMP_HOME


def _reload(env: dict):
    """在受控环境下重载 src.config（禁用 load_dotenv 读取真实 .env，屏蔽用户配置）。"""
    with (
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch("dotenv.load_dotenv"),
        mock.patch("src.utils.model_windows._load_context_settings", return_value={}),
    ):
        import src.utils.model_windows as mw
        mw._CACHE.clear()
        import src.config as cfg
        return importlib.reload(cfg)


class TestModelDefaults(unittest.TestCase):
    """缺省环境变量时的模型相关默认值。"""

    def test_defaults_when_env_missing(self):
        cfg = _reload({})
        self.assertEqual(cfg.MODEL, "deepseek-v4-flash")
        self.assertEqual(cfg.API_KEY, "")
        self.assertEqual(cfg.BASE_URL, "https://api.deepseek.com")

    def test_reads_model_from_env(self):
        cfg = _reload({
            "DEEPSEEK_MODEL": "custom-model",
            "DEEPSEEK_API_KEY": "secret-key",
            "DEEPSEEK_BASE_URL": "http://gateway.local/v1",
        })
        self.assertEqual(cfg.MODEL, "custom-model")
        self.assertEqual(cfg.API_KEY, "secret-key")
        self.assertEqual(cfg.BASE_URL, "http://gateway.local/v1")


class TestIsVisionModel(unittest.TestCase):
    """is_vision_model 的关键字命中/放行与 None 回退到默认模型。"""

    def test_hits_known_vision_keywords(self):
        cfg = _reload({})
        for name in ["gpt-4o", "gpt-4.1-mini", "gpt-4-vision", "qwen-vl-max",
                     "llava:latest", "gemini-1.5-pro", "model-4v", "deepseek-flash"]:
            self.assertTrue(cfg.is_vision_model(name), f"{name} 应为视觉模型")

    def test_plain_model_is_not_vision(self):
        cfg = _reload({})
        self.assertFalse(cfg.is_vision_model("deepseek-chat"))
        self.assertFalse(cfg.is_vision_model("random-llm"))

    def test_none_falls_back_to_configured_model(self):
        cfg = _reload({"DEEPSEEK_MODEL": "gpt-4o"})
        self.assertTrue(cfg.is_vision_model())
        cfg = _reload({"DEEPSEEK_MODEL": "deepseek-v4-flash"})
        self.assertFalse(cfg.is_vision_model())

    def test_custom_keyword_keyword_from_env(self):
        cfg = _reload({
            "DEEPSEEK_MODEL": "the-vision-model",
            "DEEPSEEK_VISION_MODEL_KEYWORDS": "vision",
        })
        # 内置关键字都不含 "vision"，只能是自定义白名单命中
        self.assertTrue(cfg.is_vision_model())
        # 自定义关键字补充进白名单，不影响原有内置关键字命中的集合
        self.assertTrue(cfg.is_vision_model("gpt-4o"))

    def test_empty_or_none_model_does_not_crash(self):
        cfg = _reload({"DEEPSEEK_MODEL": ""})
        self.assertFalse(cfg.is_vision_model())
        self.assertFalse(cfg.is_vision_model(None))


class TestContextWindow(unittest.TestCase):
    """CONTEXT_WINDOW 在导入期按 MODEL 解析，不抛异常。"""

    def test_known_model_resolves(self):
        cfg = _reload({"DEEPSEEK_MODEL": "deepseek-v4-flash"})
        self.assertEqual(cfg.CONTEXT_WINDOW, 1_000_000)
        cfg = _reload({"DEEPSEEK_MODEL": "deepseek-flash"})
        self.assertEqual(cfg.CONTEXT_WINDOW, 1_000_000)
        cfg = _reload({"DEEPSEEK_MODEL": "gpt-4o"})
        self.assertEqual(cfg.CONTEXT_WINDOW, 128_000)

    def test_unknown_model_falls_back_without_crash(self):
        cfg = _reload({"DEEPSEEK_MODEL": "totally-unknown-model"})
        self.assertEqual(cfg.CONTEXT_WINDOW, 128_000)


class TestGetClient(unittest.TestCase):
    """get_client 用当前 API_KEY/BASE_URL 构造 OpenAI 客户端。"""

    def test_constructs_client_with_key_and_base_url(self):
        cfg = _reload({
            "DEEPSEEK_MODEL": "x",
            "DEEPSEEK_API_KEY": "abc",
            "DEEPSEEK_BASE_URL": "http://u",
        })
        with mock.patch.object(cfg, "OpenAI") as openai_mock:
            openai_mock.return_value = "the-client"
            self.assertEqual(cfg.get_client(), "the-client")
        openai_mock.assert_called_once_with(api_key="abc", base_url="http://u")


if __name__ == "__main__":
    unittest.main()