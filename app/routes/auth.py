from functools import wraps
from flask import Blueprint, request, jsonify, session
from app.models import User, record_audit

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

def owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or session.get("role") not in ("owner", "admin"):
            return jsonify({"authenticated": False, "error": "Owner session required"}), 401
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    identifier = data.get("identifier", "").strip()
    password = data.get("password", "")

    if not identifier or not password:
        return jsonify({"error": "Identifier and password required"}), 400

    user = User.get_by_username_or_email(identifier)
    if not user or not User.verify_password(user, password):
        record_audit("LOGIN_REJECTED", f"Failed login attempt for '{identifier}'", ip_address=request.remote_addr)
        return jsonify({"error": "Invalid owner credentials"}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]

    record_audit("OWNER_LOGGED_IN", f"Owner '{user['username']}' authenticated", ip_address=request.remote_addr)
    return jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"]
        }
    })

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    record_audit("OWNER_LOGGED_OUT", "Owner session terminated", ip_address=request.remote_addr)
    return jsonify({"success": True, "message": "Logged out successfully"})

@auth_bp.route("/me", methods=["GET"])
def me():
    user_id = session.get("user_id")
    if not user_id or session.get("role") not in ("owner", "admin"):
        return jsonify({"authenticated": False}), 200

    user = User.get_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({"authenticated": False}), 200

    return jsonify({
        "authenticated": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"]
        }
    })

@auth_bp.route("/change-password", methods=["POST"])
@owner_required
def change_password():
    data = request.get_json() or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not new_password or len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    user = User.get_by_id(session["user_id"])
    if not User.verify_password(user, current_password):
        return jsonify({"error": "Current password is incorrect"}), 400

    User.update_password(user["id"], new_password)
    record_audit("PASSWORD_CHANGED", "Owner password updated", ip_address=request.remote_addr)
    return jsonify({"success": True, "message": "Password updated successfully"})
