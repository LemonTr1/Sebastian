from src.tools.brain.scripts_registry import get_script_registry

if __name__ == "__main__":
    #所有参数必须都是str类型
    result = get_script_registry().execute_script("project_tree", [])
    print(result)