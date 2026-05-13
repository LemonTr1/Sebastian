# sandbox.Dockerfile
FROM ubuntu:22.04

# 避免 apt 交互提示
ENV DEBIAN_FRONTEND=noninteractive

# 安装基础工具
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    nodejs npm \
    sudo \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置别名，方便调用
RUN ln -s /usr/bin/python3 /usr/bin/python

# 默认工作目录
WORKDIR /code_agent_workspace

# 为 apt install 准备（禁止安装交互式软件包）
RUN echo 'APT::Get::Assume-Yes "true";' >> /etc/apt/apt.conf.d/90forceyes
RUN echo 'APT::Get::force-yes "true";' >> /etc/apt/apt.conf.d/90forceyes
RUN echo 'DPkg::Options {"--force-confdef";"--force-confold";}' >> /etc/apt/apt.conf.d/90forceyes

# 用一个占位命令保持容器存活（实际执行时会被覆盖）
CMD ["tail", "-f", "/dev/null"]