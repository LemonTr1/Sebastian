from src.tools.toolkits.subagent import get_sub_agent_registry

if __name__ == "__main__":
    print(get_sub_agent_registry().describe_available())