"""
初始化模块

负责系统初始化，包括:
1. 创建必要的目录结构
2. 初始化数据库
3. 执行首次全量扫描
4. 生成软链接
"""

import os
import time
import logging
from typing import Dict, List, Set
from pathlib import Path
from threading import Lock

from .config_manager import config_manager
from .db_manager import DatabaseManager

logger = logging.getLogger(__name__)

class Initializer:
    """初始化器"""
    
    # 支持的视频文件格式
    VIDEO_EXTENSIONS = {
        '.mp4', '.mkv', '.ts', '.iso', '.rmvb', '.avi',
        '.mov', '.mpeg', '.mpg', '.wmv', '.3gp', '.asf',
        '.m4v', '.flv', '.m2ts', '.strm', '.tp', '.f4v'
    }
    
    def __init__(self):
        """初始化初始化器"""
        # 获取配置
        self.mount_point = config_manager.get('local_monitor.mount_point')
        self.target_base = config_manager.get('symlink.target_base')
        self.log_path = config_manager.get('logging.path')
        self.overwrite_existing = config_manager.get('symlink.overwrite_existing')
        
        # 初始化数据库管理器
        self.db = DatabaseManager()
        
        # 初始化锁
        self.lock = Lock()
    
    def initialize(self) -> bool:
        """执行初始化
        
        Returns:
            bool: 是否初始化成功
        """
        try:
            logger.info("开始系统初始化")
            
            # 创建必要的目录
            self._create_directories()
            
            # 初始化数据库
            self.db.init_database()
            
            # 执行全量扫描
            self._scan_directory_tree()
            
            # 创建软链接
            self._create_symlinks_from_db()
            
            logger.info("系统初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"系统初始化失败: {e}")
            return False
    
    def _create_directories(self):
        """创建必要的目录结构"""
        try:
            # 创建挂载点目录
            os.makedirs(self.mount_point, exist_ok=True)
            logger.info(f"创建挂载点目录: {self.mount_point}")
            
            # 创建软链接目标目录
            os.makedirs(self.target_base, exist_ok=True)
            logger.info(f"创建软链接目标目录: {self.target_base}")
            
            # 创建日志目录
            os.makedirs(self.log_path, exist_ok=True)
            logger.info(f"创建日志目录: {self.log_path}")
            
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            raise
    
    def _scan_directory_tree(self):
        """扫描目录树并存储到数据库"""
        try:
            logger.info(f"开始扫描目录: {self.mount_point}")
            start_time = time.time()
            
            # 遍历目录树
            for entry in self._walk_directory(self.mount_point):
                path = entry['path']
                is_directory = entry['is_directory']
                
                if is_directory:
                    # 记录目录
                    self.db.add_file(
                        path=path,
                        size=0,
                        modified_time=int(os.path.getmtime(path)),
                        is_directory=True,
                        parent_path=str(Path(path).parent)
                    )
                else:
                    # 记录文件
                    self.db.add_file(
                        path=path,
                        size=os.path.getsize(path),
                        modified_time=int(os.path.getmtime(path)),
                        is_directory=False,
                        parent_path=str(Path(path).parent)
                    )
            
            duration = time.time() - start_time
            logger.info(f"目录扫描完成，耗时 {duration:.2f} 秒")
            
        except Exception as e:
            logger.error(f"扫描目录树失败: {e}")
            raise
    
    def _walk_directory(self, directory: str) -> List[Dict]:
        """遍历目录树
        
        Args:
            directory: 目录路径
            
        Yields:
            Dict: 包含文件信息的字典
        """
        try:
            for root, dirs, files in os.walk(directory):
                # 记录目录
                for dir_name in dirs:
                    path = os.path.join(root, dir_name)
                    yield {
                        'path': path,
                        'is_directory': True
                    }
                
                # 记录文件
                for file_name in files:
                    path = os.path.join(root, file_name)
                    yield {
                        'path': path,
                        'is_directory': False
                    }
                    
        except Exception as e:
            logger.error(f"遍历目录失败 {directory}: {e}")
            raise
    
    def _is_video_file(self, path: str) -> bool:
        """检查是否是视频文件
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 是否是视频文件
        """
        return Path(path).suffix.lower() in self.VIDEO_EXTENSIONS
    
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
    
    def _create_symlinks_from_db(self):
        """从数据库创建软链接"""
        try:
            logger.info("开始创建软链接")
            start_time = time.time()
            
            # 获取所有非目录文件
            files = self.db.list_files(is_directory=False)
            
            # 创建软链接
            created_count = 0
            skipped_count = 0
            
            for file in files:
                path = file['path']
                
                # 检查是否应该处理
                if not self._should_process(path):
                    continue
                
                # 构建目标路径
                rel_path = os.path.relpath(path, self.mount_point)
                target_path = os.path.join(self.target_base, rel_path)
                target_dir = os.path.dirname(target_path)
                
                try:
                    # 确保目标目录存在
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # 检查目标是否已存在
                    if os.path.exists(target_path):
                        if not self.overwrite_existing:
                            skipped_count += 1
                            continue
                        os.remove(target_path)
                    
                    # 创建软链接
                    os.symlink(path, target_path)
                    created_count += 1
                    
                except Exception as e:
                    logger.error(f"创建软链接失败 {path}: {e}")
            
            duration = time.time() - start_time
            logger.info(f"软链接创建完成，创建 {created_count} 个，跳过 {skipped_count} 个，耗时 {duration:.2f} 秒")
            
        except Exception as e:
            logger.error(f"从数据库创建软链接失败: {e}")
            raise 