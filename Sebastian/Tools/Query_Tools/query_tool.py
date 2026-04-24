from agents import function_tool
import typer
import requests

@function_tool
def query_on_searxng(question: str):
    """
    这是一个专门在互联网搜索信息的工具
    Args:
        question: 问题
    Returns:
        infos: 解答问题有关的网页信息
    """
    typer.echo("[执行中]AI正在调用搜索引擎工具")
    typer.echo(f"[执行中]正在帮忙处理用户问题：{question}")
    url = "http://localhost:6080/search"
    params = {"q": question, "format": "json", "pageno": 1}
    try:
        response = requests.get(url, params=params)
    except requests.exceptions.ConnectionError:
        typer.echo(typer.style("[Error]搜索失败",fg=typer.colors.RED, bold=True))
        return None
    data = response.json()
    infos = []
    typer.echo("[执行中]AI正在组织语言")
    max_result = 5 #只取前5条信息
    for item in data["results"]:
        infos.append(item['content'])
        if --max_result < 0:
            break
    return infos
