from flask import Blueprint

from services.common import *
from services.common import _clear_login_attempts, _login_attempt_key, _login_block_remaining_seconds, _record_failed_login

auth_bp = Blueprint("auth", __name__)
bp = auth_bp


def _serialize_user(user):
    if not user:
        return {}
    return {
        "id": user["id"],
        "name": user["name"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "active": int(user.get("active", 1) or 0),
        "created_at": user.get("created_at"),
        "permissions": normalize_permissions(user.get("permissions")),
    }

@bp.route("/api/auth/login", methods=["POST"])
def login():
    data  = request.json or {}
    username = (data.get("username") or data.get("email") or "").strip().lower()
    pwd   = data.get("password","")
    if not username or not pwd:
        return error("Username and password are required")
    attempt_key = _login_attempt_key(username)
    blocked_for = _login_block_remaining_seconds(attempt_key)
    if blocked_for > 0:
        wait_mins = max(1, -(-blocked_for // 60))
        return error(f"Too many login attempts. Try again in {wait_mins} minute(s).", 429)

    db   = get_db()
    user = row_to_dict(db.execute(
        "SELECT * FROM users WHERE (lower(username)=? OR lower(email)=?) AND active=1", (username, username)
    ).fetchone())

    if not user or not verify_password(pwd, user["password"]):
        db.close()
        _record_failed_login(attempt_key)
        return error("Invalid credentials", 401)

    if password_needs_upgrade(user["password"]):
        upgraded = hash_password(pwd)
        db.execute("UPDATE users SET password=? WHERE id=?", (upgraded, user["id"]))
        db.commit()
        user["password"] = upgraded

    _clear_login_attempts(attempt_key)
    db.close()
    token = generate_token(user)
    return success({
        "token": token,
        "user": _serialize_user(user),
    }, "Login successful")



@bp.route("/api/auth/me", methods=["GET"])
@login_required
def me():
    db   = get_db()
    user = row_to_dict(db.execute(
        "SELECT id,name,username,email,role,active,permissions,created_at FROM users WHERE id=?",
        (g.user["sub"],)
    ).fetchone())
    db.close()
    return success(_serialize_user(user))



@bp.route("/api/auth/change-password", methods=["POST"])
@login_required
def change_password():
    data    = request.json or {}
    old_pwd = data.get("old_password","")
    new_pwd = data.get("new_password","")
    if not old_pwd or not new_pwd:
        return error("Both old and new password required")
    pwd_err = validate_password_strength(new_pwd)
    if pwd_err:
        return error(pwd_err)

    db   = get_db()
    user = row_to_dict(db.execute("SELECT * FROM users WHERE id=?", (g.user["sub"],)).fetchone())
    if not verify_password(old_pwd, user["password"]):
        db.close()
        return error("Current password is incorrect", 401)
    db.execute("UPDATE users SET password=? WHERE id=?", (hash_password(new_pwd), g.user["sub"]))
    db.commit(); db.close()
    audit("Changed password", "Auth")
    return success(msg="Password updated")

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/users", methods=["GET"])
@roles_required("admin")
def get_users():
    db   = get_db()
    rows = rows_to_list(db.execute(
        "SELECT id,name,username,email,role,active,permissions,created_at FROM users ORDER BY id"
    ).fetchall())
    db.close()
    return success([_serialize_user(user) for user in rows])



@bp.route("/api/users", methods=["POST"])
@roles_required("admin")
def create_user():
    d = request.json or {}
    if not all(d.get(k) for k in ("name","username","password","role")):
        return error("name, username, password, role required")
    username = d["username"].strip().lower()
    role = (d.get("role") or "").strip().lower()
    role_err = validate_user_role(role)
    if role_err:
        return error(role_err)
    pwd_err = validate_password_strength(d["password"])
    if pwd_err:
        return error(pwd_err)
    email = (d.get("email") or f"{username}@local.sacco").strip().lower()
    permissions = normalize_permissions(d.get("permissions"))
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (name,username,email,password,role,permissions) VALUES (?,?,?,?,?,?)",
            (d["name"].strip(), username, email, hash_password(d["password"]), role, json.dumps(permissions))
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.close(); return error("Username or email already registered")
    user = row_to_dict(db.execute(
        "SELECT id,name,username,email,role,active,permissions,created_at FROM users WHERE id=last_insert_rowid()"
    ).fetchone())
    db.close()
    audit(f"Created user {username}", "Users")
    return success(_serialize_user(user), "User created", 201)



@bp.route("/api/users/<int:user_id>", methods=["PUT"])
@roles_required("admin")
def update_user(user_id):
    d = request.json or {}
    if not all(d.get(k) for k in ("name","username","role")):
        return error("name, username and role required")
    username = d["username"].strip().lower()
    role = (d.get("role") or "").strip().lower()
    role_err = validate_user_role(role)
    if role_err:
        return error(role_err)
    if str(user_id) == str(g.user["sub"]) and role != "admin":
        return error("You cannot remove your own admin role")
    email = (d.get("email") or f"{username}@local.sacco").strip().lower()
    db = get_db()
    user = row_to_dict(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    if not user:
        db.close(); return error("User not found", 404)
    permissions = normalize_permissions(d.get("permissions", user.get("permissions")))
    try:
        if d.get("password"):
            pwd_err = validate_password_strength(d["password"])
            if pwd_err:
                db.close(); return error(pwd_err)
            db.execute(
                "UPDATE users SET name=?, username=?, email=?, password=?, role=?, permissions=?, active=? WHERE id=?",
                (d["name"].strip(), username, email, hash_password(d["password"]), role, json.dumps(permissions), int(d.get("active", user["active"])), user_id)
            )
        else:
            db.execute(
                "UPDATE users SET name=?, username=?, email=?, role=?, permissions=?, active=? WHERE id=?",
                (d["name"].strip(), username, email, role, json.dumps(permissions), int(d.get("active", user["active"])), user_id)
            )
        db.commit()
    except sqlite3.IntegrityError:
        db.close(); return error("Username or email already registered")
    updated = row_to_dict(db.execute(
        "SELECT id,name,username,email,role,active,permissions,created_at FROM users WHERE id=?",
        (user_id,),
    ).fetchone())
    db.close()
    audit(f"Updated user {username}", "Users")
    return success(_serialize_user(updated), "User updated")



@bp.route("/api/users/<int:user_id>/role", methods=["PATCH"])
@roles_required("admin")
def assign_user_role(user_id):
    d = request.json or {}
    role = (d.get("role") or "").strip().lower()
    role_err = validate_user_role(role)
    if role_err:
        return error(role_err)
    if str(user_id) == str(g.user["sub"]) and role != "admin":
        return error("You cannot remove your own admin role")

    db = get_db()
    user = row_to_dict(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    if not user:
        db.close(); return error("User not found", 404)
    if user.get("role") == role:
        db.close()
        return success(_serialize_user(user), "Role already assigned")

    db.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    db.commit()
    updated = row_to_dict(db.execute(
        "SELECT id,name,username,email,role,active,permissions,created_at FROM users WHERE id=?",
        (user_id,),
    ).fetchone())
    db.close()
    audit(
        f"Assigned role {role} to {updated.get('username') or updated.get('email')}",
        "Users",
        f"Previous role: {user.get('role')}"
    )
    return success(_serialize_user(updated), "Role assigned")



@bp.route("/api/users/<int:user_id>/status", methods=["PATCH"])
@roles_required("admin")
def update_user_status(user_id):
    if str(user_id) == str(g.user["sub"]):
        return error("You cannot change your own account status")
    d = request.json or {}
    active = 1 if d.get("active") else 0
    db = get_db()
    user = row_to_dict(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    if not user:
        db.close(); return error("User not found", 404)
    db.execute("UPDATE users SET active=? WHERE id=?", (active, user_id))
    db.commit(); db.close()
    audit(f"{'Activated' if active else 'Deactivated'} user {user.get('username') or user.get('email')}", "Users")
    return success(msg="User activated" if active else "User deactivated")



@bp.route("/api/users/<int:user_id>/password", methods=["PATCH"])
@roles_required("admin")
def reset_user_password(user_id):
    d = request.json or {}
    new_password = d.get("password", "")
    pwd_err = validate_password_strength(new_password)
    if pwd_err:
        return error(pwd_err)
    db = get_db()
    user = row_to_dict(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    if not user:
        db.close(); return error("User not found", 404)
    db.execute("UPDATE users SET password=? WHERE id=?", (hash_password(new_password), user_id))
    db.commit(); db.close()
    audit(f"Reset password for {user.get('username') or user.get('email')}", "Users")
    return success(msg="Password reset")



@bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@roles_required("admin")
def delete_user(user_id):
    if str(user_id) == str(g.user["sub"]):
        return error("You cannot delete your own account")
    db = get_db()
    user = row_to_dict(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    if not user:
        db.close(); return error("User not found", 404)
    db.execute("UPDATE members SET created_by=NULL WHERE created_by=?", (user_id,))
    db.execute("UPDATE loans SET approved_by=NULL WHERE approved_by=?", (user_id,))
    db.execute("UPDATE loans SET officer_id=NULL WHERE officer_id=?", (user_id,))
    db.execute("UPDATE repayments SET recorded_by=NULL WHERE recorded_by=?", (user_id,))
    db.execute("UPDATE savings_transactions SET recorded_by=NULL WHERE recorded_by=?", (user_id,))
    db.execute("DELETE FROM notifications WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM audit_logs WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit(); db.close()
    audit(f"Deleted user {user.get('username') or user.get('email')}", "Users")
    return success(msg="User deleted")
