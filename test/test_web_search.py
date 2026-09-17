from src.tools.toolkits.web_search import web_search

if __name__ == "__main__":
    query = "天气预报"
    result = web_search(query)
    print(result)