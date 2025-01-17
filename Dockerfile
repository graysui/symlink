# syntax=docker/dockerfile:1

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
    TZ=Asia/Shanghai \
    PYTHONPATH=/app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    fuse3 \
    libfuse3-dev \
    tzdata \
    curl \
    gcc \
    python3-dev \
    && ln -fs /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r symlink \
    && useradd -r -g symlink -m -s /bin/bash symlink

# 复制项目文件
COPY --chown=symlink:symlink . /app/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt && \
    chown -R symlink:symlink /app/

# 创建必要的目录并设置权限
RUN mkdir -p /var/log/symlink /app/data /app/config && \
    chown -R symlink:symlink /var/log/symlink /app/data /app/config && \
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