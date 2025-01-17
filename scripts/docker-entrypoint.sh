#!/bin/bash

# 启动主程序
python3 src/main.py &

# 等待几秒确保主程序启动
sleep 3

# 启动 GUI
exec streamlit run src/gui.py --server.address 0.0.0.0