# syntax=docker/dockerfile:1

# 第一阶段：构建依赖
FROM --platform=$BUILDPLATFORM python:3.11-slim as builder

# 设置构建参数
ARG BUILDPLATFORM
ARG TARGETPLATFORM
ARG VERSION
ARG BUILD_DATE
ARG GIT_COMMIT

# 设置构建时的环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 设置工作目录
WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装依赖到指定目录
RUN pip install --no-cache-dir -r requirements.txt -t /python-packages

# 第二阶段：运行环境
FROM --platform=$TARGETPLATFORM python:3.11-slim

# 添加元数据标签
LABEL maintainer="your-email@example.com" \
    org.opencontainers.image.title="Symlink Manager" \
    org.opencontainers.image.description="Monitor Google Drive and local directory changes, create symlinks and notify Emby" \
    org.opencontainers.image.version=${VERSION} \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${GIT_COMMIT} \
    org.opencontainers.image.licenses="MIT"

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CONFIG_PATH=/app/config/config.yaml \
    LOG_PATH=/var/log/symlink \
    DATABASE_PATH=/app/data/database.db \
    TZ=Asia/Shanghai

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    libfuse2 \
    fuse \
    tzdata \
    curl \
    && ln -fs /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r symlink \
    && useradd -r -g symlink -s /sbin/nologin symlink

# 从构建阶段复制 Python 包
COPY --from=builder /python-packages /usr/local/lib/python3.11/site-packages

# 复制项目文件
COPY --chown=symlink:symlink src/ src/
COPY --chown=symlink:symlink config/ config/
COPY --chown=symlink:symlink scripts/ scripts/
COPY --chown=symlink:symlink templates/ templates/

# 创建必要的目录并设置权限
RUN mkdir -p /var/log/symlink /app/data && \
    chown -R symlink:symlink /var/log/symlink /app/data && \
    chmod 755 /var/log/symlink && \
    chmod +x scripts/docker-entrypoint.sh

# 切换到非 root 用户
USER symlink

# 暴露端口
EXPOSE 8501 8000

# 设置健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 设置启动命令
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"] 