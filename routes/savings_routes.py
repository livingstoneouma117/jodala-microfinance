from flask import Blueprint

from services.common import *

savings_bp = Blueprint("savings", __name__)
bp = savings_bp

@bp.route("/api/savings", methods=["GET"])
@login_required
def get_savings():
    db   = get_db()
    rows = rows_to_list(db.execute(
        """SELECT m.id, m.name, m.phone, m.status, sa.balance,
           COUNT(st.id) as txn_count
           FROM members m
           LEFT JOIN savings_accounts sa ON m.id=sa.member_id
           LEFT JOIN savings_transactions st ON m.id=st.member_id
           WHERE m.member_type='member'
           GROUP BY m.id ORDER BY sa.balance DESC"""
    ).fetchall())
    db.close()
    return success(rows)



@bp.route("/api/savings/transactions", methods=["GET"])
@login_required
def get_savings_transactions():
    member_id = request.args.get("member_id","")
    q         = request.args.get("q","")
    page      = max(1, int(request.args.get("page",1)))
    limit     = int(request.args.get("limit",15))

    where  = []
    params = []
    if member_id:
        where.append("st.member_id=?"); params.append(member_id)
    if q:
        where.append("(m.name LIKE ? OR st.reference LIKE ?)"); params.extend([f"%{q}%"]*2)

    clause = ("WHERE " + " AND ".join(where)) if where else ""
    db     = get_db()
    total  = db.execute(
        f"SELECT COUNT(*) FROM savings_transactions st JOIN members m ON st.member_id=m.id {clause}", params
    ).fetchone()[0]
    rows   = rows_to_list(db.execute(
        f"""SELECT st.*, m.name as member_name
            FROM savings_transactions st JOIN members m ON st.member_id=m.id
            {clause} ORDER BY st.txn_date DESC, st.created_at DESC LIMIT ? OFFSET ?""",
        params + [limit, (page-1)*limit]
    ).fetchall())
    db.close()
    return success({"transactions": rows, "total": total, "page": page, "limit": limit, "pages": -(-total//limit)})



@bp.route("/api/savings/deposit", methods=["POST"])
@login_required
@roles_required("admin","officer","cashier","accountant")
def savings_deposit():
    d = request.json or {}
    if not d.get("member_id") or not d.get("amount"):
        return error("member_id and amount required")

    amount = float(d["amount"])
    if amount <= 0:
        return error("Amount must be positive")

    db     = get_db()
    member = row_to_dict(db.execute("SELECT * FROM members WHERE id=?", (d["member_id"],)).fetchone())
    if not member:
        db.close(); return error("Member not found")

    new_balance = member["savings"] + amount
    tid = gen_id("ST")
    ref = d.get("reference") or "DEP" + gen_id()

    db.execute("UPDATE members SET savings=? WHERE id=?", (new_balance, d["member_id"]))
    db.execute("UPDATE savings_accounts SET balance=? WHERE member_id=?", (new_balance, d["member_id"]))
    db.execute(
        "INSERT INTO savings_transactions (id,member_id,type,amount,category,txn_date,reference,balance_after,recorded_by) VALUES (?,?,?,?,?,?,?,?,?)",
        (tid, d["member_id"], "deposit", amount, d.get("category","voluntary"),
         d.get("date", date.today().isoformat()), ref, new_balance, g.user["sub"])
    )
    adjust_account_opening_balance(db, amount)
    db.commit()
    db.close()
    audit(f"Recorded deposit {tid}", "Savings", f"KES {amount} for {d['member_id']}")
    return success({"reference": ref, "new_balance": new_balance}, "Deposit recorded", 201)



@bp.route("/api/savings/withdraw", methods=["POST"])
@login_required
@roles_required("admin","officer","cashier","accountant")
def savings_withdraw():
    d = request.json or {}
    if not d.get("member_id") or not d.get("amount"):
        return error("member_id and amount required")

    amount = float(d["amount"])
    if amount <= 0:
        return error("Amount must be positive")
    db     = get_db()
    member = row_to_dict(db.execute("SELECT * FROM members WHERE id=?", (d["member_id"],)).fetchone())
    if not member:
        db.close(); return error("Member not found")
    if member["savings"] < amount:
        db.close(); return error(f"Insufficient balance. Current: KES {member['savings']:,.2f}")

    new_balance = member["savings"] - amount
    tid = gen_id("ST")
    ref = d.get("reference") or "WDR" + gen_id()

    db.execute("UPDATE members SET savings=? WHERE id=?", (new_balance, d["member_id"]))
    db.execute("UPDATE savings_accounts SET balance=? WHERE member_id=?", (new_balance, d["member_id"]))
    db.execute(
        "INSERT INTO savings_transactions (id,member_id,type,amount,category,txn_date,reference,balance_after,recorded_by) VALUES (?,?,?,?,?,?,?,?,?)",
        (tid, d["member_id"], "withdrawal", amount, d.get("category","voluntary"),
         d.get("date", date.today().isoformat()), ref, new_balance, g.user["sub"])
    )
    adjust_account_opening_balance(db, -amount)
    db.commit(); db.close()
    audit(f"Recorded withdrawal {tid}", "Savings", f"KES {amount} for {d['member_id']}")
    return success({"reference": ref, "new_balance": new_balance}, "Withdrawal processed", 201)

# ══════════════════════════════════════════════════════════════════════════════
# EXPENSES
# ══════════════════════════════════════════════════════════════════════════════