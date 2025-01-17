"""
日志管理器单元测试
"""

import os
import logging
import pytest
from pathlib import Path

from src.core.log_manager import LogManager


def test_log_manager_init(test_env):
    """测试日志管理器初始化"""
    log_dir = test_env['log_dir']
    manager = LogManager()
    
    assert manager.log_path == str(log_dir)
    assert manager.log_level == logging.DEBUG
    assert manager.max_size == 1024 * 1024  # 1MB
    assert manager.backup_count == 2


def test_get_log_level(test_env):
    """测试获取日志级别"""
    manager = LogManager()
    
    # 测试不同的日志级别
    test_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    for level_str, level_num in test_levels.items():
        os.environ['LOG_LEVEL'] = level_str
        manager.reload()
        assert manager.log_level == level_num


def test_parse_size(test_env):
    """测试解析文件大小字符串"""
    manager = LogManager()
    
    # 测试不同的大小单位
    test_sizes = {
        '1B': 1,
        '1KB': 1024,
        '1MB': 1024 * 1024,
        '1GB': 1024 * 1024 * 1024,
        '1.5MB': int(1.5 * 1024 * 1024)
    }
    
    for size_str, expected_bytes in test_sizes.items():
        assert manager._parse_size(size_str) == expected_bytes


def test_setup_logging(test_env):
    """测试设置日志记录器"""
    log_dir = test_env['log_dir']
    manager = LogManager()
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    
    # 检查日志级别
    assert root_logger.level == manager.log_level
    
    # 检查处理器
    assert len(root_logger.handlers) == 2  # 控制台处理器和文件处理器
    
    # 检查文件处理器
    file_handler = next(h for h in root_logger.handlers if isinstance(h, logging.FileHandler))
    assert file_handler.baseFilename == str(Path(log_dir) / 'symlink.log')


def test_get_logger(test_env):
    """测试获取日志记录器"""
    manager = LogManager()
    
    # 测试获取命名日志记录器
    logger = manager.get_logger('test')
    assert isinstance(logger, logging.Logger)
    assert logger.name == 'test'
    
    # 测试获取根日志记录器
    root_logger = manager.get_logger()
    assert isinstance(root_logger, logging.Logger)
    assert root_logger.name == 'root'


def test_set_level(test_env):
    """测试设置日志级别"""
    manager = LogManager()
    
    # 测试设置不同的日志级别
    test_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    
    for level in test_levels:
        manager.set_level(level)
        root_logger = logging.getLogger()
        assert root_logger.level == getattr(logging, level)
        
        # 检查所有处理器的级别
        for handler in root_logger.handlers:
            assert handler.level == getattr(logging, level)
    
    # 测试无效的日志级别
    with pytest.raises(ValueError):
        manager.set_level('INVALID_LEVEL')


def test_log_output(test_env):
    """测试日志输出"""
    log_dir = test_env['log_dir']
    log_file = Path(log_dir) / 'symlink.log'
    
    manager = LogManager()
    logger = manager.get_logger('test')
    
    # 测试不同级别的日志
    test_messages = {
        'debug': 'Debug message',
        'info': 'Info message',
        'warning': 'Warning message',
        'error': 'Error message',
        'critical': 'Critical message'
    }
    
    for level, message in test_messages.items():
        getattr(logger, level)(message)
    
    # 检查日志文件内容
    assert log_file.exists()
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
        for message in test_messages.values():
            assert message in content


def test_log_rotation(test_env):
    """测试日志轮转"""
    log_dir = test_env['log_dir']
    log_file = Path(log_dir) / 'symlink.log'
    
    # 创建一个小的最大大小以触发轮转
    os.environ['LOG_MAX_SIZE'] = '100B'
    manager = LogManager()
    logger = manager.get_logger('test')
    
    # 写入足够多的日志以触发轮转
    for i in range(100):
        logger.info('A' * 10)
    
    # 检查是否创建了备份文件
    log_files = list(Path(log_dir).glob('symlink.log*'))
    assert len(log_files) > 1
    assert len(log_files) <= manager.backup_count + 1


def test_reload(test_env):
    """测试重新加载日志配置"""
    log_dir = test_env['log_dir']
    manager = LogManager()
    
    # 修改环境变量
    os.environ['LOG_LEVEL'] = 'ERROR'
    os.environ['LOG_PATH'] = str(Path(log_dir) / 'new')
    
    # 重新加载配置
    manager.reload()
    
    # 检查配置是否更新
    assert manager.log_level == logging.ERROR
    assert manager.log_path == str(Path(log_dir) / 'new') 