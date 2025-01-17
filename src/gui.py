"""
图形用户界面

使用 Streamlit 构建 Web 界面，通过 API 调用后端服务，包括：
1. 监控状态展示和控制
2. 配置管理
3. 系统状态监控
4. 日志查看
"""

import os
import time
import json
import requests
import streamlit as st
from typing import Dict, List, Optional
import pandas as pd

# API 配置
API_BASE_URL = "http://127.0.0.1:8000"

def api_request(method: str, endpoint: str, **kwargs) -> Dict:
    """发送 API 请求"""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API 请求失败: {str(e)}")
        return {}

def render_status():
    """渲染状态页面"""
    st.header("系统状态")
    
    # 添加自动刷新选项
    auto_refresh = st.sidebar.checkbox("自动刷新", value=True)
    
    # 获取系统状态
    status = api_request("GET", "/status")
    
    # 使用列布局展示核心指标
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("软链接总数", status.get("symlink_stats", {}).get("total", 0))
    with col2:
        st.metric("成功数", status.get("symlink_stats", {}).get("success", 0))
    with col3:
        st.metric("失败数", status.get("symlink_stats", {}).get("failed", 0))
    
    # 使用两列布局展示监控状态
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("本地监控")
        if status.get("local_monitor", {}).get("running"):
            st.success("运行中")
            if st.button("停止本地监控"):
                api_request("POST", "/monitor/local/stop")
                st.rerun()
        else:
            st.error("已停止")
            if st.button("启动本地监控"):
                api_request("POST", "/monitor/local/start")
                st.rerun()
        st.text(f"挂载点: {status.get('local_monitor', {}).get('mount_point', '未设置')}")
        st.text(f"轮询间隔: {status.get('local_monitor', {}).get('polling_interval', '未设置')}秒")
    
    with col2:
        st.subheader("Google Drive 监控")
        if status.get("gdrive_monitor", {}).get("enabled"):
            if status.get("gdrive_monitor", {}).get("running"):
                st.success("运行中")
                if st.button("停止 Google Drive 监控"):
                    api_request("POST", "/monitor/gdrive/stop")
                    st.rerun()
            else:
                st.error("已停止")
                if st.button("启动 Google Drive 监控"):
                    api_request("POST", "/monitor/gdrive/start")
                    st.rerun()
        else:
            st.warning("未启用")
        st.text(f"文件夹 ID: {status.get('gdrive_monitor', {}).get('folder_id', '未设置')}")
    
    # 数据库状态
    st.subheader("数据库状态")
    db_status = api_request("GET", "/system/info").get("database_status", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("数据库大小", f"{db_status.get('size', 0)} MB")
    with col2:
        st.metric("记录总数", db_status.get('records', 0))
    with col3:
        st.metric("状态", "正常" if db_status.get('healthy', False) else "异常")
    
    # 最近处理的文件列表
    st.subheader("最近处理文件")
    recent_files = api_request("GET", "/symlink/recent")
    if recent_files.get("files"):
        df = pd.DataFrame(recent_files["files"])
        st.dataframe(
            df,
            column_config={
                "path": "文件路径",
                "status": "状态",
                "created_at": "处理时间",
                "error": "错误信息"
            },
            hide_index=True
        )
    else:
        st.info("暂无处理记录")
    
    # 自动刷新
    if auto_refresh:
        time.sleep(5)
        st.rerun()

def render_config():
    """渲染配置页面"""
    st.header("配置管理")
    
    # 获取当前配置
    config = api_request("GET", "/config")
    
    # 配置导入/导出
    col1, col2 = st.columns(2)
    with col1:
        uploaded_file = st.file_uploader("导入配置文件", type="yaml")
        if uploaded_file and st.button("导入"):
            try:
                content = uploaded_file.read()
                api_request("POST", "/config/import", files={"file": uploaded_file})
                st.success("配置导入成功")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"配置导入失败: {str(e)}")
    
    with col2:
        if st.button("导出配置"):
            config_str = api_request("GET", "/config/export")
            st.download_button(
                label="下载配置文件",
                data=config_str,
                file_name="config.yaml",
                mime="application/x-yaml"
            )
    
    # 使用表单统一提交配置
    with st.form("config_form"):
        # 本地监控配置
        st.subheader("本地监控配置")
        local_config = config.get("local_monitor", {})
        new_mount_point = st.text_input(
            "挂载点",
            local_config.get("mount_point", ""),
            help="本地监控目录的路径，必须是有效的目录路径"
        )
        new_polling_interval = st.number_input(
            "轮询间隔(秒)", 
            min_value=1,
            max_value=3600,
            value=local_config.get("polling_interval", 300),
            help="检查目录变化的时间间隔，建议值: 300秒"
        )
        
        # Google Drive 配置
        st.subheader("Google Drive 配置")
        gdrive_config = config.get("google_drive", {})
        new_gdrive_enabled = st.checkbox(
            "启用 Google Drive",
            gdrive_config.get("enabled", False),
            help="是否启用 Google Drive 监控功能"
        )
        new_folder_id = st.text_input(
            "文件夹 ID",
            gdrive_config.get("folder_id", ""),
            help="Google Drive 文件夹的唯一标识符"
        )
        new_api_interval = st.number_input(
            "API 调用间隔(秒)",
            min_value=1800,
            max_value=86400,
            value=gdrive_config.get("api_call_interval", 3600),
            help="检查 Google Drive 变化的时间间隔，建议值: 3600秒"
        )
        
        # 软链接配置
        st.subheader("软链接配置")
        symlink_config = config.get("symlink", {})
        new_target_base = st.text_input(
            "目标目录",
            symlink_config.get("target_base", ""),
            help="软链接创建的目标目录路径"
        )
        new_overwrite = st.checkbox(
            "覆盖已存在",
            symlink_config.get("overwrite_existing", False),
            help="是否覆盖已存在的软链接文件"
        )
        
        # Emby 配置
        st.subheader("Emby 配置")
        emby_config = config.get("emby", {})
        new_server_url = st.text_input(
            "服务器地址",
            emby_config.get("server_url", ""),
            help="Emby 服务器的完整 URL 地址"
        )
        new_api_key = st.text_input(
            "API 密钥",
            type="password",
            help="Emby 服务器的 API 密钥"
        )
        
        # 提交按钮
        submitted = st.form_submit_button("保存配置")
        
        if submitted:
            # 验证输入
            if new_mount_point and not os.path.isdir(new_mount_point):
                st.error("挂载点必须是有效的目录路径")
                return
            
            if new_gdrive_enabled and not new_folder_id:
                st.error("启用 Google Drive 时必须提供文件夹 ID")
                return
            
            if not new_target_base:
                st.error("目标目录不能为空")
                return
            
            # 确认对话框
            if st.checkbox("确认保存这些更改?", value=False):
                updates = []
                if new_mount_point != local_config.get("mount_point"):
                    updates.append({"path": "local_monitor.mount_point", "value": new_mount_point})
                if new_polling_interval != local_config.get("polling_interval"):
                    updates.append({"path": "local_monitor.polling_interval", "value": str(new_polling_interval)})
                if new_gdrive_enabled != gdrive_config.get("enabled"):
                    updates.append({"path": "google_drive.enabled", "value": str(new_gdrive_enabled)})
                if new_folder_id != gdrive_config.get("folder_id"):
                    updates.append({"path": "google_drive.folder_id", "value": new_folder_id})
                if new_api_interval != gdrive_config.get("api_call_interval"):
                    updates.append({"path": "google_drive.api_call_interval", "value": str(new_api_interval)})
                if new_target_base != symlink_config.get("target_base"):
                    updates.append({"path": "symlink.target_base", "value": new_target_base})
                if new_overwrite != symlink_config.get("overwrite_existing"):
                    updates.append({"path": "symlink.overwrite_existing", "value": str(new_overwrite)})
                if new_server_url != emby_config.get("server_url"):
                    updates.append({"path": "emby.server_url", "value": new_server_url})
                if new_api_key:  # 只在有新输入时更新
                    updates.append({"path": "emby.api_key", "value": new_api_key})
                
                with st.spinner("正在保存配置..."):
                    for update in updates:
                        api_request("POST", "/config", json=update)
                    
                    if updates:
                        api_request("POST", "/config/reload")
                        st.success("配置已更新并重新加载")
                        time.sleep(1)
                        st.rerun()

def render_operations():
    """渲染操作页面"""
    st.header("操作面板")
    
    # 全量扫描
    st.subheader("全量扫描")
    scan_col1, scan_col2 = st.columns([3, 1])
    with scan_col1:
        st.info("扫描所有监控目录并创建软链接")
    with scan_col2:
        if st.button("执行全量扫描", use_container_width=True):
            if st.checkbox("确认执行全量扫描?", value=False):
                with st.spinner("正在执行全量扫描..."):
                    result = api_request("POST", "/scan")
                    if result.get("status") == "success":
                        st.success(f"全量扫描完成，处理文件: {result.get('processed', 0)} 个")
                        if result.get("errors"):
                            st.warning(f"出现 {len(result['errors'])} 个错误")
                            with st.expander("查看错误详情"):
                                for error in result["errors"]:
                                    st.error(error)
                    else:
                        st.error(f"全量扫描失败: {result.get('error', '未知错误')}")
    
    # 单目录扫描
    st.subheader("单目录扫描")
    scan_path = st.text_input("输入要扫描的目录路径", help="相对于挂载点的路径，例如: movies/2024")
    scan_col1, scan_col2 = st.columns([3, 1])
    with scan_col1:
        st.info("仅扫描指定目录并创建软链接")
    with scan_col2:
        if st.button("扫描目录", use_container_width=True) and scan_path:
            if st.checkbox("确认扫描该目录?", value=False):
                with st.spinner(f"正在扫描目录: {scan_path}"):
                    result = api_request("POST", "/scan/directory", json={"path": scan_path})
                    if result.get("status") == "success":
                        st.success(f"目录扫描完成，处理文件: {result.get('processed', 0)} 个")
                        if result.get("errors"):
                            st.warning(f"出现 {len(result['errors'])} 个错误")
                            with st.expander("查看错误详情"):
                                for error in result["errors"]:
                                    st.error(error)
                    else:
                        st.error(f"目录扫描失败: {result.get('error', '未知错误')}")
    
    # Emby 刷新
    st.subheader("Emby 刷新")
    emby_status = api_request("GET", "/emby/status")
    
    if not emby_status.get("connected"):
        st.error("Emby 服务器未连接")
        st.info("请在配置页面检查 Emby 服务器地址和 API 密钥")
        return
        
    # 显示 Emby 服务器状态
    st.info(f"已连接到 Emby 服务器: {emby_status.get('server_url', '')}")
    
    libraries = emby_status.get("libraries", [])
    if not libraries:
        st.warning("未找到可用的媒体库")
        return
        
    # 媒体库选择和刷新
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_library = st.selectbox(
            "选择媒体库", 
            options=[lib["Name"] for lib in libraries],
            format_func=lambda x: x
        )
        library_info = next((lib for lib in libraries if lib["Name"] == selected_library), None)
        if library_info:
            st.text(f"路径: {library_info.get('Path', '未知')}")
            st.text(f"项目数: {library_info.get('ItemCount', 0)}")
    
    with col2:
        if st.button("刷新选中的媒体库", use_container_width=True):
            if st.checkbox("确认刷新该媒体库?", value=False):
                library_id = next(lib["Id"] for lib in libraries if lib["Name"] == selected_library)
                with st.spinner("正在刷新媒体库..."):
                    result = api_request("POST", f"/emby/refresh/library/{library_id}")
                    if result.get("status") == "success":
                        st.success("媒体库刷新已启动")
                        with st.expander("刷新详情"):
                            st.json(result.get("details", {}))
                    else:
                        st.error(f"媒体库刷新失败: {result.get('error', '未知错误')}")
    
    # 全部媒体库刷新
    st.divider()
    refresh_col1, refresh_col2 = st.columns([3, 1])
    with refresh_col1:
        st.info(f"将刷新全部 {len(libraries)} 个媒体库")
    with refresh_col2:
        if st.button("刷新所有媒体库", use_container_width=True):
            if st.checkbox("确认刷新所有媒体库?", value=False):
                with st.spinner("正在刷新所有媒体库..."):
                    result = api_request("POST", "/emby/refresh")
                    if result.get("status") == "success":
                        st.success("所有媒体库刷新已启动")
                        with st.expander("刷新详情"):
                            st.json(result.get("details", {}))
                    else:
                        st.error(f"媒体库刷新失败: {result.get('error', '未知错误')}")

def render_system():
    """渲染系统信息页面"""
    st.header("系统信息")
    
    # 获取系统信息
    info = api_request("GET", "/system/info")
    
    # CPU 使用率
    st.subheader("CPU 使用率")
    cpu_usage = info.get("cpu_usage", {})
    st.progress(float(cpu_usage.get("percentage", 0)) / 100)
    st.text(f"{cpu_usage.get('percentage', 0)}%")
    
    # 内存使用率
    st.subheader("内存使用率")
    memory_usage = info.get("memory_usage", {})
    st.progress(float(memory_usage.get("percentage", 0)) / 100)
    st.text(f"已用: {memory_usage.get('used', 0)}GB / 总计: {memory_usage.get('total', 0)}GB")
    
    # 磁盘使用率
    st.subheader("磁盘使用率")
    disk_usage = info.get("disk_usage", {})
    st.progress(float(disk_usage.get("percentage", 0)) / 100)
    st.text(f"已用: {disk_usage.get('used', 0)}GB / 总计: {disk_usage.get('total', 0)}GB")
    
    # 挂载点状态
    st.subheader("挂载点状态")
    mount_status = info.get("mount_status", {})
    if mount_status.get("mounted", False):
        st.success("已挂载")
    else:
        st.error("未挂载")
        if "error" in mount_status:
            st.text(f"错误: {mount_status['error']}")
    
    # 数据库状态
    st.subheader("数据库状态")
    db_status = info.get("database_status", {})
    if db_status.get("healthy", False):
        st.success("正常")
        st.text(f"大小: {db_status.get('size', 0)}MB")
        st.text(f"记录数: {db_status.get('records', 0)}")
    else:
        st.error("异常")
        if "error" in db_status:
            st.text(f"错误: {db_status['error']}")

def render_logs():
    """渲染日志页面"""
    st.header("系统日志")
    
    # 侧边栏控制
    st.sidebar.subheader("日志设置")
    
    # 日志级别过滤
    log_levels = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    selected_level = st.sidebar.selectbox("日志级别", log_levels, index=0)
    
    # 每页显示行数
    lines_per_page = st.sidebar.slider("每页显示行数", 10, 200, 50)
    
    # 自动刷新设置
    auto_refresh = st.sidebar.checkbox("自动刷新", value=True)
    if auto_refresh:
        refresh_interval = st.sidebar.slider("刷新间隔(秒)", 1, 30, 5)
    
    # 搜索框
    search_query = st.text_input("搜索日志", placeholder="输入关键字进行搜索...")
    
    # 获取日志
    params = {
        "lines": lines_per_page,
        "level": selected_level if selected_level != "ALL" else None,
        "search": search_query if search_query else None
    }
    logs_response = api_request("GET", "/logs", params=params)
    
    if not logs_response.get("logs"):
        st.info("没有找到符合条件的日志")
        return
    
    # 日志导出按钮
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("导出日志", use_container_width=True):
            # 获取所有日志用于导出
            export_params = {
                "lines": 1000,  # 导出更多行
                "level": selected_level if selected_level != "ALL" else None,
                "search": search_query if search_query else None
            }
            export_logs = api_request("GET", "/logs", params=export_params)
            if export_logs.get("logs"):
                log_content = "\n".join(export_logs["logs"])
                st.download_button(
                    label="下载日志文件",
                    data=log_content,
                    file_name=f"system_logs_{time.strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
    
    # 日志显示
    st.subheader("日志内容")
    
    # 使用数据框展示日志
    logs = logs_response.get("logs", [])
    log_data = []
    for log in logs:
        # 解析日志行
        try:
            # 假设日志格式为：时间 [级别] 模块: 消息
            parts = log.split(" ", 3)
            if len(parts) >= 4:
                timestamp, level, module, message = parts
                level = level.strip("[]")
                module = module.strip(":")
            else:
                timestamp, level, module, message = log, "", "", log
        except Exception:
            timestamp, level, module, message = "", "", "", log
            
        log_data.append({
            "时间": timestamp,
            "级别": level,
            "模块": module,
            "消息": message
        })
    
    if log_data:
        df = pd.DataFrame(log_data)
        # 根据日志级别设置不同的背景色
        def highlight_level(val):
            if val == "ERROR":
                return "background-color: #ffcdd2"
            elif val == "WARNING":
                return "background-color: #fff9c4"
            elif val == "INFO":
                return "background-color: #c8e6c9"
            elif val == "DEBUG":
                return "background-color: #e3f2fd"
            return ""
            
        st.dataframe(
            df.style.applymap(highlight_level, subset=["级别"]),
            use_container_width=True,
            height=400
        )
    
    # 分页控制
    if "total_pages" in logs_response:
        total_pages = logs_response["total_pages"]
        current_page = logs_response.get("current_page", 1)
        
        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            page_numbers = st.select_slider(
                "页码",
                options=range(1, total_pages + 1),
                value=current_page
            )
    
    # 自动刷新逻辑
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

def main():
    """主函数"""
    st.set_page_config(
        page_title="软链接管理系统",
        page_icon="🔗",
        layout="wide"
    )
    
    st.title("软链接管理系统")
    
    # 侧边栏导航
    pages = {
        "系统状态": render_status,
        "配置管理": render_config,
        "操作面板": render_operations,
        "系统信息": render_system,
        "系统日志": render_logs
    }
    
    page = st.sidebar.radio("导航", list(pages.keys()))
    
    # 渲染选中的页面
    pages[page]()

if __name__ == "__main__":
    main() 