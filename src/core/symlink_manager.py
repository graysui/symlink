"""
软链接管理模块

负责创建和管理软链接，包括:
1. 检查文件类型
2. 创建软链接
3. 通知 Emby 刷新
"""

import os
import logging
from pathlib import Path
from threading import Lock
from typing import Set

from .config_manager import config_manager
from .emby_notifier import EmbyNotifier

logger = logging.getLogger(__name__)

class SymlinkManager:
    """软链接管理器"""
    
    def __init__(self):
        """初始化软链接管理器"""
        # 获取配置
        self.target_base = config_manager.get('symlink.target_base')
        self.overwrite_existing = config_manager.get('symlink.overwrite_existing')
        self.video_extensions = set(config_manager.get('symlink.video_extensions'))
        
        # 确保目标目录存在
        os.makedirs(self.target_base, exist_ok=True)
        
        # 初始化 Emby 通知器
        self.emby = EmbyNotifier()
        
        # 初始化刷新目录集合和锁
        self.refresh_paths = set()
        self.refresh_lock = Lock()
    
    def _is_video_file(self, path: str) -> bool:
        """检查是否是视频文件
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 是否是视频文件
        """
        return Path(path).suffix.lower() in self.video_extensions
    
    def _should_process(self, path: str) -> bool:
        """检查是否应该处理该文件
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 是否应该处理
        """
        # 检查是否是视频文件
        if not self._is_video_file(path):
            return False
        
        # 检查是否在 BDMV 目录中
        if "BDMV" in Path(path).parts:
            return False
        
        return True
    
    def process_file(self, source_path: str) -> bool:
        """处理文件，如果是视频文件则创建软链接
        
        Args:
            source_path: 源文件路径
            
        Returns:
            bool: 是否处理成功
        """
        try:
            # 检查是否应该处理该文件
            if not self._should_process(source_path):
                logger.debug(f"跳过非视频文件或 BDMV 目录文件: {source_path}")
                return False
            
            # 创建软链接
            return self.create_symlink(source_path)
            
        except Exception as e:
            logger.error(f"处理文件失败 {source_path}: {e}")
            return False
    
    def create_symlink(self, source_path: str) -> bool:
        """创建软链接
        
        Args:
            source_path: 源文件路径
            
        Returns:
            bool: 是否创建成功
        """
        try:
            # 构建目标路径，保持原始目录结构
            rel_path = os.path.relpath(source_path, config_manager.get('local_monitor.mount_point'))
            target_path = os.path.join(self.target_base, rel_path)
            target_dir = os.path.dirname(target_path)
            
            # 确保目标目录存在
            os.makedirs(target_dir, exist_ok=True)
            
            # 如果目标已存在且不允许覆盖，则跳过
            if os.path.exists(target_path):
                if not self.overwrite_existing:
                    logger.info(f"目标已存在且不允许覆盖: {target_path}")
                    return False
                os.remove(target_path)
            
            # 创建软链接
            os.symlink(source_path, target_path)
            logger.info(f"创建软链接: {source_path} -> {target_path}")
            
            # 添加到刷新路径集合
            with self.refresh_lock:
                self.refresh_paths.add(target_path)
            
            return True
            
        except Exception as e:
            logger.error(f"创建软链接失败 {source_path}: {e}")
            return False
    
    def notify_emby(self):
        """通知 Emby 刷新媒体库"""
        with self.refresh_lock:
            if not self.refresh_paths:
                return
            
            try:
                # 获取需要刷新的路径
                paths_to_refresh = self.refresh_paths.copy()
                self.refresh_paths.clear()
                
                # 批量刷新
                results = self.emby.refresh_multiple(paths_to_refresh)
                
                # 记录刷新结果
                success_count = sum(1 for result in results.values() if result)
                logger.info(f"Emby 刷新完成: 成功 {success_count}/{len(paths_to_refresh)}")
                
            except Exception as e:
                logger.error(f"通知 Emby 刷新失败: {e}")
                # 如果刷新失败，将路径重新添加到集合中
                self.refresh_paths.update(paths_to_refresh)