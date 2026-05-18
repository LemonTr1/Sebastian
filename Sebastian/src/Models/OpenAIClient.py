import os
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

class CreateOpenAIClient:
    def __init__(self):
        self.client = OpenAI()

    @staticmethod
    def create_client(self)->OpenAI:
        self.client.base_url = os.getenv("DEEPSEEK_BASE_URL")
        self.client.api_key = str(os.getenv("DEEPSEEK_API_KEY"))
        return self.client