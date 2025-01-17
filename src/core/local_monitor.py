"""
本地目录监控模块

负责监控本地目录文件变化，包括:
1. 实时监控文件系统事件
2. 定期轮询检查变化
3. 增量扫描目录
4. 缓存机制减少 I/O
"""

import os
import time
import logging
from typing import Dict, Set
from pathlib import Path
from threading import Thread, Event, Lock
from queue import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .config_manager import config_manager
from .db_manager import DatabaseManager
from .task_queue import TaskQueue

logger = logging.getLogger(__name__)

class FileEventHandler(FileSystemEventHandler):
    """文件事件处理器"""
    
    def __init__(self, monitor):
        """初始化事件处理器
        
        Args:
            monitor: LocalMonitor 实例
        """
        self.monitor = monitor
        self.processing_lock = Lock()
        self.processing_paths = set()
    
    def on_created(self, event: FileSystemEvent):
        """处理文件创建事件"""
        if not event.is_directory:
            self._process_event(event.src_path, 'created')
    
    def on_modified(self, event: FileSystemEvent):
        """处理文件修改事件"""
        if not event.is_directory:
            self._process_event(event.src_path, 'modified')
    
    def on_deleted(self, event: FileSystemEvent):
        """处理文件删除事件"""
        if not event.is_directory:
            self._process_event(event.src_path, 'deleted')
    
    def _process_event(self, path: str, event_type: str):
        """处理文件事件
        
        Args:
            path: 文件路径
            event_type: 事件类型
        """
        with self.processing_lock:
            # 检查是否已在处理中
            if path in self.processing_paths:
                return
            self.processing_paths.add(path)
        
        try:
            # 将事件添加到队列
            self.monitor.event_queue.put((path, event_type))
            logger.debug(f"添加事件到队列: {event_type} {path}")
            
        finally:
            with self.processing_lock:
                self.processing_paths.remove(path)

class LocalMonitor:
    """本地目录监控器"""
    
    def __init__(self):
        """初始化本地目录监控器"""
        # 获取配置
        self.mount_point = config_manager.get('local_monitor.mount_point')
        self.polling_interval = config_manager.get('local_monitor.polling_interval')
        self.watch_patterns = config_manager.get('local_monitor.watch_patterns')
        self.ignore_patterns = config_manager.get('local_monitor.ignore_patterns')
        
        # 确保监控目录存在
        os.makedirs(self.mount_point, exist_ok=True)
        
        # 初始化组件
        self.db = DatabaseManager()
        self.task_queue = TaskQueue()
        
        # 初始化事件队列和处理线程
        self.event_queue = Queue()
        self.stop_event = Event()
        self.processing_thread = Thread(target=self._process_events)
        
        # 初始化观察者
        self.event_handler = FileEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.mount_point, recursive=True)
        
        # 初始化轮询线程
        self.polling_thread = Thread(target=self._poll_changes)
        
        # 初始化缓存
        self.cache_lock = Lock()
        self.path_cache = {}  # 缓存文件信息
        self.last_check = {}  # 记录最后检查时间
    
    def start(self):
        """启动监控"""
        try:
            # 启动观察者
            self.observer.start()
            logger.info(f"启动文件系统监控: {self.mount_point}")
            
            # 启动处理线程
            self.processing_thread.start()
            logger.info("启动事件处理线程")
            
            # 启动轮询线程
            self.polling_thread.start()
            logger.info(f"启动轮询线程，间隔 {self.polling_interval} 秒")
            
        except Exception as e:
            logger.error(f"启动监控失败: {e}")
            self.stop()
            raise
    
    def stop(self):
        """停止监控"""
        try:
            # 设置停止标志
            self.stop_event.set()
            
            # 停止观察者
            if self.observer.is_alive():
                self.observer.stop()
                self.observer.join()
                logger.info("停止文件系统监控")
            
            # 停止处理线程
            if self.processing_thread.is_alive():
                self.event_queue.put(None)  # 发送停止信号
                self.processing_thread.join()
                logger.info("停止事件处理线程")
            
            # 停止轮询线程
            if self.polling_thread.is_alive():
                self.polling_thread.join()
                logger.info("停止轮询线程")
            
        except Exception as e:
            logger.error(f"停止监控失败: {e}")
            raise
    
    def _process_events(self):
        """处理事件队列"""
        while not self.stop_event.is_set():
            try:
                # 从队列获取事件
                event = self.event_queue.get()
                if event is None:  # 停止信号
                    break
                
                path, event_type = event
                
                # 处理事件
                if event_type == 'deleted':
                    self.db.delete_file(path)
                    logger.info(f"删除文件记录: {path}")
                else:
                    # 获取文件信息
                    try:
                        stat = os.stat(path)
                        size = stat.st_size
                        modified_time = int(stat.st_mtime)
                        
                        # 更新数据库
                        is_new = self.db.add_file(
                            path=path,
                            size=size,
                            modified_time=modified_time,
                            is_directory=False,
                            parent_path=str(Path(path).parent)
                        )
                        
                        if is_new:
                            # 添加到任务队列
                            from .symlink_manager import SymlinkManager
                            symlink_mgr = SymlinkManager()
                            self.task_queue.add_task(
                                symlink_mgr.process_file,
                                path,
                                priority=1 if event_type == 'created' else 2
                            )
                            logger.info(f"添加处理任务: {event_type} {path}")
                            
                    except FileNotFoundError:
                        logger.warning(f"文件不存在: {path}")
                    except Exception as e:
                        logger.error(f"处理文件失败 {path}: {e}")
                
            except Exception as e:
                logger.error(f"处理事件失败: {e}")
            
            finally:
                self.event_queue.task_done()
    
    def _poll_changes(self):
        """轮询检查文件变化"""
        while not self.stop_event.is_set():
            try:
                # 扫描目录
                self._scan_directory(self.mount_point)
                logger.debug(f"完成目录扫描: {self.mount_point}")
                
                # 等待下次轮询
                self.stop_event.wait(self.polling_interval)
                
            except Exception as e:
                logger.error(f"轮询检查失败: {e}")
                # 出错后等待一段时间再重试
                time.sleep(min(self.polling_interval, 60))
    
    def _scan_directory(self, directory: str):
        """扫描目录
        
        Args:
            directory: 目录路径
        """
        try:
            # 获取目录下的所有文件
            for root, _, files in os.walk(directory):
                for filename in files:
                    path = os.path.join(root, filename)
                    
                    try:
                        # 检查是否需要跳过
                        if any(Path(path).match(pattern) for pattern in self.ignore_patterns):
                            continue
                        
                        # 获取文件信息
                        stat = os.stat(path)
                        size = stat.st_size
                        modified_time = int(stat.st_mtime)
                        
                        # 检查缓存
                        with self.cache_lock:
                            cached = self.path_cache.get(path)
                            if cached and cached['modified_time'] == modified_time:
                                continue
                            
                            # 更新缓存
                            self.path_cache[path] = {
                                'size': size,
                                'modified_time': modified_time
                            }
                        
                        # 更新数据库
                        is_new = self.db.add_file(
                            path=path,
                            size=size,
                            modified_time=modified_time,
                            is_directory=False,
                            parent_path=str(Path(path).parent)
                        )
                        
                        if is_new:
                            # 添加到任务队列
                            from .symlink_manager import SymlinkManager
                            symlink_mgr = SymlinkManager()
                            self.task_queue.add_task(
                                symlink_mgr.process_file,
                                path,
                                priority=1  # 轮询发现的变化优先级较低
                            )
                            logger.info(f"添加处理任务: {path}")
                        
                    except FileNotFoundError:
                        logger.warning(f"文件不存在: {path}")
                    except Exception as e:
                        logger.error(f"处理文件失败 {path}: {e}")
            
            # 清理过期缓存
            self._cleanup_cache()
            
        except Exception as e:
            logger.error(f"扫描目录失败 {directory}: {e}")
    
    def _cleanup_cache(self, max_age: int = 3600):
        """清理过期缓存
        
        Args:
            max_age: 最大缓存时间（秒）
        """
        try:
            current_time = time.time()
            with self.cache_lock:
                # 清理过期的缓存项
                expired = [path for path, info in self.path_cache.items()
                          if current_time - info.get('modified_time', 0) > max_age]
                
                for path in expired:
                    del self.path_cache[path]
                
                if expired:
                    logger.debug(f"清理 {len(expired)} 个过期缓存项")
                    
        except Exception as e:
            logger.error(f"清理缓存失败: {e}") 