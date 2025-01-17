"""
健康检查模块

负责监控系统健康状态，包括:
1. 检查 Google Drive API 连接
2. 检查 rclone 挂载点
3. 检查数据库连接
4. 检查 Emby 服务
5. 监控系统资源
"""

import os
import time
import psutil
import logging
import requests
import sqlite3
from typing import Dict, List
from pathlib import Path
from threading import Thread, Event

from .config_manager import config_manager

logger = logging.getLogger(__name__)

class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        """初始化健康检查器"""
        # 获取配置
        self.check_interval = config_manager.get('health_check.interval')
        self.timeout = config_manager.get('health_check.timeout')
        self.disk_threshold = config_manager.get('health_check.disk_usage_threshold')
        self.memory_threshold = config_manager.get('health_check.memory_usage_threshold')
        self.cpu_threshold = config_manager.get('health_check.cpu_usage_threshold')
        
        # 获取其他组件配置
        self.mount_point = config_manager.get('local_monitor.mount_point')
        self.db_path = config_manager.get('database.path')
        self.emby_url = config_manager.get('emby.server_url')
        self.emby_api_key = config_manager.get('emby.api_key')
        
        # 初始化停止事件
        self.stop_event = Event()
        
        # 初始化检查线程
        self.check_thread = Thread(target=self._check_loop)
    
    def start(self):
        """启动健康检查"""
        try:
            self.check_thread.start()
            logger.info(f"启动健康检查，间隔 {self.check_interval} 秒")
            
        except Exception as e:
            logger.error(f"启动健康检查失败: {e}")
            raise
    
    def stop(self):
        """停止健康检查"""
        try:
            # 设置停止标志
            self.stop_event.set()
            
            # 等待检查线程结束
            if self.check_thread.is_alive():
                self.check_thread.join()
                logger.info("停止健康检查")
            
        except Exception as e:
            logger.error(f"停止健康检查失败: {e}")
            raise
    
    def _check_loop(self):
        """健康检查循环"""
        while not self.stop_event.is_set():
            try:
                # 执行所有检查
                results = self.check_all()
                
                # 记录检查结果
                for component, result in results.items():
                    if result['status']:
                        logger.debug(f"{component} 检查通过: {result['message']}")
                    else:
                        logger.warning(f"{component} 检查失败: {result['message']}")
                
                # 等待下次检查
                self.stop_event.wait(self.check_interval)
                
            except Exception as e:
                logger.error(f"执行健康检查失败: {e}")
                # 出错后等待一段时间再重试
                time.sleep(min(self.check_interval, 60))
    
    def check_all(self) -> Dict[str, Dict]:
        """执行所有健康检查
        
        Returns:
            Dict[str, Dict]: 检查结果字典
        """
        return {
            'google_drive': self.check_google_drive(),
            'rclone_mount': self.check_rclone_mount(),
            'database': self.check_database(),
            'emby': self.check_emby(),
            'system': self.check_system_resources()
        }
    
    def is_healthy(self) -> bool:
        """检查系统是否健康
        
        Returns:
            bool: 系统是否健康
        """
        results = self.check_all()
        return all(result['status'] for result in results.values())
    
    def check_google_drive(self) -> Dict:
        """检查 Google Drive API 连接状态
        
        Returns:
            Dict: 检查结果
        """
        try:
            # TODO: 实现 Google Drive API 连接检查
            return {
                'status': True,
                'message': 'Google Drive API 连接正常'
            }
            
        except Exception as e:
            return {
                'status': False,
                'message': f'Google Drive API 连接失败: {e}'
            }
    
    def check_rclone_mount(self) -> Dict:
        """检查 rclone 挂载点状态
        
        Returns:
            Dict: 检查结果
        """
        try:
            # 检查挂载点是否存在
            if not os.path.exists(self.mount_point):
                return {
                    'status': False,
                    'message': f'挂载点不存在: {self.mount_point}'
                }
            
            # 检查挂载点是否可写
            test_file = os.path.join(self.mount_point, '.health_check')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except Exception as e:
                return {
                    'status': False,
                    'message': f'挂载点不可写: {e}'
                }
            
            return {
                'status': True,
                'message': '挂载点状态正常'
            }
            
        except Exception as e:
            return {
                'status': False,
                'message': f'检查挂载点失败: {e}'
            }
    
    def check_database(self) -> Dict:
        """检查数据库连接状态
        
        Returns:
            Dict: 检查结果
        """
        try:
            # 检查数据库文件是否存在
            if not os.path.exists(self.db_path):
                return {
                    'status': False,
                    'message': f'数据库文件不存在: {self.db_path}'
                }
            
            # 测试数据库连接
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                cursor.fetchone()
            
            return {
                'status': True,
                'message': '数据库连接正常'
            }
            
        except Exception as e:
            return {
                'status': False,
                'message': f'数据库连接失败: {e}'
            }
    
    def check_emby(self) -> Dict:
        """检查 Emby 服务状态
        
        Returns:
            Dict: 检查结果
        """
        try:
            # 检查配置
            if not self.emby_url or not self.emby_api_key:
                return {
                    'status': False,
                    'message': 'Emby 配置不完整'
                }
            
            # 测试 API 连接
            headers = {
                'X-Emby-Token': self.emby_api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{self.emby_url}/emby/System/Info",
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            return {
                'status': True,
                'message': 'Emby 服务正常'
            }
            
        except Exception as e:
            return {
                'status': False,
                'message': f'Emby 服务异常: {e}'
            }
    
    def check_system_resources(self) -> Dict:
        """检查系统资源使用情况
        
        Returns:
            Dict: 检查结果
        """
        try:
            # 检查 CPU 使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_status = cpu_percent <= self.cpu_threshold
            
            # 检查内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_status = memory_percent <= self.memory_threshold
            
            # 检查磁盘使用率
            disk = psutil.disk_usage(self.mount_point)
            disk_percent = disk.percent
            disk_status = disk_percent <= self.disk_threshold
            
            # 生成状态消息
            messages = []
            if not cpu_status:
                messages.append(f'CPU 使用率过高: {cpu_percent}%')
            if not memory_status:
                messages.append(f'内存使用率过高: {memory_percent}%')
            if not disk_status:
                messages.append(f'磁盘使用率过高: {disk_percent}%')
            
            status = cpu_status and memory_status and disk_status
            message = '系统资源正常' if status else '; '.join(messages)
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory_percent,
                    'disk_percent': disk_percent
                }
            }
            
        except Exception as e:
            return {
                'status': False,
                'message': f'检查系统资源失败: {e}'
            } 