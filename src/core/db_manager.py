"""
数据库管理模块

负责管理文件目录结构数据库，包括:
1. 初始化数据库结构
2. 记录文件信息
3. 对比文件变化
4. 支持快照功能
"""

import os
import logging
import sqlite3
from typing import Optional, Dict, List, Set, Tuple
from datetime import datetime
from pathlib import Path
from threading import Lock

from .config_manager import config_manager

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        """初始化数据库管理器"""
        # 获取配置
        self.db_path = config_manager.get('database.path')
        self.backup_count = config_manager.get('database.backup_count')
        self.backup_interval = config_manager.get('database.backup_interval')
        self.vacuum_threshold = config_manager.get('database.vacuum_threshold')
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 初始化锁
        self.db_lock = Lock()
        
        # 初始化数据库
        self.init_database()
        
        # 检查是否需要整理数据库
        self._check_vacuum_needed()
    
    def _check_vacuum_needed(self):
        """检查是否需要整理数据库"""
        try:
            if os.path.exists(self.db_path):
                size = os.path.getsize(self.db_path)
                if size > self.vacuum_threshold:
                    logger.info(f"数据库大小({size}字节)超过阈值({self.vacuum_threshold}字节)，开始整理")
                    self.vacuum_database()
        except Exception as e:
            logger.error(f"检查数据库大小失败: {e}")
    
    def vacuum_database(self):
        """整理数据库，回收未使用的空间"""
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("VACUUM")
                logger.info("数据库整理完成")
            except Exception as e:
                logger.error(f"数据库整理失败: {e}")
    
    def init_database(self):
        """初始化数据库结构"""
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # 创建文件表
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS files (
                            path TEXT PRIMARY KEY,
                            size INTEGER NOT NULL,
                            modified_time INTEGER NOT NULL,
                            is_directory BOOLEAN NOT NULL,
                            parent_path TEXT,
                            drive_id TEXT,  -- Google Drive 文件 ID
                            last_check INTEGER NOT NULL,  -- 最后检查时间
                            FOREIGN KEY (parent_path) REFERENCES files (path)
                        )
                    """)
                    
                    # 创建索引
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_parent_path 
                        ON files (parent_path)
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_drive_id 
                        ON files (drive_id)
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_last_check 
                        ON files (last_check)
                    """)
                    
                    conn.commit()
                    logger.info("数据库初始化完成")
                    
            except Exception as e:
                logger.error(f"初始化数据库失败: {e}")
                raise
    
    def add_file(self, path: str, size: int, modified_time: int, 
                 is_directory: bool, parent_path: Optional[str] = None,
                 drive_id: Optional[str] = None) -> bool:
        """添加或更新文件记录
        
        Args:
            path: 文件路径
            size: 文件大小（字节）
            modified_time: 修改时间（Unix时间戳）
            is_directory: 是否是目录
            parent_path: 父目录路径
            drive_id: Google Drive 文件 ID
            
        Returns:
            bool: 是否为新增或更新的记录
        """
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # 检查是否存在
                    cursor.execute(
                        "SELECT modified_time FROM files WHERE path = ?",
                        (path,)
                    )
                    result = cursor.fetchone()
                    
                    current_time = int(datetime.now().timestamp())
                    is_new_or_modified = True
                    
                    if result:
                        # 如果文件存在且修改时间相同，则不更新
                        if result[0] == modified_time:
                            cursor.execute(
                                "UPDATE files SET last_check = ? WHERE path = ?",
                                (current_time, path)
                            )
                            is_new_or_modified = False
                        else:
                            # 更新记录
                            cursor.execute("""
                                UPDATE files 
                                SET size = ?, modified_time = ?, is_directory = ?,
                                    parent_path = ?, drive_id = ?, last_check = ?
                                WHERE path = ?
                            """, (size, modified_time, is_directory, parent_path,
                                 drive_id, current_time, path))
                    else:
                        # 插入新记录
                        cursor.execute("""
                            INSERT INTO files (
                                path, size, modified_time, is_directory,
                                parent_path, drive_id, last_check
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (path, size, modified_time, is_directory, parent_path,
                              drive_id, current_time))
                    
                    conn.commit()
                    return is_new_or_modified
                    
            except Exception as e:
                logger.error(f"添加文件记录失败 {path}: {e}")
                return False
    
    def get_file(self, path: str) -> Optional[Dict]:
        """获取文件记录
        
        Args:
            path: 文件路径
            
        Returns:
            Optional[Dict]: 文件记录字典，不存在时返回 None
        """
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT * FROM files WHERE path = ?",
                        (path,)
                    )
                    result = cursor.fetchone()
                    
                    if result:
                        return {
                            'path': result[0],
                            'size': result[1],
                            'modified_time': result[2],
                            'is_directory': bool(result[3]),
                            'parent_path': result[4],
                            'drive_id': result[5],
                            'last_check': result[6]
                        }
                    return None
                    
            except Exception as e:
                logger.error(f"获取文件记录失败 {path}: {e}")
                return None
    
    def list_files(self, parent_path: Optional[str] = None,
                   is_directory: Optional[bool] = None) -> List[Dict]:
        """列出文件记录
        
        Args:
            parent_path: 父目录路径，None 表示列出所有记录
            is_directory: 是否只列出目录或文件
            
        Returns:
            List[Dict]: 文件记录列表
        """
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    query = "SELECT * FROM files"
                    params = []
                    conditions = []
                    
                    if parent_path is not None:
                        conditions.append("parent_path = ?")
                        params.append(parent_path)
                    
                    if is_directory is not None:
                        conditions.append("is_directory = ?")
                        params.append(is_directory)
                    
                    if conditions:
                        query += " WHERE " + " AND ".join(conditions)
                    
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    
                    return [{
                        'path': row[0],
                        'size': row[1],
                        'modified_time': row[2],
                        'is_directory': bool(row[3]),
                        'parent_path': row[4],
                        'drive_id': row[5],
                        'last_check': row[6]
                    } for row in results]
                    
            except Exception as e:
                logger.error(f"列出文件记录失败: {e}")
                return []
    
    def compare_files(self, current_files: List[Dict]) -> Tuple[List[Dict], List[Dict], List[str]]:
        """比较文件变化
        
        Args:
            current_files: 当前文件列表，每个文件包含 path, size, modified_time 信息
            
        Returns:
            Tuple[List[Dict], List[Dict], List[str]]: 
            (新增文件列表, 修改文件列表, 删除文件路径列表)
        """
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # 获取当前路径集合
                    current_paths = {f['path'] for f in current_files}
                    
                    # 获取数据库中的文件记录
                    cursor.execute("SELECT path, size, modified_time FROM files")
                    db_files = {row[0]: {'size': row[1], 'modified_time': row[2]} 
                              for row in cursor.fetchall()}
                    
                    # 找出新增、修改和删除的文件
                    new_files = []
                    modified_files = []
                    deleted_paths = []
                    
                    # 检查新增和修改的文件
                    for file in current_files:
                        path = file['path']
                        if path not in db_files:
                            new_files.append(file)
                        elif (file['size'] != db_files[path]['size'] or 
                              file['modified_time'] != db_files[path]['modified_time']):
                            modified_files.append(file)
                    
                    # 检查删除的文件
                    deleted_paths = [path for path in db_files 
                                   if path not in current_paths]
                    
                    return new_files, modified_files, deleted_paths
                    
            except Exception as e:
                logger.error(f"比较文件变化失败: {e}")
                return [], [], []
    
    def delete_file(self, path: str) -> bool:
        """删除文件记录
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 是否删除成功
        """
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM files WHERE path = ?",
                        (path,)
                    )
                    conn.commit()
                    return cursor.rowcount > 0
                    
            except Exception as e:
                logger.error(f"删除文件记录失败 {path}: {e}")
                return False
    
    def cleanup_old_records(self, max_age: int = 86400) -> int:
        """清理过期记录
        
        Args:
            max_age: 最大保留时间（秒）
            
        Returns:
            int: 清理的记录数量
        """
        with self.db_lock:
            try:
                current_time = int(datetime.now().timestamp())
                cutoff_time = current_time - max_age
                
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM files WHERE last_check < ?",
                        (cutoff_time,)
                    )
                    conn.commit()
                    return cursor.rowcount
                    
            except Exception as e:
                logger.error(f"清理过期记录失败: {e}")
                return 0
    
    def backup_database(self) -> bool:
        """备份数据库
        
        Returns:
            bool: 是否备份成功
        """
        try:
            # 生成备份文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{self.db_path}.{timestamp}.bak"
            
            # 复制数据库文件
            with open(self.db_path, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())
            
            # 清理旧备份
            backup_files = sorted([f for f in os.listdir(os.path.dirname(self.db_path))
                                 if f.startswith(os.path.basename(self.db_path)) 
                                 and f.endswith('.bak')])
            
            while len(backup_files) > self.backup_count:
                os.remove(os.path.join(os.path.dirname(self.db_path), backup_files.pop(0)))
            
            logger.info(f"数据库备份完成: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"备份数据库失败: {e}")
            return False 