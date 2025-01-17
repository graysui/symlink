#!/bin/bash
set -e

# 等待 rclone 挂载点就绪
echo "等待 rclone 挂载点就绪..."
while [ ! -d "${MOUNT_POINT}" ]; do
    sleep 5
done

# 检查配置文件
if [ ! -f "${CONFIG_PATH}" ]; then
    echo "错误: 配置文件不存在 ${CONFIG_PATH}"
    exit 1
fi

# 检查必要的环境变量
required_vars=(
    "MOUNT_POINT"
    "TARGET_BASE"
    "LOG_PATH"
    "DATABASE_PATH"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "错误: 环境变量 $var 未设置"
        exit 1
    fi
done

# 确保目录存在
mkdir -p "${LOG_PATH}"
mkdir -p "$(dirname ${DATABASE_PATH})"

# 启动 FastAPI 服务
echo "启动 FastAPI 服务..."
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4 &

# 等待 FastAPI 服务就绪
echo "等待 FastAPI 服务就绪..."
while ! curl -s http://localhost:8000/health > /dev/null; do
    sleep 1
done

# 启动 Streamlit 界面
echo "启动 Streamlit 界面..."
streamlit run src/gui.py --server.port 8501 --server.address 0.0.0.0

# 捕获信号并优雅退出
trap 'kill $(jobs -p)' SIGINT SIGTERM

# 等待所有后台进程完成
wait