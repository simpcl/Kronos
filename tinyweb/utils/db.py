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
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                wallet_address TEXT PRIMARY KEY,
                nickname TEXT,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                login_count INTEGER DEFAULT 0
            )
        """
        )

        # 创建索引提高查询性能
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wallet_address 
            ON users(wallet_address)
        """
        )

        # 创建邀请码表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS invite_codes (
                code TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                max_uses INTEGER DEFAULT 1,
                current_uses INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_by TEXT
            )
        """
        )

        # 创建邀请码使用记录表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS invite_code_uses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                used_by TEXT NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (code) REFERENCES invite_codes(code)
            )
        """
        )

        # 创建索引
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_invite_code 
            ON invite_codes(code)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_invite_code_uses 
            ON invite_code_uses(code, used_by)
        """
        )

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
            "SELECT * FROM users WHERE wallet_address = ?", (address.lower(),)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "wallet_address": row["wallet_address"],
                "nickname": row["nickname"],
                "email": row["email"],
                "created_at": row["created_at"],
                "last_login": row["last_login"],
                "login_count": row["login_count"],
            }
        return None

    def create_user(self, address: str) -> bool:
        """
        创建新用户（仅创建，不更新已存在的用户）

        Args:
            address: 钱包地址

        Returns:
            True 表示创建了新用户，False 表示用户已存在
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO users (wallet_address, login_count, last_login)
                VALUES (?, 1, CURRENT_TIMESTAMP)
            """,
                (address.lower(),),
            )
            conn.commit()
            is_new = True
        except sqlite3.IntegrityError:
            # 用户已存在
            is_new = False
        finally:
            conn.close()

        return is_new

    def update_login_info(self, address: str) -> bool:
        """
        更新用户登录信息

        Args:
            address: 钱包地址

        Returns:
            是否成功更新
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users 
            SET last_login = CURRENT_TIMESTAMP, 
                login_count = login_count + 1
            WHERE wallet_address = ?
        """,
            (address.lower(),),
        )
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()

        return updated

    def update_user_info(
        self, address: str, nickname: Optional[str] = None, email: Optional[str] = None
    ) -> bool:
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
            updates.append("nickname = ?")
            params.append(nickname)
        if email is not None:
            updates.append("email = ?")
            params.append(email)

        if not updates:
            conn.close()
            return False

        params.append(address.lower())
        cursor.execute(
            f'UPDATE users SET {", ".join(updates)} WHERE wallet_address = ?', params
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

        cursor.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "wallet_address": row["wallet_address"],
                "nickname": row["nickname"],
                "email": row["email"],
                "created_at": row["created_at"],
                "last_login": row["last_login"],
                "login_count": row["login_count"],
            }
            for row in rows
        ]

    def create_invite_code(
        self, code: str, max_uses: int = 1, created_by: Optional[str] = None
    ) -> bool:
        """
        创建邀请码

        Args:
            code: 邀请码
            max_uses: 最大使用次数，0 表示无限制
            created_by: 创建者钱包地址

        Returns:
            是否成功创建
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO invite_codes (code, max_uses, created_by)
                VALUES (?, ?, ?)
            """,
                (code.upper(), max_uses, created_by),
            )
            conn.commit()
            success = True
        except sqlite3.IntegrityError:
            success = False
        finally:
            conn.close()

        return success

    def validate_invite_code(self, code: str) -> bool:
        """
        验证邀请码是否有效

        Args:
            code: 邀请码

        Returns:
            邀请码是否有效可用
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM invite_codes 
            WHERE code = ? AND is_active = 1
        """,
            (code.upper(),),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return False

        # 检查使用次数限制
        max_uses = row["max_uses"]
        current_uses = row["current_uses"]

        # max_uses = 0 表示无限制
        if max_uses > 0 and current_uses >= max_uses:
            return False

        return True

    def use_invite_code(self, code: str, address: str) -> bool:
        """
        使用邀请码（注册新用户时调用）

        Args:
            code: 邀请码
            address: 使用邀请码的钱包地址

        Returns:
            是否成功使用
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 检查是否已经使用过该邀请码
            cursor.execute(
                """
                SELECT COUNT(*) FROM invite_code_uses 
                WHERE code = ? AND used_by = ?
            """,
                (code.upper(), address.lower()),
            )
            already_used = cursor.fetchone()[0] > 0

            if already_used:
                conn.close()
                return False

            # 检查邀请码是否有效
            cursor.execute(
                """
                SELECT max_uses, current_uses, is_active 
                FROM invite_codes 
                WHERE code = ?
            """,
                (code.upper(),),
            )
            row = cursor.fetchone()

            if not row or row[2] != 1:  # is_active
                conn.close()
                return False

            max_uses, current_uses = row[0], row[1]

            # 检查使用次数限制
            if max_uses > 0 and current_uses >= max_uses:
                conn.close()
                return False

            # 增加使用次数
            cursor.execute(
                """
                UPDATE invite_codes 
                SET current_uses = current_uses + 1
                WHERE code = ?
            """,
                (code.upper(),),
            )

            # 记录使用历史
            cursor.execute(
                """
                INSERT INTO invite_code_uses (code, used_by)
                VALUES (?, ?)
            """,
                (code.upper(), address.lower()),
            )

            conn.commit()
            success = True
        except Exception as e:
            conn.rollback()
            success = False
        finally:
            conn.close()

        return success

    def get_invite_code_info(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取邀请码信息

        Args:
            code: 邀请码

        Returns:
            邀请码信息字典，如果不存在返回 None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM invite_codes WHERE code = ?
        """,
            (code.upper(),),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "code": row["code"],
                "created_at": row["created_at"],
                "max_uses": row["max_uses"],
                "current_uses": row["current_uses"],
                "is_active": bool(row["is_active"]),
                "created_by": row["created_by"],
            }
        return None

    def get_all_invite_codes(self, limit: int = 100) -> list:
        """
        获取所有邀请码列表（用于管理）

        Args:
            limit: 返回数量限制

        Returns:
            邀请码列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM invite_codes 
            ORDER BY created_at DESC 
            LIMIT ?
        """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "code": row["code"],
                "created_at": row["created_at"],
                "max_uses": row["max_uses"],
                "current_uses": row["current_uses"],
                "is_active": bool(row["is_active"]),
                "created_by": row["created_by"],
            }
            for row in rows
        ]

    def deactivate_invite_code(self, code: str) -> bool:
        """
        停用邀请码

        Args:
            code: 邀请码

        Returns:
            是否成功停用
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE invite_codes 
            SET is_active = 0 
            WHERE code = ?
        """,
            (code.upper(),),
        )
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()

        return updated


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
