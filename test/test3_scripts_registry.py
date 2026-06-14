from src.tools.brain.scripts_registry import get_script_registry
from src.tools.brain.skill_registry import get_skill_registry

if __name__ == "__main__":
    print(get_script_registry().scripts_describe_available())
    print()
    print(get_skill_registry().describe_available())