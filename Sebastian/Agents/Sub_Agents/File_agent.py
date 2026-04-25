from agents import *
import typer
from agents import model_settings

from cli import deepseek_model

file_agent = Agent(
    name = "FileManager",
    model = deepseek_model,
    model_settings=ModelSettings(
        temperature=0.2,
        max_tokens=1000
    )
)