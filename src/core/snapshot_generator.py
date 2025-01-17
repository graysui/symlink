"""
快照生成模块

负责生成目录结构快照，包括:
1. 从数据库读取目录结构
2. 构建目录树
3. 生成 HTML 快照
"""

import os
import json
import logging
from typing import Dict, List
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from .config_manager import config_manager
from .db_manager import DatabaseManager

logger = logging.getLogger(__name__)

class SnapshotGenerator:
    """快照生成器"""
    
    def __init__(self):
        """初始化快照生成器"""
        # 获取配置
        self.template_dir = config_manager.get('snapshot.template_dir')
        self.output_dir = config_manager.get('snapshot.output_dir')
        self.max_snapshots = config_manager.get('snapshot.max_snapshots')
        
        # 初始化数据库管理器
        self.db = DatabaseManager()
        
        # 初始化 Jinja2 环境
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=True
        )
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _build_directory_tree(self) -> Dict:
        """构建目录树
        
        Returns:
            Dict: 目录树字典
        """
        try:
            # 获取所有文件记录
            files = self.db.list_files()
            
            # 构建目录树
            root = {'name': '', 'type': 'dir', 'children': {}}
            
            for file in files:
                path = file['path']
                is_directory = file['is_directory']
                size = file['size']
                modified_time = file['modified_time']
                
                # 分割路径
                parts = Path(path).parts
                
                # 从根开始遍历
                current = root
                for i, part in enumerate(parts):
                    # 如果是最后一个部分
                    if i == len(parts) - 1:
                        # 添加文件或目录
                        current['children'][part] = {
                            'name': part,
                            'type': 'dir' if is_directory else 'file',
                            'size': size,
                            'modified_time': modified_time,
                            'children': {} if is_directory else None
                        }
                    else:
                        # 如果目录不存在，创建它
                        if part not in current['children']:
                            current['children'][part] = {
                                'name': part,
                                'type': 'dir',
                                'size': 0,
                                'modified_time': 0,
                                'children': {}
                            }
                        current = current['children'][part]
            
            return root
            
        except Exception as e:
            logger.error(f"构建目录树失败: {e}")
            raise
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小
        
        Args:
            size: 文件大小（字节）
            
        Returns:
            str: 格式化后的大小字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    def generate_snapshot(self, title: str = None) -> bool:
        """生成快照
        
        Args:
            title: 快照标题，默认使用时间戳
            
        Returns:
            bool: 是否生成成功
        """
        try:
            # 构建目录树
            tree = self._build_directory_tree()
            
            # 计算统计信息
            total_dirs = 0
            total_files = 0
            total_size = 0
            
            def count_items(node):
                nonlocal total_dirs, total_files, total_size
                for child in node['children'].values():
                    if child['type'] == 'dir':
                        total_dirs += 1
                        count_items(child)
                    else:
                        total_files += 1
                        total_size += child['size']
            
            count_items(tree)
            
            # 准备模板数据
            data = {
                'title': title or f"目录快照 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                'generated_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_dirs': total_dirs,
                'total_files': total_files,
                'total_size': self._format_size(total_size),
                'tree': json.dumps(tree)
            }
            
            # 生成快照文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(self.output_dir, f"snapshot_{timestamp}.html")
            
            # 渲染模板
            template = self.jinja_env.get_template('snap2html.jinja2')
            html = template.render(**data)
            
            # 写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)
            
            logger.info(f"生成快照文件: {output_file}")
            
            # 清理旧快照
            self._cleanup_old_snapshots()
            
            return True
            
        except Exception as e:
            logger.error(f"生成快照失败: {e}")
            return False
    
    def _cleanup_old_snapshots(self):
        """清理旧的快照文件"""
        try:
            # 获取所有快照文件
            snapshots = sorted([
                f for f in os.listdir(self.output_dir)
                if f.startswith('snapshot_') and f.endswith('.html')
            ])
            
            # 如果超过最大数量，删除旧的快照
            while len(snapshots) > self.max_snapshots:
                file_to_delete = os.path.join(self.output_dir, snapshots.pop(0))
                os.remove(file_to_delete)
                logger.info(f"删除旧快照: {file_to_delete}")
                
        except Exception as e:
            logger.error(f"清理旧快照失败: {e}")
            raise 