from src.tools.toolkits.skill_registry import get_skill_registry

if __name__ == "__main__":
    #所有参数必须都是str类型
    result = get_skill_registry().execute_script("project_tree", [])
    print(result)