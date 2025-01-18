"""
Emby 通知模块

负责通知 Emby 刷新媒体库，包括:
1. 获取媒体库信息
2. 精确刷新指定目录
3. 处理刷新响应
"""

import os
import time
import logging
import requests
from typing import Dict, List, Optional
from pathlib import Path

from .config_manager import config_manager

logger = logging.getLogger(__name__)

class EmbyNotifier:
    """Emby 通知器"""
    
    def __init__(self):
        """初始化 Emby 通知器"""
        self.server_url = config_manager.get('emby.server_url')
        self.api_key = config_manager.get('emby.api_key')
        self.retry_count = config_manager.get('emby.retry_count')
        self.retry_interval = config_manager.get('emby.retry_interval')
        
        if not self.server_url or not self.api_key:
            logger.warning("Emby 配置不完整")
    
    def _get_headers(self) -> Dict:
        """获取请求头"""
        return {
            'X-Emby-Token': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """发送请求到 Emby 服务器"""
        url = f"{self.server_url}/emby{endpoint}"
        headers = self._get_headers()
        
        for attempt in range(self.retry_count):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    timeout=30,
                    **kwargs
                )
                response.raise_for_status()
                return response.json() if response.content else {}
                
            except requests.exceptions.RequestException as e:
                if attempt < self.retry_count - 1:
                    logger.warning(f"请求失败，将在 {self.retry_interval} 秒后重试: {e}")
                    time.sleep(self.retry_interval)
                else:
                    logger.error(f"请求失败，已达到最大重试次数: {e}")
                    raise
    
    def _get_libraries(self) -> List[Dict]:
        """获取媒体库列表"""
        try:
            response = self._make_request('GET', '/Library/VirtualFolders')
            return response
        except Exception as e:
            logger.error(f"获取媒体库列表失败: {e}")
            return []
    
    def _refresh_library(self, library_id: str) -> Dict:
        """刷新指定媒体库"""
        try:
            response = self._make_request(
                'POST',
                f'/Library/VirtualFolders/Refresh?id={library_id}'
            )
            return {'status': 'success', 'library_id': library_id}
        except Exception as e:
            logger.error(f"刷新媒体库失败: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def refresh_library(self, path: str) -> Dict:
        """刷新指定路径的媒体库"""
        try:
            # 获取所有媒体库
            libraries = self._get_libraries()
            
            # 找到包含指定路径的媒体库
            target_library = None
            for library in libraries:
                if path.startswith(library.get('Path', '')):
                    target_library = library
                    break
            
            if not target_library:
                return {
                    'status': 'error',
                    'message': f'未找到包含路径 {path} 的媒体库'
                }
            
            # 刷新找到的媒体库
            return self._refresh_library(target_library['Id'])
            
        except Exception as e:
            logger.error(f"刷新媒体库失败: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def refresh_all(self) -> Dict:
        """刷新所有媒体库"""
        try:
            libraries = self._get_libraries()
            results = []
            
            for library in libraries:
                result = self._refresh_library(library['Id'])
                results.append({
                    'library': library['Name'],
                    'result': result
                })
            
            return {
                'status': 'success',
                'results': results
            }
            
        except Exception as e:
            logger.error(f"刷新所有媒体库失败: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def check_connection(self) -> Dict:
        """检查与 Emby 服务器的连接"""
        try:
            if not self.server_url or not self.api_key:
                return {
                    'status': False,
                    'message': 'Emby 配置不完整'
                }
            
            response = self._make_request('GET', '/System/Info')
            return {
                'status': True,
                'server_name': response.get('ServerName', 'Unknown'),
                'version': response.get('Version', 'Unknown'),
                'operating_system': response.get('OperatingSystem', 'Unknown')
            }
            
        except Exception as e:
            return {
                'status': False,
                'message': str(e)
            } 