"""
健康检查器单元测试
"""

import os
import sqlite3
import requests
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.core.health_checker import HealthChecker


@pytest.fixture
def health_checker(test_env):
    """创建健康检查器实例"""
    return HealthChecker()


def test_health_checker_init(test_env, health_checker):
    """测试健康检查器初始化"""
    db_dir = test_env['db_dir']
    db_path = Path(db_dir) / 'symlink.db'
    
    assert health_checker.db_path == str(db_path)
    assert health_checker.emby_url == 'http://localhost:8096'
    assert health_checker.emby_api_key == 'test_api_key'


@patch('src.core.health_checker.logger')
def test_check_google_drive(mock_logger, health_checker):
    """测试 Google Drive API 检查"""
    # TODO: 等 Google Drive API 模块完成后实现更详细的测试
    status, message = health_checker.check_google_drive()
    assert status is True
    assert 'healthy' in message.lower()


def test_check_rclone_mount(test_env, health_checker):
    """测试 rclone 挂载点检查"""
    mount_dir = test_env['mount_dir']
    
    # 测试挂载点不存在的情况
    status, message = health_checker.check_rclone_mount()
    assert status is False
    assert 'not configured' in message.lower()
    
    # 测试挂载点存在但不可写的情况
    with patch('pathlib.Path.touch', side_effect=PermissionError):
        status, message = health_checker.check_rclone_mount()
        assert status is False
        assert 'not writable' in message.lower()
    
    # 测试挂载点正常的情况
    with patch('pathlib.Path.touch'), patch('pathlib.Path.unlink'):
        status, message = health_checker.check_rclone_mount()
        assert status is True
        assert 'accessible' in message.lower()


def test_check_database(test_env, health_checker):
    """测试数据库检查"""
    db_dir = test_env['db_dir']
    db_path = Path(db_dir) / 'symlink.db'
    
    # 测试数据库不存在的情况
    if db_path.exists():
        db_path.unlink()
    status, message = health_checker.check_database()
    assert status is False
    assert 'not exist' in message.lower()
    
    # 测试数据库正常的情况
    conn = sqlite3.connect(db_path)
    conn.close()
    status, message = health_checker.check_database()
    assert status is True
    assert 'healthy' in message.lower()
    
    # 测试数据库损坏的情况
    with patch('sqlite3.connect', side_effect=sqlite3.Error):
        status, message = health_checker.check_database()
        assert status is False
        assert 'failed' in message.lower()


@patch('requests.get')
def test_check_emby(mock_get, health_checker):
    """测试 Emby 服务检查"""
    # 测试配置缺失的情况
    health_checker.emby_url = ''
    health_checker.emby_api_key = ''
    status, message = health_checker.check_emby()
    assert status is False
    assert 'missing' in message.lower()
    
    # 恢复配置
    health_checker.emby_url = 'http://localhost:8096'
    health_checker.emby_api_key = 'test_api_key'
    
    # 测试服务正常的情况
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    status, message = health_checker.check_emby()
    assert status is True
    assert 'available' in message.lower()
    
    # 验证请求头
    mock_get.assert_called_with(
        'http://localhost:8096/System/Info',
        headers={
            'X-Emby-Token': 'test_api_key',
            'Accept': 'application/json'
        }
    )
    
    # 测试服务不可用的情况
    mock_get.side_effect = requests.exceptions.RequestException
    status, message = health_checker.check_emby()
    assert status is False
    assert 'not available' in message.lower()


@patch('psutil.cpu_percent')
@patch('psutil.virtual_memory')
@patch('psutil.disk_usage')
def test_check_system_resources(mock_disk, mock_memory, mock_cpu, health_checker):
    """测试系统资源检查"""
    # 模拟正常的资源使用情况
    mock_cpu.return_value = 50.0
    
    mock_memory = MagicMock()
    mock_memory.percent = 60.0
    
    mock_disk = MagicMock()
    mock_disk.percent = 70.0
    
    results = health_checker.check_system_resources()
    assert len(results) == 3  # CPU, 内存, 磁盘
    
    for status, message in results:
        assert status is True
        assert 'normal' in message.lower()
    
    # 模拟资源使用过高的情况
    mock_cpu.return_value = 95.0
    mock_memory.percent = 92.0
    mock_disk.percent = 91.0
    
    results = health_checker.check_system_resources()
    for status, message in results:
        assert status is False
        assert 'high' in message.lower()


def test_check_all(health_checker):
    """测试全面健康检查"""
    # 使用补丁模拟所有检查都成功的情况
    with patch.multiple(
        health_checker,
        check_google_drive=MagicMock(return_value=(True, 'OK')),
        check_rclone_mount=MagicMock(return_value=(True, 'OK')),
        check_database=MagicMock(return_value=(True, 'OK')),
        check_emby=MagicMock(return_value=(True, 'OK')),
        check_system_resources=MagicMock(return_value=[
            (True, 'CPU OK'),
            (True, 'Memory OK'),
            (True, 'Disk OK')
        ])
    ):
        results = health_checker.check_all()
        assert all(status for status, _ in results.values())
    
    # 模拟部分检查失败的情况
    with patch.multiple(
        health_checker,
        check_google_drive=MagicMock(return_value=(False, 'Failed')),
        check_rclone_mount=MagicMock(return_value=(True, 'OK')),
        check_database=MagicMock(return_value=(False, 'Failed')),
        check_emby=MagicMock(return_value=(True, 'OK')),
        check_system_resources=MagicMock(return_value=[
            (True, 'CPU OK'),
            (False, 'Memory High'),
            (True, 'Disk OK')
        ])
    ):
        results = health_checker.check_all()
        assert not all(status for status, _ in results.values())


def test_is_healthy(health_checker):
    """测试系统健康状态检查"""
    # 模拟系统健康的情况
    with patch.object(
        health_checker,
        'check_all',
        return_value={
            'test1': (True, 'OK'),
            'test2': (True, 'OK')
        }
    ):
        assert health_checker.is_healthy() is True
    
    # 模拟系统不健康的情况
    with patch.object(
        health_checker,
        'check_all',
        return_value={
            'test1': (True, 'OK'),
            'test2': (False, 'Failed')
        }
    ):
        assert health_checker.is_healthy() is False 