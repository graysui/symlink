"""
日志管理模块

负责统一的日志记录和管理，包括:
1. 分级日志记录
2. 日志文件轮转
3. 日志格式化输出
4. 日志聚合发送
"""

import os
import logging
import logging.handlers
from pathlib import Path
from typing import Optional, Union

from .config_manager import config_manager

class LogManager:
    """日志管理器"""
    
    def __init__(self):
        """初始化日志管理器"""
        # 获取配置
        self.log_path = config_manager.get('logging.path')
        self.log_level = self._parse_log_level(config_manager.get('logging.level'))
        self.max_size = self._parse_size(config_manager.get('logging.max_size'))
        self.backup_count = config_manager.get('logging.backup_count')
        self.log_format = config_manager.get('logging.format', 
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        
        # 初始化根日志器
        self._setup_logging()
    
    def _parse_log_level(self, level: str) -> int:
        """解析日志级别
        
        Args:
            level: 日志级别字符串
            
        Returns:
            int: 日志级别数值
        """
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return level_map.get(level.upper(), logging.INFO)
    
    def _parse_size(self, size: Union[int, str]) -> int:
        """解析文件大小
        
        Args:
            size: 大小，可以是整数（字节）或字符串（如 "10MB"）
            
        Returns:
            int: 字节数
        """
        # 如果是整数，直接返回
        if isinstance(size, int):
            return size
            
        # 如果是字符串，解析单位
        if isinstance(size, str):
            units = {
                'B': 1,
                'KB': 1024,
                'MB': 1024 * 1024,
                'GB': 1024 * 1024 * 1024
            }
            
            size_upper = size.upper()
            for unit, multiplier in units.items():
                if size_upper.endswith(unit):
                    try:
                        number = float(size_upper[:-len(unit)])
                        return int(number * multiplier)
                    except ValueError:
                        break
        
        # 默认返回 10MB
        return 10 * 1024 * 1024
    
    def _setup_logging(self):
        """设置日志配置"""
        # 获取根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # 清除现有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 创建格式化器
        formatter = logging.Formatter(self.log_format)
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 添加文件处理器
        log_file = os.path.join(self.log_path, 'app.log')
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.max_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """获取日志器
        
        Args:
            name: 日志器名称，默认返回根日志器
            
        Returns:
            logging.Logger: 日志器实例
        """
        return logging.getLogger(name)
    
    def set_level(self, level: str):
        """设置日志级别
        
        Args:
            level: 日志级别
        """
        level_num = self._parse_log_level(level)
        logging.getLogger().setLevel(level_num)
    
    def reload(self):
        """重新加载日志配置"""
        try:
            # 重新获取配置
            self.log_level = self._parse_log_level(config_manager.get('logging.level'))
            self.max_size = self._parse_size(config_manager.get('logging.max_size'))
            self.backup_count = config_manager.get('logging.backup_count')
            self.log_format = config_manager.get('logging.format',
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            
            # 重新设置日志配置
            self._setup_logging()
            
        except Exception as e:
            logging.error(f"重新加载日志配置失败: {e}")
            raise

# 创建全局日志管理器实例
log_manager = LogManager() 