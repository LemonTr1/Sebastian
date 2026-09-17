from src.tools.toolkits.web_fetch import web_fetch

if __name__ == "__main__":
    url = "https://www.baidu.com"
    result = web_fetch(url)
    print(result)