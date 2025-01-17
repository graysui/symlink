"""
配置管理器单元测试
"""

import os
import yaml
import pytest
from pathlib import Path

from src.core.config_manager import ConfigManager


def test_config_manager_init(test_env):
    """测试配置管理器初始化"""
    config_path = test_env['config_path']
    manager = ConfigManager(str(config_path))
    
    assert manager.config_path == str(config_path)
    assert isinstance(manager.config, dict)


def test_create_default_config(test_env):
    """测试创建默认配置"""
    config_path = test_env['config_path']
    manager = ConfigManager(str(config_path))
    
    # 检查配置文件是否存在
    assert Path(config_path).exists()
    
    # 检查配置内容
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    assert 'monitoring' in config
    assert 'google_drive' in config['monitoring']
    assert 'local' in config['monitoring']
    assert 'emby' in config
    assert 'database' in config
    assert 'logging' in config


def test_load_config(test_env):
    """测试加载配置"""
    config_path = test_env['config_path']
    test_config = test_env['test_config']
    
    # 写入测试配置
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(test_config, f)
    
    manager = ConfigManager(str(config_path))
    assert manager.config == test_config


def test_override_from_env(test_env):
    """测试环境变量覆盖配置"""
    config_path = test_env['config_path']
    
    # 设置环境变量
    os.environ['GOOGLE_DRIVE_FOLDER_ID'] = 'env_folder_id'
    os.environ['API_CALL_INTERVAL'] = '120'
    os.environ['EMBY_SERVER_URL'] = 'http://env-server:8096'
    
    manager = ConfigManager(str(config_path))
    
    # 检查环境变量是否正确覆盖配置
    assert manager.get('monitoring.google_drive.folder_id') == 'env_folder_id'
    assert manager.get('monitoring.google_drive.api_call_interval') == '120'
    assert manager.get('emby.server_url') == 'http://env-server:8096'


def test_get_config(test_env):
    """测试获取配置项"""
    config_path = test_env['config_path']
    test_config = test_env['test_config']
    
    # 写入测试配置
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(test_config, f)
    
    manager = ConfigManager(str(config_path))
    
    # 测试获取存在的配置项
    assert manager.get('monitoring.google_drive.folder_id') == 'test_folder_id'
    assert manager.get('monitoring.local.polling_interval') == 30
    
    # 测试获取不存在的配置项
    assert manager.get('not.exist') is None
    assert manager.get('not.exist', 'default') == 'default'


def test_set_config(test_env):
    """测试设置配置项"""
    config_path = test_env['config_path']
    manager = ConfigManager(str(config_path))
    
    # 设置配置项
    manager.set('monitoring.google_drive.folder_id', 'new_folder_id')
    manager.set('new.key', 'new_value')
    
    # 检查内存中的配置
    assert manager.get('monitoring.google_drive.folder_id') == 'new_folder_id'
    assert manager.get('new.key') == 'new_value'
    
    # 检查配置文件
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    assert config['monitoring']['google_drive']['folder_id'] == 'new_folder_id'
    assert config['new']['key'] == 'new_value'


def test_reload_config(test_env):
    """测试重新加载配置"""
    config_path = test_env['config_path']
    test_config = test_env['test_config']
    
    # 写入初始配置
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(test_config, f)
    
    manager = ConfigManager(str(config_path))
    initial_folder_id = manager.get('monitoring.google_drive.folder_id')
    
    # 修改配置文件
    test_config['monitoring']['google_drive']['folder_id'] = 'modified_folder_id'
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(test_config, f)
    
    # 重新加载配置
    manager.reload()
    
    # 检查配置是否更新
    assert manager.get('monitoring.google_drive.folder_id') == 'modified_folder_id'
    assert manager.get('monitoring.google_drive.folder_id') != initial_folder_id 