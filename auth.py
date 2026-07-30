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

MODULE_ACTIONS = {
    "dashboard": set(),
    "members": {"create", "edit", "delete", "export"},
    "borrowers": {"create", "edit", "delete", "export"},
    "loans": {"create", "edit", "delete", "approve", "disburse", "reject", "export"},
    "loan-products": {"create", "edit", "delete", "export"},
    "savings": {"create", "edit", "delete", "export"},
    "repayments": {"create", "edit", "delete", "export"},
    "reports": {"export"},
    "accounting": {"edit", "export"},
    "expenses": {"create", "edit", "delete", "export"},
    "settings": {"edit"},
    "notifications": {"edit"},
    "audit-logs": {"export"},
}

MODULE_LABELS = {
    "dashboard": "Dashboard",
    "members": "Members",
    "borrowers": "Borrowers",
    "loans": "Loans",
    "loan-products": "Loan Products",
    "savings": "Savings",
    "repayments": "Repayments",
    "reports": "Reports",
    "accounting": "Accounting",
    "expenses": "Expenses",
    "settings": "Settings",
    "notifications": "Notifications",
    "audit-logs": "Audit Logs",
}

ACTION_LABELS = {
    "create": "Create",
    "edit": "Edit",
    "delete": "Delete",
    "approve": "Approve",
    "disburse": "Disburse",
    "reject": "Reject",
    "export": "Export",
}

VALID_PERMISSIONS = tuple(sorted(
    {module for module in MODULE_ACTIONS}
    | {f"{module}.{action}" for module, actions in MODULE_ACTIONS.items() for action in actions}
))


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
        if not perm:
            continue
        if "." in perm:
            module, action = perm.split(".", 1)
            if action == "view":
                perm = module
        if perm in VALID_PERMISSIONS and perm not in seen:
            seen.add(perm)
            cleaned.append(perm)
    return cleaned


def split_permission(permission: str) -> tuple[str, str | None]:
    safe = str(permission or "").strip().lower()
    if not safe:
        return "", None
    if "." not in safe:
        return safe, None
    module, action = safe.split(".", 1)
    if action == "view":
        return module, None
    return module, action or None


def permission_matches(user_permission: str, required_permission: str) -> bool:
    user_module, user_action = split_permission(user_permission)
    req_module, req_action = split_permission(required_permission)
    if not user_module or not req_module or user_module != req_module:
        return False
    if user_action is None or req_action is None:
        return True
    return user_action == req_action


def route_permission_for_path(path: str, method: str | None = None) -> str | None:
    safe_path = str(path or "")
    safe_method = str(method or "").upper()

    if safe_path.startswith("/api/reports/export/"):
        return "reports.export"
    if safe_path.startswith("/api/loans/") and safe_path.endswith("/approve"):
        return "loans.approve"
    if safe_path.startswith("/api/loans/") and safe_path.endswith("/disburse"):
        return "loans.disburse"
    if safe_path.startswith("/api/loans/") and safe_path.endswith("/reject"):
        return "loans.reject"
    if safe_path.startswith("/api/loans/") and (safe_path.endswith("/statement.pdf") or safe_path.endswith("/statement")):
        return "loans.export"
    if safe_path.startswith("/api/loans/") and ("/guarantors" in safe_path or safe_path.endswith("/restructure")):
        return "loans.edit"
    if safe_path.startswith("/api/savings/") and "/passbook" in safe_path:
        return "savings.export"
    if safe_path.startswith("/api/expenses/accounts/") and safe_path.endswith("/status"):
        return "expenses.edit"
    if safe_path.startswith("/api/notifications/read-all"):
        return "notifications.edit"
    if safe_path.startswith("/api/notifications/") and safe_path.endswith("/read"):
        return "notifications.edit"
    if safe_path.startswith("/api/settings/account/add"):
        return "settings.edit"
    if safe_path.startswith("/api/settings"):
        return "settings.edit" if safe_method in {"PUT", "POST", "PATCH", "DELETE"} else "settings"
    if safe_path.startswith("/api/dividends"):
        if safe_method in {"GET", "HEAD"}:
            return "accounting"
        return "accounting.edit"

    prefix_map = {
        "/api/members": "members",
        "/api/borrowers": "members",
        "/api/loan-products": "loan-products",
        "/api/loans": "loans",
        "/api/savings": "savings",
        "/api/repayments": "repayments",
        "/api/reports": "reports",
        "/api/accounting": "accounting",
        "/api/expenses": "expenses",
    }
    for prefix, module in prefix_map.items():
        if safe_path.startswith(prefix):
            if safe_method in {"GET", "HEAD"}:
                return module
            if safe_method == "POST":
                return f"{module}.create"
            if safe_method in {"PUT", "PATCH"}:
                return f"{module}.edit"
            if safe_method == "DELETE":
                return f"{module}.delete"
            return module
    return None


def has_permission(user: dict, permission: str) -> bool:
    perm = str(permission or "").strip().lower()
    if not perm:
        return False
    user_permissions = normalize_permissions(user.get("permissions"))
    return any(permission_matches(user_perm, perm) for user_perm in user_permissions)


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

            route_permission = route_permission_for_path(request.path, request.method)
            if route_permission and has_permission(g.user, route_permission):
                return f(*args, **kwargs)

            return jsonify({"error": "Insufficient permissions"}), 403
        return decorated
    return decorator

