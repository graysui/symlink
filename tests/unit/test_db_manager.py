"""
数据库管理器单元测试
"""

import os
import sqlite3
import time
from pathlib import Path

import pytest

from src.core.db_manager import DatabaseManager


@pytest.fixture
def db_manager(test_env):
    """创建数据库管理器实例"""
    return DatabaseManager()


def test_db_manager_init(test_env, db_manager):
    """测试数据库管理器初始化"""
    db_dir = test_env['db_dir']
    db_path = Path(db_dir) / 'symlink.db'
    
    assert db_manager.db_path == str(db_path)
    assert db_manager.backup_interval == 3600
    assert db_manager.backup_count == 3
    assert db_path.exists()


def test_init_database(test_env, db_manager):
    """测试数据库初始化"""
    # 检查表是否创建
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        
        # 检查文件表
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='files'
        ''')
        assert cursor.fetchone() is not None
        
        # 检查软链接表
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='symlinks'
        ''')
        assert cursor.fetchone() is not None
        
        # 检查索引
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='index' AND sql IS NOT NULL
        ''')
        indexes = [row[0] for row in cursor.fetchall()]
        assert 'idx_files_path' in indexes
        assert 'idx_files_parent' in indexes
        assert 'idx_symlinks_source' in indexes


def test_backup_database(test_env, db_manager):
    """测试数据库备份"""
    db_dir = test_env['db_dir']
    
    # 创建一些测试数据
    db_manager.add_file('/test/file1.txt', 100, int(time.time()), False)
    
    # 执行备份
    db_manager.backup_database()
    
    # 检查备份文件
    backup_dir = Path(db_dir) / 'backup'
    backup_files = list(backup_dir.glob('symlink_*.db'))
    assert len(backup_files) == 1
    
    # 检查备份文件内容
    with sqlite3.connect(backup_files[0]) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT path FROM files WHERE path = ?', ('/test/file1.txt',))
        assert cursor.fetchone() is not None


def test_add_file(test_env, db_manager):
    """测试添加文件记录"""
    # 添加目录
    dir_time = int(time.time())
    dir_id = db_manager.add_file('/test', 0, dir_time, True)
    
    # 添加文件
    file_time = int(time.time())
    file_id = db_manager.add_file('/test/file1.txt', 100, file_time, False, '/test')
    
    # 检查记录
    file_record = db_manager.get_file('/test/file1.txt')
    assert file_record is not None
    assert file_record['path'] == '/test/file1.txt'
    assert file_record['size'] == 100
    assert file_record['modified_time'] == file_time
    assert file_record['is_directory'] is False
    assert file_record['parent_id'] == dir_id


def test_add_symlink(test_env, db_manager):
    """测试添加软链接记录"""
    # 添加源文件
    source_time = int(time.time())
    db_manager.add_file('/source/file1.txt', 100, source_time, False)
    
    # 添加软链接
    symlink_id = db_manager.add_symlink('/source/file1.txt', '/target/file1.txt')
    
    # 检查记录
    symlink_record = db_manager.get_symlink('/target/file1.txt')
    assert symlink_record is not None
    assert symlink_record['target_path'] == '/target/file1.txt'
    assert symlink_record['source_path'] == '/source/file1.txt'
    
    # 测试添加不存在的源文件
    with pytest.raises(ValueError):
        db_manager.add_symlink('/not/exist.txt', '/target/not_exist.txt')


def test_get_file(test_env, db_manager):
    """测试获取文件记录"""
    # 添加文件
    file_time = int(time.time())
    db_manager.add_file('/test/file1.txt', 100, file_time, False)
    
    # 获取存在的文件
    file_record = db_manager.get_file('/test/file1.txt')
    assert file_record is not None
    assert file_record['path'] == '/test/file1.txt'
    
    # 获取不存在的文件
    assert db_manager.get_file('/not/exist.txt') is None


def test_get_symlink(test_env, db_manager):
    """测试获取软链接记录"""
    # 添加源文件和软链接
    source_time = int(time.time())
    db_manager.add_file('/source/file1.txt', 100, source_time, False)
    db_manager.add_symlink('/source/file1.txt', '/target/file1.txt')
    
    # 获取存在的软链接
    symlink_record = db_manager.get_symlink('/target/file1.txt')
    assert symlink_record is not None
    assert symlink_record['target_path'] == '/target/file1.txt'
    assert symlink_record['source_path'] == '/source/file1.txt'
    
    # 获取不存在的软链接
    assert db_manager.get_symlink('/target/not_exist.txt') is None


def test_list_files(test_env, db_manager):
    """测试列出文件记录"""
    # 添加测试数据
    dir_time = int(time.time())
    db_manager.add_file('/test', 0, dir_time, True)
    db_manager.add_file('/test/file1.txt', 100, dir_time, False, '/test')
    db_manager.add_file('/test/file2.txt', 200, dir_time, False, '/test')
    
    # 列出所有文件
    all_files = db_manager.list_files()
    assert len(all_files) == 3
    
    # 列出特定目录的文件
    dir_files = db_manager.list_files('/test')
    assert len(dir_files) == 2
    assert all(file['parent_id'] is not None for file in dir_files)


def test_list_symlinks(test_env, db_manager):
    """测试列出软链接记录"""
    # 添加测试数据
    source_time = int(time.time())
    db_manager.add_file('/source/file1.txt', 100, source_time, False)
    db_manager.add_file('/source/file2.txt', 200, source_time, False)
    db_manager.add_symlink('/source/file1.txt', '/target/file1.txt')
    db_manager.add_symlink('/source/file2.txt', '/target/file2.txt')
    
    # 列出所有软链接
    all_symlinks = db_manager.list_symlinks()
    assert len(all_symlinks) == 2
    
    # 列出特定源文件的软链接
    file_symlinks = db_manager.list_symlinks('/source/file1.txt')
    assert len(file_symlinks) == 1
    assert file_symlinks[0]['source_path'] == '/source/file1.txt'


def test_delete_file(test_env, db_manager):
    """测试删除文件记录"""
    # 添加文件
    file_time = int(time.time())
    db_manager.add_file('/test/file1.txt', 100, file_time, False)
    
    # 删除存在的文件
    assert db_manager.delete_file('/test/file1.txt') is True
    assert db_manager.get_file('/test/file1.txt') is None
    
    # 删除不存在的文件
    assert db_manager.delete_file('/not/exist.txt') is False


def test_delete_symlink(test_env, db_manager):
    """测试删除软链接记录"""
    # 添加源文件和软链接
    source_time = int(time.time())
    db_manager.add_file('/source/file1.txt', 100, source_time, False)
    db_manager.add_symlink('/source/file1.txt', '/target/file1.txt')
    
    # 删除存在的软链接
    assert db_manager.delete_symlink('/target/file1.txt') is True
    assert db_manager.get_symlink('/target/file1.txt') is None
    
    # 删除不存在的软链接
    assert db_manager.delete_symlink('/target/not_exist.txt') is False


def test_vacuum(test_env, db_manager):
    """测试数据库压缩"""
    # 添加和删除一些数据以产生碎片
    for i in range(100):
        file_time = int(time.time())
        path = f'/test/file{i}.txt'
        db_manager.add_file(path, 100, file_time, False)
        db_manager.delete_file(path)
    
    # 获取压缩前的文件大小
    db_path = Path(db_manager.db_path)
    size_before = db_path.stat().st_size
    
    # 执行压缩
    db_manager.vacuum()
    
    # 获取压缩后的文件大小
    size_after = db_path.stat().st_size
    
    # 压缩后的文件应该更小
    assert size_after < size_before 