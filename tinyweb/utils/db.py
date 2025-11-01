"""
数据库工具模块
用于管理用户数据的 SQLite 数据库操作
"""
import sqlite3
import os
import datetime
from typing import Optional, Dict, Any


class UserDB:
    """用户数据库管理类"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径，如果为 None 则使用默认路径
        """
        if db_path is None:
            # 默认数据库路径在 webui 目录下
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "users.db")
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                wallet_address TEXT PRIMARY KEY,
                nickname TEXT,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                login_count INTEGER DEFAULT 0
            )
        ''')
        
        # 创建索引提高查询性能
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_wallet_address 
            ON users(wallet_address)
        ''')
        
        conn.commit()
        conn.close()
    
    def get_user_by_address(self, address: str) -> Optional[Dict[str, Any]]:
        """
        根据钱包地址获取用户信息
        
        Args:
            address: 钱包地址
            
        Returns:
            用户信息字典，如果不存在返回 None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 返回字典格式
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM users WHERE wallet_address = ?',
            (address.lower(),)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'wallet_address': row['wallet_address'],
                'nickname': row['nickname'],
                'email': row['email'],
                'created_at': row['created_at'],
                'last_login': row['last_login'],
                'login_count': row['login_count']
            }
        return None
    
    def create_user(self, address: str) -> bool:
        """
        创建新用户（自动注册）
        
        Args:
            address: 钱包地址
            
        Returns:
            True 表示创建了新用户，False 表示用户已存在（更新了登录信息）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO users (wallet_address, login_count, last_login)
                VALUES (?, 1, CURRENT_TIMESTAMP)
            ''', (address.lower(),))
            conn.commit()
            is_new = True
        except sqlite3.IntegrityError:
            # 用户已存在，更新登录信息
            cursor.execute('''
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP, 
                    login_count = login_count + 1
                WHERE wallet_address = ?
            ''', (address.lower(),))
            conn.commit()
            is_new = False
        finally:
            conn.close()
        
        return is_new
    
    def update_user_info(self, address: str, nickname: Optional[str] = None, 
                         email: Optional[str] = None) -> bool:
        """
        更新用户信息（可选注册信息）
        
        Args:
            address: 钱包地址
            nickname: 昵称
            email: 邮箱
            
        Returns:
            是否成功更新
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if nickname is not None:
            updates.append('nickname = ?')
            params.append(nickname)
        if email is not None:
            updates.append('email = ?')
            params.append(email)
        
        if not updates:
            conn.close()
            return False
        
        params.append(address.lower())
        cursor.execute(
            f'UPDATE users SET {", ".join(updates)} WHERE wallet_address = ?',
            params
        )
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        
        return updated
    
    def get_all_users(self, limit: int = 100) -> list:
        """
        获取所有用户列表（用于管理）
        
        Args:
            limit: 返回数量限制
            
        Returns:
            用户列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM users ORDER BY created_at DESC LIMIT ?',
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'wallet_address': row['wallet_address'],
                'nickname': row['nickname'],
                'email': row['email'],
                'created_at': row['created_at'],
                'last_login': row['last_login'],
                'login_count': row['login_count']
            }
            for row in rows
        ]


# 全局数据库实例
_user_db_instance = None


def get_user_db() -> UserDB:
    """
    获取全局数据库实例（单例模式）
    
    Returns:
        UserDB 实例
    """
    global _user_db_instance
    if _user_db_instance is None:
        _user_db_instance = UserDB()
    return _user_db_instance

