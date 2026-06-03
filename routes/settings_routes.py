from flask import Blueprint

from services.common import *

settings_bp = Blueprint("settings", __name__)
bp = settings_bp

@bp.route("/api/notifications", methods=["GET"])
@login_required
def get_notifications():
    db = get_db()
    rows = rows_to_list(db.execute(
        "SELECT * FROM notifications WHERE user_id=? OR user_id IS NULL ORDER BY created_at DESC LIMIT 30",
        (g.user["sub"],)
    ).fetchall())
    unread = db.execute(
        "SELECT COUNT(*) FROM notifications WHERE (user_id=? OR user_id IS NULL) AND read=0",
        (g.user["sub"],)
    ).fetchone()[0]
    db.close()
    return success({"notifications": rows, "unread": unread})



@bp.route("/api/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    db = get_db()
    db.execute("UPDATE notifications SET read=1 WHERE user_id=? OR user_id IS NULL", (g.user["sub"],))
    db.commit(); db.close()
    return success(msg="All notifications marked as read")



@bp.route("/api/notifications/<int:nid>/read", methods=["PATCH"])
@login_required
def mark_read(nid):
    db = get_db()
    db.execute("UPDATE notifications SET read=1 WHERE id=?", (nid,))
    db.commit(); db.close()
    return success(msg="Notification marked as read")

# ══════════════════════════════════════════════════════════════════════════════
# AUDIT LOG
# ══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/audit-logs", methods=["GET"])
@login_required
@roles_required("admin","accountant")
def get_audit_logs():
    module = request.args.get("module","")
    page   = max(1, int(request.args.get("page",1)))
    limit  = int(request.args.get("limit",15))
    where  = "WHERE module=?" if module else ""
    params = [module] if module else []
    db     = get_db()
    total  = db.execute(f"SELECT COUNT(*) FROM audit_logs {where}", params).fetchone()[0]
    rows   = rows_to_list(db.execute(
        f"SELECT * FROM audit_logs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, (page-1)*limit]
    ).fetchall())
    db.close()
    return success({"logs": rows, "total": total, "page": page, "limit": limit, "pages": -(-total//limit)})

# ══════════════════════════════════════════════════════════════════════════════
# USERS (admin only)
# ══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/settings", methods=["GET"])
def get_settings():
    return success(get_settings_dict())



@bp.route("/api/settings", methods=["PUT"])
@roles_required("admin")
def update_settings():
    allowed = {
        "sacco_name",
        "logo_text",
        "logo_image",
        "logo_url",
        "address",
        "phone",
        "account_opening_balance",
        "default_penalty_rate",
        "penalty_grace_days",
    }
    d = request.json or {}
    db = get_db()
    for key, value in d.items():
        if key in allowed:
            db.execute(
                "INSERT INTO app_settings (key,value,updated_at) VALUES (?,?,datetime('now')) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
                (key, str(value or ""))
            )
    db.commit(); db.close()
    audit("Updated application settings", "Settings")
    return success(get_settings_dict(), "Settings saved")



@bp.route("/api/settings/account/add", methods=["POST"])
@roles_required("admin", "accountant")
def add_main_account_funds():
    d = request.json or {}
    try:
        amount = float(d.get("amount") or 0)
    except (TypeError, ValueError):
        return error("Amount must be a valid number")
    if amount <= 0:
        return error("Amount must be greater than zero")

    db = get_db()
    current_opening = get_account_opening_balance(db)
    new_opening = set_account_opening_balance(db, current_opening + amount)
    db.commit()
    db.close()

    audit("Added funds to main account", "Settings", f"KES {amount:,.2f}")
    settings = get_settings_dict()
    return success({
        "added_amount": amount,
        "account_opening_balance": float(settings.get("account_opening_balance") or 0),
        "settings": settings,
    }, "Main account updated")

# ══════════════════════════════════════════════════════════════════════════════
# LOAN CALCULATOR (public — no auth)
# ══════════════════════════════════════════════════════════════════════════════
