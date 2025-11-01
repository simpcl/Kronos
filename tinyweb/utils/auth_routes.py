"""
认证路由模块
定义 Web3 钱包认证相关的 Flask 路由
"""
from flask import Blueprint, request, jsonify, session
from functools import wraps
from .auth import get_wallet_auth
from .db import get_user_db


# 创建认证蓝图
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def require_auth(f):
    """
    登录验证装饰器
    
    用于保护需要认证的路由
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'wallet_address' not in session or not session.get('authenticated'):
            return jsonify({'error': 'Authentication required', 'authenticated': False}), 401
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/challenge', methods=['POST'])
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
        session['auth_nonce'] = nonce
        session['auth_address'] = address.lower()
        
        return jsonify({
            "success": True,
            "message": message,
            "nonce": nonce
        })
    except Exception as e:
        return jsonify({"error": f"Failed to generate challenge: {str(e)}"}), 500


@auth_bp.route('/verify', methods=['POST'])
def verify_auth():
    """
    验证签名并完成登录/注册
    
    请求体:
        {
            "wallet_address": "0x...",
            "signature": "0x...",
            "message": "挑战消息"
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
        
        if not all([address, signature, message]):
            return jsonify({"error": "Missing required parameters"}), 400
        
        auth = get_wallet_auth()
        
        # 验证签名
        if not auth.verify_signature(message, signature, address):
            return jsonify({"error": "Invalid signature"}), 401
        
        # 检查用户是否存在
        db = get_user_db()
        user_exists = db.get_user_by_address(address) is not None
        
        # 创建或更新用户（自动注册）
        is_new = db.create_user(address)
        user = db.get_user_by_address(address)
        
        if not user:
            return jsonify({"error": "Failed to create user"}), 500
        
        # 创建 session
        session['wallet_address'] = address.lower()
        session['authenticated'] = True
        
        return jsonify({
            "success": True,
            "is_new_user": is_new,
            "message": "Registration successful" if is_new else "Login successful",
            "user": {
                "wallet_address": user['wallet_address'],
                "nickname": user['nickname'] or f"User_{address[:8]}...{address[-6:]}",
                "email": user['email'],
                "created_at": user['created_at'],
                "login_count": user['login_count']
            }
        })
    except Exception as e:
        return jsonify({"error": f"Authentication failed: {str(e)}"}), 500


@auth_bp.route('/profile', methods=['POST'])
@require_auth
def update_profile():
    """
    更新用户资料（可选注册信息）
    
    请求体:
        {
            "nickname": "用户昵称",
            "email": "user@example.com"
        }
        
    返回:
        {
            "success": true,
            "message": "Profile updated successfully",
            "user": {...}
        }
    """
    try:
        address = session.get('wallet_address')
        if not address:
            return jsonify({"error": "Not authenticated"}), 401
        
        data = request.get_json()
        nickname = data.get("nickname")
        email = data.get("email")
        
        db = get_user_db()
        db.update_user_info(address, nickname=nickname, email=email)
        
        user = db.get_user_by_address(address)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        return jsonify({
            "success": True,
            "message": "Profile updated successfully",
            "user": {
                "wallet_address": user['wallet_address'],
                "nickname": user['nickname'],
                "email": user['email']
            }
        })
    except Exception as e:
        return jsonify({"error": f"Failed to update profile: {str(e)}"}), 500


@auth_bp.route('/logout', methods=['POST'])
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


@auth_bp.route('/status', methods=['GET'])
def auth_status():
    """
    检查登录状态
    
    返回:
        {
            "authenticated": true/false,
            "user": {...}  # 如果已登录
        }
    """
    if 'wallet_address' in session and session.get('authenticated'):
        address = session.get('wallet_address')
        db = get_user_db()
        user = db.get_user_by_address(address)
        
        if user:
            return jsonify({
                "authenticated": True,
                "user": {
                    "wallet_address": user['wallet_address'],
                    "nickname": user['nickname'] or f"User_{address[:8]}...{address[-6:]}",
                    "email": user['email'],
                    "created_at": user['created_at'],
                    "login_count": user['login_count']
                }
            })
    
    return jsonify({"authenticated": False})

