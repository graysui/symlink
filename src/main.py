"""
主程序入口

负责启动和管理整个系统，包括：
1. 初始化配置
2. 设置日志
3. 启动本地监控
4. 启动 Google Drive 监控
5. 启动健康检查
6. 处理系统信号
"""

import os
import sys
import signal
import logging
from pathlib import Path

from core.config_manager import config_manager
from core.log_manager import LogManager
from core.local_monitor import LocalMonitor
from core.gdrive_api import GoogleDriveAPI
from core.health_checker import HealthChecker

def setup_logging():
    """初始化日志设置"""
    log_manager = LogManager()
    log_manager.setup_logging()
    return log_manager.get_logger(__name__)

def signal_handler(signum, frame):
    """处理系统信号"""
    logger = logging.getLogger(__name__)
    logger.info(f"接收到信号: {signum}")
    
    if hasattr(signal_handler, 'monitor'):
        logger.info("正在停止本地监控...")
        signal_handler.monitor.stop()
    
    if hasattr(signal_handler, 'gdrive_monitor'):
        logger.info("正在停止 Google Drive 监控...")
        signal_handler.gdrive_monitor.stop()
        
    if hasattr(signal_handler, 'health_checker'):
        logger.info("正在停止健康检查...")
        signal_handler.health_checker.stop()
    
    logger.info("程序退出")
    sys.exit(0)

def main():
    """主程序入口"""
    # 初始化配置
    config = config_manager
    
    # 设置日志
    logger = setup_logging()
    logger.info("启动软链接管理系统")
    
    try:
        # 创建本地监控器
        monitor = LocalMonitor()
        signal_handler.monitor = monitor
        
        # 创建 Google Drive 监控器
        gdrive_monitor = None
        if config.get('google_drive.enabled'):
            try:
                gdrive_monitor = GoogleDriveAPI()
                signal_handler.gdrive_monitor = gdrive_monitor
                gdrive_monitor.start()
                logger.info("启动 Google Drive 监控")
            except Exception as e:
                logger.warning(f"Google Drive 监控启动失败: {e}")
        
        # 创建健康检查器
        health_checker = HealthChecker()
        signal_handler.health_checker = health_checker
        
        # 注册信号处理
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 启动监控和健康检查
        monitor.start()
        health_checker.start()
        logger.info("启动健康检查")
        
        # 保持程序运行
        signal.pause()
        
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 