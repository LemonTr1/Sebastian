import os
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

MODEL = str(os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"))
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


# 具备视觉能力（支持 image_url 多模态输入）的模型名片段白名单。
# 识别逻辑为大小写不敏感的子串匹配，可通过环境变量 DEEPSEEK_VISION_MODEL_KEYWORDS 覆盖/扩展。
VISION_MODEL_KEYWORDS = (
    *tuple(
        filter(None, os.getenv("DEEPSEEK_VISION_MODEL_KEYWORDS", "").replace(",", " ").strip().split())
    ),
    "gpt-4o", "gpt-4.1", "gpt-4-vision", "vl", "qwen-vl", "llava", "gemini", "4v", "deepseek-flash"
)


def is_vision_model(model: str | None = None) -> bool:
    """判断指定模型是否支持视觉输入。默认以 .env 配置的 DEEPSEEK_MODEL 为准。

    OpenAI 兼容 API 中，纯文本模型收到含 image_url 的 content part 会直接 400 报错，
    因此调用 view_image 等图片工具前必须据此做优雅降级。
    """
    m = (model or MODEL or "").lower()
    return any(k in m for k in VISION_MODEL_KEYWORDS)


from src.utils.model_windows import resolve_context_window

# 基于 .env 模型名动态解析上下文窗口，进程内只解析一次
CONTEXT_WINDOW = resolve_context_window(MODEL)

def get_client() -> OpenAI:
    _client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
    )
    return _client
