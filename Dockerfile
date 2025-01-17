# 使用官方 Python 基础镜像
FROM python:3.8-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CONFIG_PATH=/app/config/config.yaml \
    LOG_PATH=/var/log/symlink \
    DATABASE_PATH=/app/data/database.db

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libfuse2 \
    fuse \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
COPY src/ src/
COPY config/ config/
COPY scripts/ scripts/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建必要的目录
RUN mkdir -p /var/log/symlink && \
    chmod 755 /var/log/symlink && \
    mkdir -p /app/data

# 设置启动脚本权限
RUN chmod +x scripts/docker-entrypoint.sh

# 暴露 Streamlit 端口
EXPOSE 8501

# 设置启动命令
CMD ["/app/scripts/docker-entrypoint.sh"] 