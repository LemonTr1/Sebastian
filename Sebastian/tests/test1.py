from src.Interfaces.Docker.EnsureDocker import ensure_image
from src.Interfaces.Exception.ImageNotFoundException import ImageNotFoundException


def main():
    try:
        ensure_image("python:3.11-slim")
        print("拉取成功")
    except ImageNotFoundException as e:
        print(e)
        pass

if __name__ == "__main__":
    main()