"""
任务队列模块

负责管理异步任务，包括:
1. 任务调度和执行
2. 任务优先级管理
3. 失败重试机制
4. 任务状态追踪
"""

import os
import time
import logging
from typing import Any, Callable, Dict, List, Optional
from queue import PriorityQueue
from threading import Thread, Event, Lock
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from .config_manager import config_manager

logger = logging.getLogger(__name__)

class Task:
    """任务类"""
    
    def __init__(self, func: Callable, args: tuple = None, kwargs: dict = None,
                 priority: int = 0, retry_count: int = 0):
        """初始化任务
        
        Args:
            func: 任务函数
            args: 位置参数
            kwargs: 关键字参数
            priority: 优先级（数字越小优先级越高）
            retry_count: 当前重试次数
        """
        self.func = func
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.priority = priority
        self.retry_count = retry_count
        self.created_time = datetime.now()
        self.start_time = None
        self.end_time = None
        self.status = 'pending'  # pending, running, completed, failed
        self.result = None
        self.error = None
    
    def __lt__(self, other):
        """优先级比较"""
        return self.priority < other.priority

class TaskQueue:
    """任务队列管理器"""
    
    def __init__(self):
        """初始化任务队列管理器"""
        # 获取配置
        self.max_workers = config_manager.get('task_queue.max_workers')
        self.max_retries = config_manager.get('task_queue.max_retries')
        self.retry_delay = config_manager.get('task_queue.retry_delay')
        self.batch_size = config_manager.get('task_queue.batch_size')
        
        # 初始化队列和线程池
        self.queue = PriorityQueue()
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # 初始化状态追踪
        self.tasks: Dict[str, Task] = {}
        self.task_lock = Lock()
        
        # 初始化停止事件
        self.stop_event = Event()
        
        # 启动处理线程
        self.processing_thread = Thread(target=self._process_queue)
        self.processing_thread.start()
    
    def add_task(self, func: Callable, *args, priority: int = 0, **kwargs) -> str:
        """添加任务
        
        Args:
            func: 任务函数
            *args: 位置参数
            priority: 优先级
            **kwargs: 关键字参数
            
        Returns:
            str: 任务ID
        """
        try:
            # 创建任务
            task = Task(func, args, kwargs, priority)
            task_id = str(id(task))
            
            # 记录任务
            with self.task_lock:
                self.tasks[task_id] = task
            
            # 添加到队列
            self.queue.put((priority, task))
            logger.debug(f"添加任务: {task_id}")
            
            return task_id
            
        except Exception as e:
            logger.error(f"添加任务失败: {e}")
            raise
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[Dict]: 任务状态信息
        """
        with self.task_lock:
            task = self.tasks.get(task_id)
            if not task:
                return None
            
            return {
                'status': task.status,
                'created_time': task.created_time,
                'start_time': task.start_time,
                'end_time': task.end_time,
                'retry_count': task.retry_count,
                'result': task.result,
                'error': str(task.error) if task.error else None
            }
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否取消成功
        """
        with self.task_lock:
            task = self.tasks.get(task_id)
            if not task or task.status != 'pending':
                return False
            
            task.status = 'cancelled'
            return True
    
    def _process_queue(self):
        """处理任务队列"""
        while not self.stop_event.is_set():
            try:
                # 获取任务
                _, task = self.queue.get(timeout=1)
                
                # 如果任务已取消，跳过
                if task.status == 'cancelled':
                    continue
                
                # 更新任务状态
                task.status = 'running'
                task.start_time = datetime.now()
                
                try:
                    # 执行任务
                    future = self.executor.submit(task.func, *task.args, **task.kwargs)
                    task.result = future.result()
                    task.status = 'completed'
                    
                except Exception as e:
                    task.error = e
                    logger.error(f"任务执行失败: {e}")
                    
                    # 检查是否需要重试
                    if task.retry_count < self.max_retries:
                        task.retry_count += 1
                        task.status = 'pending'
                        # 延迟重试
                        time.sleep(self.retry_delay)
                        self.queue.put((task.priority, task))
                        logger.info(f"任务重试 ({task.retry_count}/{self.max_retries})")
                    else:
                        task.status = 'failed'
                
                finally:
                    task.end_time = datetime.now()
                    self.queue.task_done()
                
            except Exception as e:
                logger.error(f"处理任务队列失败: {e}")
    
    def stop(self):
        """停止任务队列"""
        try:
            # 设置停止标志
            self.stop_event.set()
            
            # 等待处理线程结束
            self.processing_thread.join()
            
            # 关闭线程池
            self.executor.shutdown(wait=True)
            
            logger.info("停止任务队列")
            
        except Exception as e:
            logger.error(f"停止任务队列失败: {e}")
            raise
    
    def cleanup_old_tasks(self, max_age: int = 86400):
        """清理旧任务记录
        
        Args:
            max_age: 最大保留时间（秒）
        """
        try:
            current_time = datetime.now()
            with self.task_lock:
                # 清理已完成或失败的旧任务
                expired = [
                    task_id for task_id, task in self.tasks.items()
                    if task.status in ('completed', 'failed', 'cancelled') and
                    (current_time - task.end_time).total_seconds() > max_age
                ]
                
                for task_id in expired:
                    del self.tasks[task_id]
                
                if expired:
                    logger.debug(f"清理 {len(expired)} 个过期任务")
                    
        except Exception as e:
            logger.error(f"清理旧任务失败: {e}")
            raise 