import docker
from Interface.Exception.ImageNotFoundException import ImageNotFoundException

def ensure_image(image_name: str)->str:
    """检查本地是否有指定镜像，没有则自动拉取，并返回镜像名称"""
    client = docker.from_env()

    try:
        # 尝试获取镜像，如果存在直接返回
        image = client.images.get(image_name)
        return image.tags[0]
    except docker.errors.ImageNotFound:
        # 镜像不存在，执行拉取
        image = client.images.pull(image_name)
        return image.tags[0]
    except docker.errors.APIError as e:
        raise ImageNotFoundException(f"Docker镜像：{image_name}拉取失败：{str(e)}")