"""
Database Utility Module
SQLite database operations for managing user data
"""

import sqlite3
import os
import datetime
from typing import Optional, Dict, Any


class UserDB:
    """User database management class"""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection

        Args:
            db_path: Database file path, use default path if None
        """
        if db_path is None:
            # Default database path is in the webui directory
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "users.db")

        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database table structure"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create user table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                wallet_address TEXT PRIMARY KEY,
                nickname TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                login_count INTEGER DEFAULT 0
            )
        """
        )

        # Create indexes to improve query performance
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wallet_address 
            ON users(wallet_address)
        """
        )

        # Create invite codes table
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

        # Create invite code usage records table
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

        # Create indexes
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
        Get user information by wallet address

        Args:
            address: Wallet address

        Returns:
            User information dictionary, return None if not exists
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return dictionary format
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
                "created_at": row["created_at"],
                "last_login": row["last_login"],
                "login_count": row["login_count"],
            }
        return None

    def create_user(self, address: str) -> bool:
        """
        Create new user (only create, don't update existing users)

        Args:
            address: Wallet address

        Returns:
            True means new user created, False means user already exists
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
            # User already exists
            is_new = False
        finally:
            conn.close()

        return is_new

    def update_login_info(self, address: str) -> bool:
        """
        Update user login information

        Args:
            address: Wallet address

        Returns:
            Whether update was successful
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

    def update_user_info(self, address: str, nickname: Optional[str] = None) -> bool:
        """
        Update user information (optional registration information)

        Args:
            address: Wallet address
            nickname: Nickname

        Returns:
            Whether update was successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        updates = []
        params = []

        if nickname is not None:
            updates.append("nickname = ?")
            params.append(nickname)

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
        Get all users list (for management)

        Args:
            limit: Return quantity limit

        Returns:
            User list
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
        Create invite code

        Args:
            code: Invite code
            max_uses: Maximum uses, 0 means unlimited
            created_by: Creator wallet address

        Returns:
            Whether creation was successful
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
        Validate invite code

        Args:
            code: Invite code

        Returns:
            Whether invite code is valid and usable
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

        # Check usage limit
        max_uses = row["max_uses"]
        current_uses = row["current_uses"]

        # max_uses = 0 means unlimited
        if max_uses > 0 and current_uses >= max_uses:
            return False

        return True

    def use_invite_code(self, code: str, address: str) -> bool:
        """
        Use invite code (called when registering new user)

        Args:
            code: Invite code
            address: Wallet address using the invite code

        Returns:
            Whether usage was successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check if invite code has already been used
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

            # Check if invite code is valid
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

            # Check usage limit
            if max_uses > 0 and current_uses >= max_uses:
                conn.close()
                return False

            # Increment usage count
            cursor.execute(
                """
                UPDATE invite_codes 
                SET current_uses = current_uses + 1
                WHERE code = ?
            """,
                (code.upper(),),
            )

            # Record usage history
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
        Get invite code information

        Args:
            code: Invite code

        Returns:
            Invite code information dictionary, return None if not exists
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
        Get all invite codes list (for management)

        Args:
            limit: Return quantity limit

        Returns:
            Invite code list
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
        Deactivate invite code

        Args:
            code: Invite code

        Returns:
            Whether deactivation was successful
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


# Global database instance
_user_db_instance = None


def get_user_db() -> UserDB:
    """
    Get global database instance (singleton pattern)

    Returns:
        UserDB instance
    """
    global _user_db_instance
    if _user_db_instance is None:
        _user_db_instance = UserDB()
    return _user_db_instance
