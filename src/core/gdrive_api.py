"""
Google Drive API 监控模块

负责监控 Google Drive 文件变化，包括:
1. 获取文件活动数据
2. 解析文件变化信息
3. 更新数据库记录
4. 通知软链接模块
"""

import os
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread, Event

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config_manager import config_manager
from .db_manager import DatabaseManager
from .symlink_manager import SymlinkManager

logger = logging.getLogger(__name__)

class GoogleDriveAPI:
    """Google Drive API 管理器"""
    
    def __init__(self):
        """初始化 Google Drive API 管理器"""
        # 获取配置
        self.folder_id = config_manager.get('google_drive.folder_id')
        self.api_call_interval = config_manager.get('google_drive.api_call_interval')
        self.credentials_path = config_manager.get('google_drive.credentials_path')
        self.token_path = config_manager.get('google_drive.token_path')
        
        # 初始化组件
        self.db = DatabaseManager()
        self.symlink_mgr = SymlinkManager()
        
        # 初始化认证
        self.credentials = self._get_credentials()
        
        # 初始化服务
        self.service = build('drive', 'v3', credentials=self.credentials)
        self.activity_service = build('driveactivity', 'v2', credentials=self.credentials)
        
        # 初始化停止事件
        self.stop_event = Event()
        
        # 记录上次检查时间
        self.last_check_time = datetime.utcnow()
    
    def _get_credentials(self) -> Credentials:
        """获取 Google Drive API 凭证
        
        Returns:
            Credentials: Google Drive API 凭证
        """
        creds = None
        
        # 尝试从文件加载凭证
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path)
        
        # 如果没有凭证或已过期
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # 从客户端配置文件创建凭证
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path,
                    ['https://www.googleapis.com/auth/drive.readonly',
                     'https://www.googleapis.com/auth/drive.activity.readonly']
                )
                creds = flow.run_local_server(port=0)
            
            # 保存凭证
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        return creds
    
    def start(self):
        """启动监控"""
        try:
            # 启动监控线程
            self.monitor_thread = Thread(target=self._monitor_changes)
            self.monitor_thread.start()
            logger.info(f"启动 Google Drive 监控，间隔 {self.api_call_interval} 秒")
            
        except Exception as e:
            logger.error(f"启动监控失败: {e}")
            raise
    
    def stop(self):
        """停止监控"""
        try:
            # 设置停止标志
            self.stop_event.set()
            
            # 等待线程结束
            if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
                self.monitor_thread.join()
                logger.info("停止 Google Drive 监控")
            
        except Exception as e:
            logger.error(f"停止监控失败: {e}")
            raise
    
    def _monitor_changes(self):
        """监控文件变化"""
        while not self.stop_event.is_set():
            try:
                # 获取文件活动
                activities = self._get_activities()
                
                # 处理文件变化
                for activity in activities:
                    self._process_activity(activity)
                
                # 更新检查时间
                self.last_check_time = datetime.utcnow()
                
                # 等待下次检查
                self.stop_event.wait(self.api_call_interval)
                
            except Exception as e:
                logger.error(f"监控文件变化失败: {e}")
                # 出错后等待一段时间再重试
                time.sleep(min(self.api_call_interval, 60))
    
    def _get_activities(self) -> List[Dict]:
        """获取文件活动
        
        Returns:
            List[Dict]: 文件活动列表
        """
        try:
            # 构建查询参数
            query = {
                'ancestorName': f'items/{self.folder_id}',
                'filter': f'time >= "{self.last_check_time.isoformat()}Z"'
            }
            
            # 获取活动列表
            response = self.activity_service.activity().query(body=query).execute()
            
            return response.get('activities', [])
            
        except Exception as e:
            logger.error(f"获取文件活动失败: {e}")
            return []
    
    def _process_activity(self, activity: Dict):
        """处理文件活动
        
        Args:
            activity: 文件活动信息
        """
        try:
            # 获取文件 ID
            targets = activity.get('targets', [])
            if not targets:
                return
            
            # 获取文件信息
            file_id = targets[0].get('driveItem', {}).get('name', '').split('/')[-1]
            if not file_id:
                return
            
            # 获取文件元数据
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, modifiedTime, parents'
            ).execute()
            
            # 构建文件路径
            path = self._get_file_path(file)
            if not path:
                return
            
            # 更新数据库
            is_new = self.db.add_file(
                path=path,
                size=int(file.get('size', 0)),
                modified_time=int(datetime.strptime(
                    file['modifiedTime'], '%Y-%m-%dT%H:%M:%S.%fZ'
                ).timestamp()),
                is_directory=file['mimeType'] == 'application/vnd.google-apps.folder',
                parent_path=str(Path(path).parent),
                drive_id=file['id']
            )
            
            if is_new:
                # 通知软链接模块
                self.symlink_mgr.process_file(path)
                logger.info(f"处理文件变化: {path}")
            
        except Exception as e:
            logger.error(f"处理文件活动失败: {e}")
    
    def _get_file_path(self, file: Dict) -> Optional[str]:
        """获取文件在本地的路径
        
        Args:
            file: 文件信息
            
        Returns:
            Optional[str]: 文件路径，获取失败时返回 None
        """
        try:
            # 获取文件路径部分
            path_parts = []
            current = file
            
            while current:
                # 如果是目标文件夹，停止
                if current['id'] == self.folder_id:
                    break
                
                path_parts.append(current['name'])
                
                # 获取父文件夹
                if 'parents' not in current:
                    break
                    
                parent_id = current['parents'][0]
                current = self.service.files().get(
                    fileId=parent_id,
                    fields='id, name, parents'
                ).execute()
            
            # 如果没有找到目标文件夹，返回 None
            if not path_parts:
                return None
            
            # 构建本地路径
            mount_point = config_manager.get('local_monitor.mount_point')
            path = os.path.join(mount_point, *reversed(path_parts))
            
            return path
            
        except Exception as e:
            logger.error(f"获取文件路径失败: {e}")
            return None 