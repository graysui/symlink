"""
图形操作界面

使用 Streamlit 构建的图形操作界面，包括:
1. 目录监控
2. Google Drive 监控
3. 系统状态监控
4. 软链接管理
5. 配置管理
6. 日志设置
"""

import os
import time
import streamlit as st
from pathlib import Path

from core.config_manager import config_manager
from core.initializer import Initializer
from core.local_monitor import LocalMonitor
from core.gdrive_api import GoogleDriveMonitor
from core.snapshot_generator import SnapshotGenerator
from core.health_checker import HealthChecker

# 设置页面标题
st.set_page_config(
    page_title="视频文件软链接管理系统",
    page_icon="🎥",
    layout="wide"
)

def render_local_monitor():
    """渲染目录监控页面"""
    st.header("目录监控")
    mount_point = config_manager.get("local_monitor.mount_point")
    st.write(f"监控目录: {mount_point}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("首次全量扫描"):
            initializer = Initializer()
            with st.spinner("正在执行全量扫描..."):
                if initializer.initialize():
                    st.success("全量扫描完成")
                else:
                    st.error("全量扫描失败")
    
    with col2:
        if st.button("启动本地监控"):
            st.session_state.local_monitor = LocalMonitor()
            st.session_state.local_monitor.start()
            st.success("本地监控已启动")

def render_gdrive_monitor():
    """渲染 Google Drive 监控页面"""
    st.header("Google Drive 监控")
    folder_id = config_manager.get("google_drive.folder_id")
    st.write(f"监控文件夹: {folder_id}")
    
    if st.button("启动 Google Drive 监控"):
        st.session_state.gdrive_monitor = GoogleDriveMonitor()
        st.session_state.gdrive_monitor.start()
        st.success("Google Drive 监控已启动")

def render_system_status():
    """渲染系统状态页面"""
    st.header("系统状态")
    health_checker = HealthChecker()
    status = health_checker.check_all()
    
    for component, info in status.items():
        st.write(f"{component}: {'✅' if info['status'] else '❌'} {info['message']}")

def render_symlink_manager():
    """渲染软链接管理页面"""
    st.header("软链接管理")
    target_base = config_manager.get("symlink.target_base")
    st.write(f"软链接目标目录: {target_base}")

def render_config():
    """渲染配置管理页面"""
    st.header("配置管理")
    
    # 基本配置
    st.subheader("基本配置")
    mount_point = st.text_input("挂载点路径", config_manager.get("local_monitor.mount_point"))
    target_base = st.text_input("软链接目标路径", config_manager.get("symlink.target_base"))
    
    # Google Drive 配置
    st.subheader("Google Drive 配置")
    folder_id = st.text_input("文件夹 ID", config_manager.get("google_drive.folder_id"))
    api_key = st.text_input("API 密钥", config_manager.get("google_drive.api_key"), type="password")
    
    # Emby 配置
    st.subheader("Emby 配置")
    server_url = st.text_input("服务器地址", config_manager.get("emby.server_url"))
    emby_api_key = st.text_input("API 密钥", config_manager.get("emby.api_key"), type="password")
    
    if st.button("保存配置"):
        config_manager.set("local_monitor.mount_point", mount_point)
        config_manager.set("symlink.target_base", target_base)
        config_manager.set("google_drive.folder_id", folder_id)
        config_manager.set("google_drive.api_key", api_key)
        config_manager.set("emby.server_url", server_url)
        config_manager.set("emby.api_key", emby_api_key)
        config_manager.save()
        st.success("配置已保存")

def render_logs():
    """渲染日志设置页面"""
    st.header("日志设置")
    log_path = config_manager.get("logging.path")
    log_file = Path(log_path) / "app.log"
    
    if log_file.exists():
        with open(log_file, "r") as f:
            logs = f.readlines()[-50:]  # 显示最后 50 行
            for log in logs:
                st.text(log.strip())

def main():
    """主函数"""
    # 侧边栏导航
    st.sidebar.title("导航")
    page = st.sidebar.radio(
        "选择功能",
        ["目录监控", "Google Drive 监控", "系统状态", "软链接管理", "配置管理", "日志设置"]
    )
    
    # 根据选择渲染对应页面
    if page == "目录监控":
        render_local_monitor()
    elif page == "Google Drive 监控":
        render_gdrive_monitor()
    elif page == "系统状态":
        render_system_status()
    elif page == "软链接管理":
        render_symlink_manager()
    elif page == "配置管理":
        render_config()
    else:
        render_logs()

if __name__ == "__main__":
    main() 