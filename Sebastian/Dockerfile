FROM python:3.12-slim

# 避免交互式提示
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make \
    curl wget \
    vim \
    libpq-dev \
    nmap tshark tcpdump \
    nodejs npm \
    zip \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY . .
CMD ["python", "cli.py"]
