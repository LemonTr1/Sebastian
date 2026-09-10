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

from src.utils.model_windows import resolve_context_window

# 基于 .env 模型名动态解析上下文窗口，进程内只解析一次
CONTEXT_WINDOW = resolve_context_window(MODEL)

def get_client() -> OpenAI:
    _client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
    )
    return _client
