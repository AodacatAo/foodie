# 食集 · QNAP NAS 容器镜像
# 基础镜像走 Docker Hub（国内不可达时用 --build-arg BASE_IMAGE=<镜像源>/library/python:3.11-slim），
# pip 走清华镜像，Playwright Chrome 走 npmmirror 加速，apt 走阿里源
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Chromium(Chrome for Testing)/OCR(onnxruntime)/Whisper 运行所需系统库（apt 走阿里源，快 10 倍+）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates fonts-liberation \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 libdrm2 \
    libgbm1 libglib2.0-0 libnspr4 libnss3 libpango-1.0-0 libx11-6 libxcb1 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2 \
    libxshmfence1 libxtst6 xdg-utils libegl1 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖层（代码不变时复用缓存）
COPY backend/requirements.txt requirements.txt
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Playwright + Chrome for Testing（channel=chrome 需要；镜像加速）
RUN pip install playwright -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright \
       python -m playwright install chrome \
    && rm -rf /root/.cache/ms-playwright/.links

# 应用代码（data 目录由 docker-compose 卷挂载，不入镜像）
COPY backend/app backend/app
COPY frontend/dist frontend/dist
COPY .env .env

WORKDIR /app/backend
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
