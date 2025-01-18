"""
主程序入口

负责启动和管理整个系统，包括：
1. 初始化配置
2. 设置日志
3. 启动本地监控
4. 启动 Google Drive 监控
5. 启动健康检查
6. 提供 API 接口
"""

import os
import sys
import signal
import logging
from pathlib import Path
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel

from src.core.config_manager import config_manager
from src.core.log_manager import LogManager
from src.core.local_monitor import LocalMonitor
from src.core.gdrive_api import GoogleDriveAPI
from src.core.health_checker import HealthChecker
from src.core.initializer import Initializer
from src.core.symlink_manager import SymlinkManager
from src.core.emby_notifier import EmbyNotifier

# 创建 FastAPI 应用
app = FastAPI(title="Symlink Manager API")

# 全局服务实例
monitor: Optional[LocalMonitor] = None
gdrive_monitor: Optional[GoogleDriveAPI] = None
health_checker: Optional[HealthChecker] = None
symlink_manager: Optional[SymlinkManager] = None
emby_notifier: Optional[EmbyNotifier] = None

class ConfigUpdate(BaseModel):
    path: str
    value: str

def setup_logging():
    """初始化日志设置"""
    log_manager = LogManager()
    log_manager.setup_logging()
    return log_manager.get_logger(__name__)

def init_services():
    """初始化所有服务"""
    global monitor, gdrive_monitor, health_checker, symlink_manager, emby_notifier
    
    # 创建软链接管理器
    symlink_manager = SymlinkManager()
    
    # 创建 Emby 通知器
    emby_notifier = EmbyNotifier()
    
    # 创建本地监控器
    monitor = LocalMonitor()
    
    # 创建 Google Drive 监控器
    if config_manager.get('google_drive.enabled'):
        try:
            gdrive_monitor = GoogleDriveAPI()
            gdrive_monitor.start()
            logger.info("启动 Google Drive 监控")
        except Exception as e:
            logger.warning(f"Google Drive 监控启动失败: {e}")
    
    # 创建健康检查器
    health_checker = HealthChecker()
    health_checker.start()
    logger.info("启动健康检查")
    
    # 启动本地监控
    monitor.start()
    logger.info("启动本地监控")

def cleanup_services():
    """清理所有服务"""
    if monitor:
        monitor.stop()
    if gdrive_monitor:
        gdrive_monitor.stop()
    if health_checker:
        health_checker.stop()

@app.get("/status")
async def get_status():
    """获取系统状态"""
    status = {
        "local_monitor": {
            "running": monitor and monitor.is_running(),
            "mount_point": config_manager.get('local_monitor.mount_point'),
            "polling_interval": config_manager.get('local_monitor.polling_interval')
        },
        "gdrive_monitor": {
            "running": gdrive_monitor and gdrive_monitor.is_running(),
            "enabled": config_manager.get('google_drive.enabled'),
            "folder_id": config_manager.get('google_drive.folder_id')
        },
        "symlink": {
            "target_base": config_manager.get('symlink.target_base'),
            "overwrite_existing": config_manager.get('symlink.overwrite_existing')
        },
        "health": health_checker and health_checker.check_all()
    }
    return status

@app.get("/health")
async def get_health():
    """获取详细的健康状态"""
    if not health_checker:
        raise HTTPException(status_code=500, detail="健康检查器未初始化")
    return health_checker.check_all()

@app.post("/monitor/local/{action}")
async def control_local_monitor(action: str):
    """控制本地监控"""
    if not monitor:
        raise HTTPException(status_code=500, detail="本地监控未初始化")
    
    if action == "start":
        monitor.start()
        return {"status": "started"}
    elif action == "stop":
        monitor.stop()
        return {"status": "stopped"}
    else:
        raise HTTPException(status_code=400, detail="无效的操作")

@app.post("/monitor/gdrive/{action}")
async def control_gdrive_monitor(action: str):
    """控制 Google Drive 监控"""
    if not gdrive_monitor:
        raise HTTPException(status_code=500, detail="Google Drive 监控未初始化")
    
    if action == "start":
        gdrive_monitor.start()
        return {"status": "started"}
    elif action == "stop":
        gdrive_monitor.stop()
        return {"status": "stopped"}
    else:
        raise HTTPException(status_code=400, detail="无效的操作")

@app.post("/scan")
async def run_full_scan():
    """执行全量扫描"""
    try:
        initializer = Initializer()
        initializer.initialize()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"全量扫描失败: {str(e)}")

@app.post("/emby/refresh")
async def refresh_emby(path: Optional[str] = None):
    """刷新 Emby 媒体库"""
    if not emby_notifier:
        raise HTTPException(status_code=500, detail="Emby 通知器未初始化")
    
    try:
        if path:
            result = emby_notifier.refresh_library(path)
        else:
            result = emby_notifier.refresh_all()
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新 Emby 失败: {str(e)}")

@app.get("/logs")
async def get_logs(lines: int = 50):
    """获取最新日志"""
    log_path = config_manager.get('logging.path')
    log_file = os.path.join(log_path, 'app.log')
    
    if not os.path.exists(log_file):
        return {"logs": []}
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = f.readlines()[-lines:]
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {str(e)}")

@app.post("/config")
async def update_config(update: ConfigUpdate):
    """更新配置"""
    try:
        config_manager.set(update.path, update.value)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")

@app.get("/config")
async def get_config():
    """获取当前配置"""
    return {
        "local_monitor": {
            "mount_point": config_manager.get('local_monitor.mount_point'),
            "polling_interval": config_manager.get('local_monitor.polling_interval'),
            "watch_patterns": config_manager.get('local_monitor.watch_patterns'),
            "ignore_patterns": config_manager.get('local_monitor.ignore_patterns')
        },
        "google_drive": {
            "enabled": config_manager.get('google_drive.enabled'),
            "folder_id": config_manager.get('google_drive.folder_id'),
            "api_call_interval": config_manager.get('google_drive.api_call_interval')
        },
        "symlink": {
            "target_base": config_manager.get('symlink.target_base'),
            "overwrite_existing": config_manager.get('symlink.overwrite_existing'),
            "video_extensions": config_manager.get('symlink.video_extensions')
        },
        "emby": {
            "server_url": config_manager.get('emby.server_url'),
            "api_key": "********"  # 隐藏敏感信息
        },
        "logging": {
            "path": config_manager.get('logging.path'),
            "level": config_manager.get('logging.level'),
            "max_size": config_manager.get('logging.max_size'),
            "backup_count": config_manager.get('logging.backup_count')
        }
    }

@app.post("/config/reload")
async def reload_config():
    """重新加载配置文件"""
    try:
        config_manager.reload()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新加载配置失败: {str(e)}")

@app.get("/symlink/status")
async def get_symlink_status():
    """获取软链接状态"""
    if not symlink_manager:
        raise HTTPException(status_code=500, detail="软链接管理器未初始化")
    return {
        "target_base": symlink_manager.target_base,
        "video_extensions": symlink_manager.video_extensions,
        "overwrite_existing": symlink_manager.overwrite_existing
    }

@app.post("/symlink/process")
async def process_file(file_path: str):
    """处理单个文件的软链接"""
    if not symlink_manager:
        raise HTTPException(status_code=500, detail="软链接管理器未初始化")
    try:
        result = symlink_manager.process_file(file_path)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理文件失败: {str(e)}")

@app.get("/emby/status")
async def get_emby_status():
    """获取 Emby 服务状态"""
    if not emby_notifier:
        raise HTTPException(status_code=500, detail="Emby 通知器未初始化")
    try:
        libraries = emby_notifier._get_libraries()
        return {
            "server_url": emby_notifier.server_url,
            "connected": True,
            "libraries": libraries
        }
    except Exception as e:
        return {
            "server_url": emby_notifier.server_url,
            "connected": False,
            "error": str(e)
        }

@app.post("/emby/refresh/library/{library_id}")
async def refresh_emby_library(library_id: str):
    """刷新指定的 Emby 媒体库"""
    if not emby_notifier:
        raise HTTPException(status_code=500, detail="Emby 通知器未初始化")
    try:
        result = emby_notifier._refresh_library(library_id)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新媒体库失败: {str(e)}")

@app.get("/system/info")
async def get_system_info():
    """获取系统信息"""
    if not health_checker:
        raise HTTPException(status_code=500, detail="健康检查器未初始化")
    return {
        "cpu_usage": health_checker.check_cpu_usage(),
        "memory_usage": health_checker.check_memory_usage(),
        "disk_usage": health_checker.check_disk_usage(),
        "mount_status": health_checker.check_mount_point(),
        "database_status": health_checker.check_database()
    }

@app.get("/symlink/recent")
async def get_recent_symlinks(limit: int = 50):
    """获取最近处理的软链接记录"""
    if not symlink_manager:
        raise HTTPException(status_code=500, detail="软链接管理器未初始化")
    try:
        recent_files = symlink_manager.get_recent_files(limit)
        return {"files": recent_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最近记录失败: {str(e)}")

def signal_handler(signum, frame):
    """处理系统信号"""
    logger.info(f"接收到信号: {signum}")
    cleanup_services()
    logger.info("程序退出")
    sys.exit(0)

if __name__ == '__main__':
    # 设置日志
    logger = setup_logging()
    logger.info("启动软链接管理系统")
    
    try:
        # 初始化服务
        init_services()
        
        # 注册信号处理
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 启动 FastAPI 服务
        uvicorn.run(app, host="127.0.0.1", port=8000)
        
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        cleanup_services()
        sys.exit(1) 