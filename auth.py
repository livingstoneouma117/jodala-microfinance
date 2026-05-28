"""
SACCOFinance LMS - Auth utilities (JWT via PyJWT)
"""
import json
import os
import jwt
import hashlib
import time
import uuid
from functools import wraps
from flask import request, jsonify, g

from database import get_db


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
EXP_HOURS = _int_env("JWT_EXP_HOURS", 24)

FEATURE_PERMISSIONS = {
    "dashboard": "dashboard",
    "members": "members",
    "borrowers": "members",
    "loans": "loans",
    "loan-products": "loans",
    "savings": "savings",
    "repayments": "repayments",
    "reports": "reports",
    "accounting": "accounting",
    "expenses": "expenses",
    "settings": "settings",
    "notifications": "settings",
    "audit-logs": "settings",
}

VALID_PERMISSIONS = tuple(sorted(set(FEATURE_PERMISSIONS.values())))


def _load_secret_key() -> str:
    key = (os.environ.get("SECRET_KEY") or "").strip()
    if not key:
        # Dev fallback; set SECRET_KEY explicitly in production.
        key = "dev-secret-key-change-this-before-production-2026"
    if ALGORITHM.upper().startswith("HS") and len(key.encode("utf-8")) < 32:
        # Keep deployment backward-compatible if an older short key is still set.
        # A stronger explicit SECRET_KEY should still be configured in production.
        key = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return key


SECRET_KEY = _load_secret_key()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def normalize_role(role: str) -> str:
    return str(role or "").strip().lower()


def normalize_permissions(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = [item.strip() for item in raw.split(",")]
    elif isinstance(value, (list, tuple, set)):
        parsed = list(value)
    else:
        parsed = []

    seen = set()
    cleaned = []
    for item in parsed:
        perm = str(item or "").strip().lower().replace(" ", "_")
        if perm and perm in VALID_PERMISSIONS and perm not in seen:
            seen.add(perm)
            cleaned.append(perm)
    return cleaned


def route_permission_for_path(path: str) -> str | None:
    safe_path = str(path or "")
    for prefix, permission in FEATURE_PERMISSIONS.items():
        if safe_path.startswith(f"/api/{prefix}"):
            return permission
    return None


def has_permission(user: dict, permission: str) -> bool:
    perm = str(permission or "").strip().lower()
    if not perm:
        return False
    return perm in normalize_permissions(user.get("permissions"))


def generate_token(user: dict) -> str:
    payload = {
        "sub":   str(user["id"]),
        "email": user["email"],
        "role":  user["role"],
        "name":  user["name"],
        "permissions": normalize_permissions(user.get("permissions")),
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

def _load_current_user(user_id):
    db = get_db()
    user = db.execute(
        "SELECT id,name,username,email,role,active,permissions,created_at FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    db.close()
    if not user or not int(user["active"] or 0):
        return None
    return {
        "sub": str(user["id"]),
        "name": user["name"],
        "username": user["username"],
        "email": user["email"],
        "role": normalize_role(user["role"]),
        "active": int(user["active"] or 0),
        "permissions": normalize_permissions(user["permissions"]),
        "created_at": user["created_at"],
    }


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            token = request.args.get("token")
            if token:
                payload = decode_token(token)
                if payload:
                    user = _load_current_user(payload.get("sub"))
                    if user:
                        g.user = user
                        return f(*args, **kwargs)
            return jsonify({"error": "Missing or invalid token"}), 401
        token = auth.split(" ", 1)[1]
        payload = decode_token(token)
        if not payload:
            return jsonify({"error": "Token expired or invalid"}), 401
        user = _load_current_user(payload.get("sub"))
        if not user:
            return jsonify({"error": "Token expired or invalid"}), 401
        g.user = user
        return f(*args, **kwargs)
    return decorated


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            normalized_roles = {normalize_role(role) for role in roles}
            user_role = normalize_role(g.user.get("role"))
            if user_role in normalized_roles:
                return f(*args, **kwargs)

            route_permission = route_permission_for_path(request.path)
            if route_permission and has_permission(g.user, route_permission):
                return f(*args, **kwargs)

            return jsonify({"error": "Insufficient permissions"}), 403
        return decorated
    return decorator

