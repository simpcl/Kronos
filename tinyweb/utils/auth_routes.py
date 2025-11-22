"""
认证路由模块
定义 Web3 钱包认证相关的 Flask 路由
"""

import os
from flask import Blueprint, request, jsonify, session
from functools import wraps
from .auth import get_wallet_auth
from .db import get_user_db


# 创建认证蓝图
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "wallet_address" not in session or not session.get("authenticated"):
            return (
                jsonify({"error": "Authentication required", "authenticated": False}),
                401,
            )
        return f(*args, **kwargs)

    return decorated_function


def require_admin_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "wallet_address" not in session or not session.get("authenticated"):
            return (
                jsonify({"error": "Authentication required", "authenticated": False}),
                401,
            )
        address = session.get("wallet_address")
        if not address:
            return jsonify({"error": "Not authenticated"}), 401
        ADMIN_PUBLIC_KEY = os.environ.get("ADMIN_PUBLIC_KEY", "")
        if address is not ADMIN_PUBLIC_KEY:
            return jsonify({"error": "Need admin authenticated"}), 403
        return f(*args, **kwargs)

    return decorated_function


@auth_bp.route("/challenge", methods=["POST"])
def get_challenge():
    """
    获取签名挑战消息（登录/注册的第一步）

    请求体:
        {
            "wallet_address": "0x..."
        }

    返回:
        {
            "success": true,
            "message": "挑战消息",
            "nonce": "随机字符串"
        }
    """
    try:
        data = request.get_json()
        address = data.get("wallet_address")

        if not address:
            return jsonify({"error": "Wallet address is required"}), 400

        auth = get_wallet_auth()

        # 验证地址格式
        if not auth.validate_address(address):
            return jsonify({"error": "Invalid wallet address format"}), 400

        # 生成挑战消息
        message, nonce = auth.generate_challenge_message(address)

        # 将 nonce 存入 session（用于防重放攻击）
        session["auth_nonce"] = nonce
        session["auth_address"] = address.lower()

        return jsonify({"success": True, "message": message, "nonce": nonce})
    except Exception as e:
        return jsonify({"error": f"Failed to generate challenge: {str(e)}"}), 500


@auth_bp.route("/verify", methods=["POST"])
def verify_auth():
    """
    验证签名并完成登录/注册

    请求体:
        {
            "wallet_address": "0x...",
            "signature": "0x...",
            "message": "挑战消息",
            "invite_code": "邀请码（新用户注册时必需）"
        }

    返回:
        {
            "success": true,
            "is_new_user": false,
            "message": "Login successful",
            "user": {...}
        }
    """
    try:
        data = request.get_json()
        address = data.get("wallet_address")
        signature = data.get("signature")
        message = data.get("message")
        invite_code = data.get("invite_code")

        if not all([address, signature, message]):
            return jsonify({"error": "Missing required parameters"}), 400

        auth = get_wallet_auth()

        # 验证签名
        if not auth.verify_signature(message, signature, address):
            return jsonify({"error": "Invalid signature"}), 401

        db = get_user_db()

        # 检查用户是否存在
        existing_user = db.get_user_by_address(address)

        if existing_user:
            # 用户已存在，更新登录信息并允许登录
            is_new = False
            db.update_login_info(address)
            user = db.get_user_by_address(address)
        else:
            # 用户不存在，需要邀请码才能注册
            if not invite_code:
                return (
                    jsonify(
                        {
                            "error": "Invite code required for registration",
                            "requires_invite": True,
                        }
                    ),
                    403,
                )

            # 验证邀请码
            if not db.validate_invite_code(invite_code):
                return (
                    jsonify(
                        {
                            "error": "Invalid or expired invite code",
                            "requires_invite": True,
                        }
                    ),
                    403,
                )

            # 使用邀请码并创建用户
            if not db.use_invite_code(invite_code, address):
                return (
                    jsonify(
                        {"error": "Failed to use invite code", "requires_invite": True}
                    ),
                    403,
                )

            # 创建新用户
            is_new = db.create_user(address)
            user = db.get_user_by_address(address)

            if not user:
                return jsonify({"error": "Failed to create user"}), 500

        # 创建 session
        session["wallet_address"] = address.lower()
        session["authenticated"] = True

        return jsonify(
            {
                "success": True,
                "is_new_user": is_new,
                "message": "Registration successful" if is_new else "Login successful",
                "user": {
                    "wallet_address": user["wallet_address"],
                    "nickname": user["nickname"]
                    or f"User_{address[:8]}...{address[-6:]}",
                    "created_at": user["created_at"],
                    "login_count": user["login_count"],
                },
            }
        )
    except Exception as e:
        return jsonify({"error": f"Authentication failed: {str(e)}"}), 500


@auth_bp.route("/profile", methods=["POST"])
@require_auth
def update_profile():
    """
    更新用户资料（可选注册信息）

    请求体:
        {
            "nickname": "用户昵称"
        }

    返回:
        {
            "success": true,
            "message": "Profile updated successfully",
            "user": {...}
        }
    """
    try:
        address = session.get("wallet_address")
        if not address:
            return jsonify({"error": "Not authenticated"}), 401

        data = request.get_json()
        nickname = data.get("nickname")

        db = get_user_db()
        db.update_user_info(address, nickname=nickname)

        user = db.get_user_by_address(address)
        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify(
            {
                "success": True,
                "message": "Profile updated successfully",
                "user": {
                    "wallet_address": user["wallet_address"],
                    "nickname": user["nickname"],
                },
            }
        )
    except Exception as e:
        return jsonify({"error": f"Failed to update profile: {str(e)}"}), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    登出

    返回:
        {
            "success": true,
            "message": "Logged out successfully"
        }
    """
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})


@auth_bp.route("/status", methods=["GET"])
def auth_status():
    """
    检查登录状态

    返回:
        {
            "authenticated": true/false,
            "user": {...}  # 如果已登录
        }
    """
    if "wallet_address" in session and session.get("authenticated"):
        address = session.get("wallet_address")
        db = get_user_db()
        user = db.get_user_by_address(address)

        if user:
            return jsonify(
                {
                    "authenticated": True,
                    "user": {
                        "wallet_address": user["wallet_address"],
                        "nickname": user["nickname"]
                        or f"User_{address[:8]}...{address[-6:]}",
                        "created_at": user["created_at"],
                        "login_count": user["login_count"],
                    },
                }
            )

    return jsonify({"authenticated": False})


@auth_bp.route("/invite/create", methods=["POST"])
@require_admin_auth
def create_invite_code():
    """
    创建邀请码（需要登录）

    请求体:
        {
            "code": "邀请码",
            "max_uses": 1  # 最大使用次数，0 表示无限制
        }

    返回:
        {
            "success": true,
            "code": "邀请码",
            "message": "Invite code created successfully"
        }
    """
    try:
        address = session.get("wallet_address")
        if not address:
            return jsonify({"error": "Not authenticated"}), 401
        if address[10:18] != "2607d6fd":  # 2607d6fd 是 admin 的 wallet_address
            return jsonify({"error": "Only admin can create invite code"}), 403

        data = request.get_json()
        code = data.get("code")
        max_uses = data.get("max_uses", 1)

        if not code:
            return jsonify({"error": "Invite code is required"}), 400

        db = get_user_db()

        if db.create_invite_code(code, max_uses, address):
            return jsonify(
                {
                    "success": True,
                    "code": code.upper(),
                    "message": "Invite code created successfully",
                }
            )
        else:
            return (
                jsonify({"error": "Failed to create invite code (may already exist)"}),
                400,
            )

    except Exception as e:
        return jsonify({"error": f"Failed to create invite code: {str(e)}"}), 500


@auth_bp.route("/invite/validate", methods=["POST"])
def validate_invite_code_endpoint():
    """
    验证邀请码是否有效（无需登录）

    请求体:
        {
            "code": "邀请码"
        }

    返回:
        {
            "valid": true/false,
            "code": "邀请码",
            "info": {...}  # 如果有效
        }
    """
    try:
        data = request.get_json()
        code = data.get("code")

        if not code:
            return jsonify({"error": "Invite code is required"}), 400

        db = get_user_db()
        is_valid = db.validate_invite_code(code)

        response = {"valid": is_valid, "code": code.upper()}

        if is_valid:
            info = db.get_invite_code_info(code)
            if info:
                response["info"] = {
                    "max_uses": info["max_uses"],
                    "current_uses": info["current_uses"],
                    "remaining_uses": (
                        info["max_uses"] - info["current_uses"]
                        if info["max_uses"] > 0
                        else "unlimited"
                    ),
                }

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": f"Failed to validate invite code: {str(e)}"}), 500


@auth_bp.route("/invite/list", methods=["GET"])
@require_auth
def list_invite_codes():
    """
    获取邀请码列表（需要登录）

    返回:
        {
            "success": true,
            "codes": [...]
        }
    """
    try:
        db = get_user_db()
        codes = db.get_all_invite_codes()

        return jsonify({"success": True, "codes": codes})

    except Exception as e:
        return jsonify({"error": f"Failed to list invite codes: {str(e)}"}), 500


@auth_bp.route("/invite/deactivate", methods=["POST"])
@require_auth
def deactivate_invite_code_endpoint():
    """
    停用邀请码（需要登录）

    请求体:
        {
            "code": "邀请码"
        }

    返回:
        {
            "success": true,
            "message": "Invite code deactivated successfully"
        }
    """
    try:
        data = request.get_json()
        code = data.get("code")

        if not code:
            return jsonify({"error": "Invite code is required"}), 400

        db = get_user_db()

        if db.deactivate_invite_code(code):
            return jsonify(
                {"success": True, "message": "Invite code deactivated successfully"}
            )
        else:
            return jsonify({"error": "Failed to deactivate invite code"}), 400

    except Exception as e:
        return jsonify({"error": f"Failed to deactivate invite code: {str(e)}"}), 500
