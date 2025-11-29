"""
Authentication Routes Module
Defines Flask routes for Web3 wallet authentication
"""

import os
from flask import Blueprint, request, jsonify, session
from functools import wraps
from .auth import get_wallet_auth
from .db import get_user_db


# Create authentication blueprint
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
        ADMIN_WALLET_ADDRESS = os.environ.get("ADMIN_WALLET_ADDRESS", "")
        if address != ADMIN_WALLET_ADDRESS.lower():
            print(f"admin wallet address: {ADMIN_WALLET_ADDRESS}")
            print(f"Not admin: {address}")
            return jsonify({"error": "Need admin authenticated"}), 403
        return f(*args, **kwargs)

    return decorated_function


@auth_bp.route("/challenge", methods=["POST"])
def get_challenge():
    """
    Get signature challenge message (first step of login/registration)

    Request body:
        {
            "wallet_address": "0x..."
        }

    Returns:
        {
            "success": true,
            "message": "Challenge message",
            "nonce": "Random string"
        }
    """
    try:
        data = request.get_json()
        address = data.get("wallet_address")

        if not address:
            return jsonify({"error": "Wallet address is required"}), 400

        auth = get_wallet_auth()

        # Validate address format
        if not auth.validate_address(address):
            return jsonify({"error": "Invalid wallet address format"}), 400

        # Generate challenge message
        message, nonce = auth.generate_challenge_message(address)

        # Store nonce in session (for replay attack prevention)
        session["auth_nonce"] = nonce
        session["auth_address"] = address.lower()

        return jsonify({"success": True, "message": message, "nonce": nonce})
    except Exception as e:
        return jsonify({"error": f"Failed to generate challenge: {str(e)}"}), 500


@auth_bp.route("/verify", methods=["POST"])
def verify_auth():
    """
    Verify signature and complete login/registration

    Request body:
        {
            "wallet_address": "0x...",
            "signature": "0x...",
            "message": "Challenge message",
            "invite_code": "Invite code (required for new user registration)"
        }

    Returns:
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

        # Verify signature
        if not auth.verify_signature(message, signature, address):
            return jsonify({"error": "Invalid signature"}), 401

        db = get_user_db()

        # Check if user exists
        existing_user = db.get_user_by_address(address)

        if existing_user:
            # User exists, update login info and allow login
            is_new = False
            db.update_login_info(address)
            user = db.get_user_by_address(address)
        else:
            # User doesn't exist, invite code required for registration
            admin_wallet_address = os.environ.get("ADMIN_WALLET_ADDRESS", "")
            if admin_wallet_address.lower() != address:
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

                # Validate invite code
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

                # Use invite code and create user
                if not db.use_invite_code(invite_code, address):
                    return (
                        jsonify(
                            {"error": "Failed to use invite code", "requires_invite": True}
                        ),
                        403,
                    )

            # Create new user
            is_new = db.create_user(address)
            user = db.get_user_by_address(address)

            if not user:
                return jsonify({"error": "Failed to create user"}), 500

        # Create session
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
    Update user profile (optional registration information)

    Request body:
        {
            "nickname": "User nickname"
        }

    Returns:
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
    Logout

    Returns:
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
    Check authentication status

    Returns:
        {
            "authenticated": true/false,
            "user": {...}  # if authenticated
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
    Create invite code (requires login)

    Request body:
        {
            "code": "Invite code",
            "max_uses": 1  # Maximum uses, 0 means unlimited
        }

    Returns:
        {
            "success": true,
            "code": "Invite code",
            "message": "Invite code created successfully"
        }
    """
    try:
        address = session.get("wallet_address")
        if not address:
            return jsonify({"error": "Not authenticated"}), 401

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
    Validate invite code (no login required)

    Request body:
        {
            "code": "Invite code"
        }

    Returns:
        {
            "valid": true/false,
            "code": "Invite code",
            "info": {...}  # if valid
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
    Get invite code list (requires login)

    Returns:
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
    Deactivate invite code (requires login)

    Request body:
        {
            "code": "Invite code"
        }

    Returns:
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
