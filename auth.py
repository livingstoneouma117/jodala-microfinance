"""
SACCOFinance LMS - Auth utilities (JWT via PyJWT)
"""
import os
import jwt
import hashlib
import time
import uuid
from functools import wraps
from flask import request, jsonify, g


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
EXP_HOURS = _int_env("JWT_EXP_HOURS", 24)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token(user: dict) -> str:
    payload = {
        "sub":   str(user["id"]),
        "email": user["email"],
        "role":  user["role"],
        "name":  user["name"],
        "iat":   int(time.time()),
        "exp":   int(time.time()) + EXP_HOURS * 3600,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def gen_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:8].upper()


# ── Decorators ───────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            token = request.args.get("token")
            if token:
                payload = decode_token(token)
                if payload:
                    g.user = payload
                    return f(*args, **kwargs)
            return jsonify({"error": "Missing or invalid token"}), 401
        token = auth.split(" ", 1)[1]
        payload = decode_token(token)
        if not payload:
            return jsonify({"error": "Token expired or invalid"}), 401
        g.user = payload
        return f(*args, **kwargs)
    return decorated


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            if g.user.get("role") not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
