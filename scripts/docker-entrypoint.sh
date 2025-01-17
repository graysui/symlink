#!/bin/bash
set -e

# 输出系统信息
echo "系统架构: $(uname -m)"
echo "Python 版本: $(python3 --version)"
echo "Python 路径: $(which python3)"
echo "Site packages 路径: $(python3 -c 'import site; print(site.getsitepackages()[0])')"
echo "当前用户: $(whoami)"
echo "PATH: $PATH"
echo "PYTHONPATH: $PYTHONPATH"

# 检查 uvicorn 是否可用
echo "检查 uvicorn 安装..."
if python3 -c "import uvicorn" 2>/dev/null; then
    echo "uvicorn 已安装"
    python3 -c "import uvicorn; print('uvicorn 版本:', uvicorn.__version__)"
    echo "uvicorn 路径: $(python3 -c 'import uvicorn; print(uvicorn.__file__)')"
else
    echo "错误: uvicorn 未安装或无法导入"
    pip list | grep uvicorn || echo "未找到 uvicorn 包"
    exit 1
fi

# 检查并创建配置文件
if [ ! -f "${CONFIG_PATH}" ]; then
    echo "配置文件不存在，从示例配置创建..."
    if [ -f "/app/config/config.yaml.example" ]; then
        cp /app/config/config.yaml.example "${CONFIG_PATH}"
        echo "已创建默认配置文件"
    else
        echo "错误: 示例配置文件不存在"
        exit 1
    fi
fi

# 等待 rclone 挂载点就绪
echo "等待 rclone 挂载点就绪..."
while [ ! -d "${MOUNT_POINT}" ]; do
    sleep 5
done

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
mkdir -p "$(dirname ${CONFIG_PATH})"

# 启动 FastAPI 服务
echo "启动 FastAPI 服务..."
echo "尝试直接运行 uvicorn..."
cd /app && PYTHONPATH=/app python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4 &

# 等待 FastAPI 服务就绪
echo "等待 FastAPI 服务就绪..."
while ! curl -s http://localhost:8000/health > /dev/null; do
    sleep 1
done

# 启动 Streamlit 界面
echo "启动 Streamlit 界面..."
cd /app && PYTHONPATH=/app python3 -m streamlit run src/gui.py --server.port 8501 --server.address 0.0.0.0

# 捕获信号并优雅退出
trap 'kill $(jobs -p)' SIGINT SIGTERM

# 等待所有后台进程完成
wait