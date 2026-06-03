from flask_compat import Blueprint

from services.common import *

expenses_bp = Blueprint("expenses", __name__)
bp = expenses_bp

@bp.route("/api/expenses/accounts", methods=["GET"])
@login_required
def get_expense_accounts():
    include_inactive = request.args.get("include_inactive", "false").strip().lower() == "true"
    db = get_db()
    if include_inactive:
        rows = rows_to_list(db.execute(
            """SELECT ea.*, u.name as created_by_name
               FROM expense_accounts ea
               LEFT JOIN users u ON ea.created_by=u.id
               ORDER BY ea.active DESC, ea.name ASC"""
        ).fetchall())
    else:
        rows = rows_to_list(db.execute(
            """SELECT ea.*, u.name as created_by_name
               FROM expense_accounts ea
               LEFT JOIN users u ON ea.created_by=u.id
               WHERE ea.active=1
               ORDER BY ea.name ASC"""
        ).fetchall())
    db.close()
    return success(rows)



@bp.route("/api/expenses/accounts", methods=["POST"])
@login_required
@roles_required("admin", "accountant")
def create_expense_account():
    d = request.json or {}
    name = (d.get("name") or "").strip()
    code = (d.get("code") or "").strip().upper()
    description = (d.get("description") or "").strip()

    if not name:
        return error("Account name is required")

    db = get_db()
    try:
        db.execute(
            "INSERT INTO expense_accounts (code,name,description,active,created_by) VALUES (?,?,?,?,?)",
            (code or None, name, description or None, 1, g.user["sub"])
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        return error("Expense account name or code already exists")

    account = row_to_dict(db.execute(
        "SELECT * FROM expense_accounts WHERE id=last_insert_rowid()"
    ).fetchone())
    db.close()
    audit(f"Created expense account {account['name']}", "Expenses", account.get("code") or "")
    return success(account, "Expense account created", 201)



@bp.route("/api/expenses/accounts/<int:account_id>/status", methods=["PATCH"])
@login_required
@roles_required("admin", "accountant")
def update_expense_account_status(account_id):
    d = request.json or {}
    active = 1 if bool(d.get("active", True)) else 0

    db = get_db()
    account = row_to_dict(db.execute(
        "SELECT * FROM expense_accounts WHERE id=?",
        (account_id,)
    ).fetchone())
    if not account:
        db.close()
        return error("Expense account not found", 404)

    db.execute("UPDATE expense_accounts SET active=? WHERE id=?", (active, account_id))
    db.commit()
    updated = row_to_dict(db.execute("SELECT * FROM expense_accounts WHERE id=?", (account_id,)).fetchone())
    db.close()
    audit(
        f"{'Activated' if active else 'Deactivated'} expense account {updated.get('name')}",
        "Expenses",
        updated.get("code") or ""
    )
    return success(updated, "Expense account status updated")



@bp.route("/api/expenses/transactions", methods=["GET"])
@login_required
def get_expense_transactions():
    q = request.args.get("q", "").strip()
    account_id = request.args.get("account_id", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    limit = int(request.args.get("limit", 15))

    where = []
    params = []
    if q:
        where.append("(et.id LIKE ? OR et.reference LIKE ? OR et.payee LIKE ? OR et.notes LIKE ? OR ea.name LIKE ?)")
        params.extend([f"%{q}%"] * 5)
    if account_id:
        where.append("et.account_id=?")
        params.append(account_id)
    if date_from:
        where.append("et.expense_date>=?")
        params.append(clean_date(date_from))
    if date_to:
        where.append("et.expense_date<=?")
        params.append(clean_date(date_to))

    clause = ("WHERE " + " AND ".join(where)) if where else ""
    db = get_db()
    total = db.execute(
        f"""SELECT COUNT(*)
            FROM expense_transactions et
            JOIN expense_accounts ea ON et.account_id=ea.id
            {clause}""",
        params,
    ).fetchone()[0]
    total_amount = db.execute(
        f"""SELECT COALESCE(SUM(et.amount),0)
            FROM expense_transactions et
            JOIN expense_accounts ea ON et.account_id=ea.id
            {clause}""",
        params,
    ).fetchone()[0]
    rows = rows_to_list(db.execute(
        f"""SELECT et.*, ea.name as account_name, ea.code as account_code, u.name as recorded_by_name
            FROM expense_transactions et
            JOIN expense_accounts ea ON et.account_id=ea.id
            LEFT JOIN users u ON et.recorded_by=u.id
            {clause}
            ORDER BY et.expense_date DESC, et.created_at DESC
            LIMIT ? OFFSET ?""",
        params + [limit, (page - 1) * limit],
    ).fetchall())
    db.close()
    return success({
        "transactions": rows,
        "total": total,
        "total_amount": total_amount,
        "page": page,
        "limit": limit,
        "pages": -(-total // limit),
    })



@bp.route("/api/expenses/transactions", methods=["POST"])
@login_required
@roles_required("admin", "accountant")
def create_expense_transaction():
    d = request.json or {}
    if not d.get("account_id") or not d.get("amount"):
        return error("account_id and amount are required")

    amount = float(d.get("amount") or 0)
    if amount <= 0:
        return error("Amount must be greater than zero")

    expense_date = clean_date(d.get("expense_date"), date.today().isoformat())
    db = get_db()
    account = row_to_dict(db.execute(
        "SELECT * FROM expense_accounts WHERE id=?",
        (d["account_id"],)
    ).fetchone())
    if not account:
        db.close()
        return error("Expense account not found")
    if not int(account.get("active") or 0):
        db.close()
        return error("Expense account is inactive")

    eid = gen_id("EX")
    reference = (d.get("reference") or "").strip() or f"EXP-{gen_id()}"
    payee = (d.get("payee") or "").strip()
    notes = (d.get("notes") or "").strip()

    db.execute(
        """INSERT INTO expense_transactions
           (id,account_id,amount,expense_date,reference,payee,notes,recorded_by)
           VALUES (?,?,?,?,?,?,?,?)""",
        (eid, int(d["account_id"]), amount, expense_date, reference, payee or None, notes or None, g.user["sub"])
    )
    adjust_account_opening_balance(db, -amount)
    db.commit()
    row = row_to_dict(db.execute(
        """SELECT et.*, ea.name as account_name, ea.code as account_code
           FROM expense_transactions et
           JOIN expense_accounts ea ON et.account_id=ea.id
           WHERE et.id=?""",
        (eid,),
    ).fetchone())
    db.close()
    audit(f"Recorded expense {eid}", "Expenses", f"KES {amount:,.2f} - {row.get('account_name')}")
    return success(row, "Expense recorded", 201)





@bp.route("/api/expenses/transactions/<expense_id>", methods=["PUT", "PATCH"])
@login_required
@roles_required("admin", "accountant")
def update_expense_transaction(expense_id):
    d = request.json or {}
    if not d.get("account_id") or not d.get("amount"):
        return error("account_id and amount are required")

    try:
        account_id = int(d.get("account_id"))
        amount = float(d.get("amount") or 0)
    except (TypeError, ValueError):
        return error("Invalid account or amount")

    if amount <= 0:
        return error("Amount must be greater than zero")

    expense_date = clean_date(d.get("expense_date"), date.today().isoformat())
    reference = (d.get("reference") or "").strip() or None
    payee = (d.get("payee") or "").strip() or None
    notes = (d.get("notes") or "").strip() or None

    db = get_db()
    existing = row_to_dict(db.execute(
        "SELECT * FROM expense_transactions WHERE id=?",
        (expense_id,),
    ).fetchone())
    if not existing:
        db.close()
        return error("Expense not found", 404)

    account = row_to_dict(db.execute(
        "SELECT * FROM expense_accounts WHERE id=?",
        (account_id,),
    ).fetchone())
    if not account:
        db.close()
        return error("Expense account not found")
    if not int(account.get("active") or 0) and account_id != int(existing.get("account_id") or 0):
        db.close()
        return error("Expense account is inactive")

    db.execute(
        """UPDATE expense_transactions
           SET account_id=?, amount=?, expense_date=?, reference=?, payee=?, notes=?
           WHERE id=?""",
        (account_id, amount, expense_date, reference, payee, notes, expense_id),
    )
    old_amount = float(existing.get("amount") or 0)
    adjust_account_opening_balance(db, old_amount - amount)
    db.commit()

    row = row_to_dict(db.execute(
        """SELECT et.*, ea.name as account_name, ea.code as account_code, u.name as recorded_by_name
           FROM expense_transactions et
           JOIN expense_accounts ea ON et.account_id=ea.id
           LEFT JOIN users u ON et.recorded_by=u.id
           WHERE et.id=?""",
        (expense_id,),
    ).fetchone())
    db.close()
    audit(
        f"Edited expense {expense_id}",
        "Expenses",
        f"KES {old_amount:,.2f} -> KES {amount:,.2f} - {row.get('account_name')}",
    )
    return success(row, "Expense updated")
@bp.route("/api/expenses/transactions/<expense_id>", methods=["DELETE"])
@login_required
@roles_required("admin", "accountant")
def delete_expense_transaction(expense_id):
    db = get_db()
    row = row_to_dict(db.execute(
        """SELECT et.*, ea.name as account_name
           FROM expense_transactions et
           JOIN expense_accounts ea ON et.account_id=ea.id
           WHERE et.id=?""",
        (expense_id,),
    ).fetchone())
    if not row:
        db.close()
        return error("Expense not found", 404)

    db.execute("DELETE FROM expense_transactions WHERE id=?", (expense_id,))
    adjust_account_opening_balance(db, float(row.get("amount") or 0))
    db.commit()
    db.close()
    audit(
        f"Deleted expense {expense_id}",
        "Expenses",
        f"KES {float(row.get('amount') or 0):,.2f} - {row.get('account_name')}"
    )
    return success(msg="Expense deleted")

# ══════════════════════════════════════════════════════════════════════════════
# REPORTS
# ══════════════════════════════════════════════════════════════════════════════
