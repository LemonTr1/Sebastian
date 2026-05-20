FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make git curl wget vim libpq-dev \
    openjdk-17-jdk-headless \
    nmap tshark tcpdump \
    whois dnsutils \
    libimage-exiftool-perl \
    nodejs npm zip unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN java -version && javac -version

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# pip 可装的 OSINT 工具
RUN pip install --no-cache-dir \
    sherlock-project \
    holehe \
    maigret \
    socialscan

RUN npm install -g infoooze

COPY . .
CMD ["python", "cli.py"]
