"""
Pytest 配置文件

提供测试环境设置和通用 fixtures
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def temp_dir():
    """创建临时目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")
def config_file(temp_dir):
    """创建测试配置文件"""
    config_dir = Path(temp_dir) / 'config'
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / 'config.yaml'
    
    # 创建测试配置
    test_config = {
        'monitoring': {
            'google_drive': {
                'folder_id': 'test_folder_id',
                'api_call_interval': 60
            },
            'local': {
                'polling_interval': 30,
                'mount_point': str(Path(temp_dir) / 'mount')
            }
        },
        'emby': {
            'server_url': 'http://localhost:8096',
            'api_key': 'test_api_key'
        },
        'database': {
            'path': str(Path(temp_dir) / 'data/db/symlink.db'),
            'backup_interval': 3600,
            'backup_count': 3
        },
        'logging': {
            'path': str(Path(temp_dir) / 'data/logs'),
            'level': 'DEBUG',
            'max_size': '1MB',
            'backup_count': 2
        }
    }
    
    yield config_file, test_config


@pytest.fixture(scope="function")
def test_env(temp_dir, config_file):
    """设置测试环境"""
    config_path, test_config = config_file
    
    # 创建必要的目录
    data_dir = Path(temp_dir) / 'data'
    log_dir = data_dir / 'logs'
    db_dir = data_dir / 'db'
    mount_dir = Path(temp_dir) / 'mount'
    
    for directory in [log_dir, db_dir, mount_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    
    # 设置环境变量
    os.environ['CONFIG_PATH'] = str(config_path)
    os.environ['DATABASE_PATH'] = str(db_dir / 'symlink.db')
    os.environ['LOG_PATH'] = str(log_dir)
    os.environ['GOOGLE_DRIVE_FOLDER_ID'] = 'test_folder_id'
    os.environ['EMBY_SERVER_URL'] = 'http://localhost:8096'
    os.environ['EMBY_API_KEY'] = 'test_api_key'
    
    yield {
        'temp_dir': temp_dir,
        'config_path': config_path,
        'test_config': test_config,
        'data_dir': data_dir,
        'log_dir': log_dir,
        'db_dir': db_dir,
        'mount_dir': mount_dir
    }
    
    # 清理环境变量
    for key in ['CONFIG_PATH', 'DATABASE_PATH', 'LOG_PATH',
                'GOOGLE_DRIVE_FOLDER_ID', 'EMBY_SERVER_URL', 'EMBY_API_KEY']:
        os.environ.pop(key, None) 