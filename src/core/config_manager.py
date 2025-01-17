"""
配置管理模块

负责统一管理所有配置项，包括:
1. 加载和解析配置文件
2. 配置项验证
3. 环境变量覆盖
4. 配置热重载
"""

import os
import re
import yaml
import logging
from typing import Any, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器"""
    
    # 配置项验证规则
    VALIDATION_RULES = {
        'google_drive.folder_id': {'type': str, 'required': True},
        'google_drive.api_key': {'type': str, 'required': True},
        'google_drive.api_call_interval': {'type': int, 'min': 60, 'max': 86400},
        'local_monitor.mount_point': {'type': str, 'required': True},
        'local_monitor.polling_interval': {'type': int, 'min': 30, 'max': 3600},
        'symlink.target_base': {'type': str, 'required': True},
        'symlink.video_extensions': {'type': list},
        'emby.server_url': {'type': str, 'required': True},
        'emby.api_key': {'type': str, 'required': True},
        'database.path': {'type': str, 'required': True},
        'database.backup_count': {'type': int, 'min': 1, 'max': 100},
        'logging.path': {'type': str, 'required': True},
        'logging.level': {'type': str, 'enum': ['DEBUG', 'INFO', 'WARNING', 'ERROR']},
        'logging.max_size': {'type': int, 'min': 1048576},  # 最小1MB
        'health_check.interval': {'type': int, 'min': 60, 'max': 3600},
        'task_queue.max_workers': {'type': int, 'min': 1, 'max': 16}
    }
    
    # 环境变量映射
    ENV_MAPPING = {
        'GOOGLE_DRIVE_FOLDER_ID': 'google_drive.folder_id',
        'GOOGLE_DRIVE_API_KEY': 'google_drive.api_key',
        'MOUNT_POINT': 'local_monitor.mount_point',
        'SYMLINK_TARGET': 'symlink.target_base',
        'EMBY_SERVER_URL': 'emby.server_url',
        'EMBY_API_KEY': 'emby.api_key',
        'LOG_LEVEL': 'logging.level',
        'DB_PATH': 'database.path'
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为环境变量或 config/config.yaml
        """
        self.config_path = config_path or os.getenv('CONFIG_PATH', 'config/config.yaml')
        self.config: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            # 如果配置文件不存在，创建默认配置
            if not os.path.exists(self.config_path):
                self.create_default_config()
            
            # 读取配置文件
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            # 使用环境变量覆盖配置
            self._override_from_env()
            
            # 验证配置
            self._validate_config()
            
            logger.info("配置加载完成")
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            raise
    
    def create_default_config(self):
        """创建默认配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self._get_default_config(), f, allow_unicode=True)
            logger.info(f"创建默认配置文件: {self.config_path}")
        except Exception as e:
            logger.error(f"创建默认配置文件失败: {e}")
            raise
    
    def _get_default_config(self) -> Dict:
        """获取默认配置
        
        Returns:
            Dict: 默认配置字典
        """
        return {
            'google_drive': {
                'folder_id': '',
                'api_key': '',
                'api_call_interval': 3600,
                'credentials_path': 'config/credentials.json',
                'token_path': 'config/token.json'
            },
            'local_monitor': {
                'mount_point': '/media/mount',
                'polling_interval': 300,
                'watch_patterns': ['*'],
                'ignore_patterns': ['.git/*', '*.tmp']
            },
            'symlink': {
                'target_base': '/media/links',
                'overwrite_existing': False,
                'video_extensions': [
                    '.mp4', '.mkv', '.ts', '.iso', '.rmvb', '.avi',
                    '.mov', '.mpeg', '.mpg', '.wmv', '.3gp', '.asf',
                    '.m4v', '.flv', '.m2ts', '.strm', '.tp', '.f4v'
                ]
            },
            'emby': {
                'server_url': 'http://localhost:8096',
                'api_key': '',
                'retry_count': 3,
                'retry_interval': 5
            },
            'database': {
                'path': 'config/database.db',
                'backup_count': 5,
                'backup_interval': 86400,
                'vacuum_threshold': 104857600
            },
            'logging': {
                'path': '/var/log/symlink',
                'level': 'INFO',
                'max_size': 10485760,
                'backup_count': 5,
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'snapshot': {
                'template_dir': 'templates',
                'output_dir': 'snapshots',
                'max_snapshots': 10
            },
            'health_check': {
                'interval': 300,
                'timeout': 30,
                'disk_usage_threshold': 90,
                'memory_usage_threshold': 90,
                'cpu_usage_threshold': 90
            },
            'task_queue': {
                'max_workers': 4,
                'max_retries': 3,
                'retry_delay': 5,
                'batch_size': 100
            }
        }
    
    def _override_from_env(self):
        """使用环境变量覆盖配置"""
        for env_var, config_path in self.ENV_MAPPING.items():
            value = os.getenv(env_var)
            if value is not None:
                self.set(config_path, self._convert_value(value, config_path))
    
    def _convert_value(self, value: str, config_path: str) -> Any:
        """转换配置值类型
        
        Args:
            value: 配置值
            config_path: 配置路径
            
        Returns:
            Any: 转换后的配置值
        """
        if config_path not in self.VALIDATION_RULES:
            return value
            
        rule = self.VALIDATION_RULES[config_path]
        if rule['type'] == bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        elif rule['type'] == int:
            return int(value)
        elif rule['type'] == float:
            return float(value)
        elif rule['type'] == list:
            return value.split(',')
        return value
    
    def _validate_config(self):
        """验证配置项"""
        for path, rule in self.VALIDATION_RULES.items():
            value = self.get(path)
            
            # 检查必需项
            if rule.get('required', False) and not value:
                raise ValueError(f"配置项 {path} 为必填项")
            
            # 如果值为空且非必需，跳过后续验证
            if not value and not rule.get('required', False):
                continue
            
            # 类型检查
            if not isinstance(value, rule['type']):
                raise TypeError(f"配置项 {path} 类型必须为 {rule['type'].__name__}")
            
            # 数值范围检查
            if isinstance(value, (int, float)):
                if 'min' in rule and value < rule['min']:
                    raise ValueError(f"配置项 {path} 不能小于 {rule['min']}")
                if 'max' in rule and value > rule['max']:
                    raise ValueError(f"配置项 {path} 不能大于 {rule['max']}")
            
            # 枚举值检查
            if 'enum' in rule and value not in rule['enum']:
                raise ValueError(f"配置项 {path} 必须是以下值之一: {', '.join(rule['enum'])}")
    
    def get(self, path: str, default: Any = None) -> Any:
        """获取配置项
        
        Args:
            path: 配置路径，使用点号分隔，如 'google_drive.folder_id'
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        try:
            value = self.config
            for key in path.split('.'):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, path: str, value: Any):
        """设置配置项
        
        Args:
            path: 配置路径，使用点号分隔，如 'google_drive.folder_id'
            value: 配置值
        """
        keys = path.split('.')
        current = self.config
        
        # 遍历到最后一个键之前
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # 设置最后一个键的值
        current[keys[-1]] = value
    
    def save(self):
        """保存配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self.config, f, allow_unicode=True)
            logger.info("配置保存完成")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            raise
    
    def reload(self):
        """重新加载配置"""
        self.load_config()
        logger.info("配置重新加载完成")


# 创建全局配置管理器实例
config_manager = ConfigManager() 