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
        # 获取配置
        self.server_url = config_manager.get('emby.server_url')
        self.api_key = config_manager.get('emby.api_key')
        self.retry_count = config_manager.get('emby.retry_count')
        self.retry_interval = config_manager.get('emby.retry_interval')
        
        # 构建请求头
        self.headers = {
            'X-Emby-Token': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def _get_libraries(self) -> List[Dict]:
        """获取媒体库列表
        
        Returns:
            List[Dict]: 媒体库列表
        """
        try:
            response = requests.get(
                f"{self.server_url}/emby/Library/VirtualFolders",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取媒体库列表失败: {e}")
            return []
    
    def _find_library_for_path(self, path: str) -> Optional[str]:
        """查找包含指定路径的媒体库
        
        Args:
            path: 文件路径
            
        Returns:
            Optional[str]: 媒体库 ID，未找到时返回 None
        """
        try:
            libraries = self._get_libraries()
            path = os.path.abspath(path)
            
            for library in libraries:
                for location in library.get('Locations', []):
                    if path.startswith(os.path.abspath(location)):
                        return library.get('ItemId')
            
            return None
            
        except Exception as e:
            logger.error(f"查找媒体库失败 {path}: {e}")
            return None
    
    def _refresh_library(self, library_id: str) -> bool:
        """刷新指定媒体库
        
        Args:
            library_id: 媒体库 ID
            
        Returns:
            bool: 是否刷新成功
        """
        for attempt in range(self.retry_count):
            try:
                response = requests.post(
                    f"{self.server_url}/emby/Library/VirtualFolders/Refresh",
                    params={'id': library_id},
                    headers=self.headers
                )
                response.raise_for_status()
                return True
                
            except Exception as e:
                if attempt < self.retry_count - 1:
                    logger.warning(f"刷新媒体库失败，将在 {self.retry_interval} 秒后重试: {e}")
                    time.sleep(self.retry_interval)
                else:
                    logger.error(f"刷新媒体库失败，已达到最大重试次数: {e}")
        
        return False
    
    def _refresh_item(self, item_id: str) -> bool:
        """刷新指定项目
        
        Args:
            item_id: 项目 ID
            
        Returns:
            bool: 是否刷新成功
        """
        for attempt in range(self.retry_count):
            try:
                response = requests.post(
                    f"{self.server_url}/emby/Items/{item_id}/Refresh",
                    headers=self.headers
                )
                response.raise_for_status()
                return True
                
            except Exception as e:
                if attempt < self.retry_count - 1:
                    logger.warning(f"刷新项目失败，将在 {self.retry_interval} 秒后重试: {e}")
                    time.sleep(self.retry_interval)
                else:
                    logger.error(f"刷新项目失败，已达到最大重试次数: {e}")
        
        return False
    
    def refresh_multiple(self, paths: List[str]) -> Dict[str, bool]:
        """批量刷新多个路径
        
        Args:
            paths: 需要刷新的路径列表
            
        Returns:
            Dict[str, bool]: 刷新结果字典，键为路径，值为是否刷新成功
        """
        results = {}
        
        try:
            # 按媒体库分组路径
            libraries = {}
            for path in paths:
                library_id = self._find_library_for_path(path)
                if library_id:
                    if library_id not in libraries:
                        libraries[library_id] = []
                    libraries[library_id].append(path)
                else:
                    logger.warning(f"未找到包含路径的媒体库: {path}")
                    results[path] = False
            
            # 刷新每个媒体库
            for library_id, lib_paths in libraries.items():
                success = self._refresh_library(library_id)
                for path in lib_paths:
                    results[path] = success
            
            return results
            
        except Exception as e:
            logger.error(f"批量刷新失败: {e}")
            return {path: False for path in paths} 