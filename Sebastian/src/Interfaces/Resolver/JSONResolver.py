import json
from src.Interfaces.Exception.JsonResolverError import JsonResolverError

class JsonResolver:
    @staticmethod
    def check(json_dict: dict):
        error_keys = []
        flag = True
        if "success" not in json_dict:
            flag = False
            error_keys.append("success")
        if "operator" not in json_dict:
            flag = False
            error_keys.append("operator")
        if "tool_name" not in json_dict:
            flag = False
            error_keys.append("tool_name")
        if "summary" not in json_dict:
            flag = False
            error_keys.append("summary")
        if "data" not in json_dict:
            flag = False
            error_keys.append("data")
        if "need_confirmed" not in json_dict:
            flag = False
            error_keys.append("need_confirmed")
        if not flag:
            raise JsonResolverError(
                f"返回格式中不存在这些字段:{error_keys}，"
                """
                json格式必须为：
                {
                  "success": 操作是否执行成功，成功为"True"，失败为"False",
                  "operator": <你的名字:"File"或"Code"或"Web"或"Memory">,
                  "tool_name": [<完成指令调用的所有工具列表>],
                  "summary": "<自然语言描述的操作摘要>",
                  "data": {
                    // 具体操作的相关数据
                  },
                  "need_confirmed": "需要用户确认为True,否则为False"
                }
                """
            )
        return True

    @staticmethod
    def resolve_to_json(json_str: str)->dict:
        after_load = json.loads(json_str)
        JsonResolver.check(after_load)
        return after_load


