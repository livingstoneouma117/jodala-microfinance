from flask import Blueprint

from services.common import *

repayments_bp = Blueprint("repayments", __name__)
bp = repayments_bp

@bp.route("/api/repayments", methods=["GET"])
@login_required
def get_repayments():
    q     = request.args.get("q","").strip()
    page  = max(1, int(request.args.get("page",1)))
    limit = int(request.args.get("limit",10))

    where  = []
    params = []
    if q:
        where.append("(r.id LIKE ? OR r.loan_id LIKE ? OR m.name LIKE ? OR r.reference LIKE ?)")
        params.extend([f"%{q}%"] * 4)

    clause = ("WHERE " + " AND ".join(where)) if where else ""
    db     = get_db()
    total  = db.execute(
        f"SELECT COUNT(*) FROM repayments r JOIN members m ON r.member_id=m.id {clause}", params
    ).fetchone()[0]
    rows   = rows_to_list(db.execute(
        f"""SELECT r.*, m.name as member_name, u.name as recorded_by_name
            FROM repayments r
            JOIN members m ON r.member_id=m.id
            LEFT JOIN users u ON r.recorded_by=u.id
            {clause} ORDER BY r.payment_date DESC, r.created_at DESC LIMIT ? OFFSET ?""",
        params + [limit, (page-1)*limit]
    ).fetchall())
    db.close()
    return success({"repayments": rows, "total": total, "page": page, "limit": limit, "pages": -(-total//limit)})



@bp.route("/api/repayments", methods=["POST"])
@login_required
@roles_required("admin","officer","cashier")
def create_repayment():
    d = request.json or {}
    required = ["loan_id","amount","payment_date"]
    if not all(d.get(k) for k in required):
        return error("Required: loan_id, amount, payment_date")

    amount = float(d["amount"])
    if amount <= 0:
        return error("Amount must be positive")

    db   = get_db()
    refresh_loan_statuses(db)
    db.commit()
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (d["loan_id"],)).fetchone())
    if not loan:
        db.close(); return error("Loan not found")
    if loan["status"] not in ("active","overdue"):
        db.close(); return error("Loan is not active")

    rid = gen_id("R")
    method = d.get("method","cash")
    ref = d.get("reference") or (
        "QK" + gen_id() if method=="mpesa" else
        "BNK" + gen_id() if method=="bank" else
        "CSH" + gen_id()
    )
    if ref and db.execute("SELECT id FROM repayments WHERE reference=?", (ref,)).fetchone():
        db.close(); return error("A repayment with this reference already exists")

    schedule = rows_to_list(db.execute(
        "SELECT * FROM loan_schedule WHERE loan_id=? ORDER BY installment", (loan["id"],)
    ).fetchall())
    if not schedule:
        db.close(); return error("Loan has no repayment schedule. Disburse it first.")
    total_repayable = sum(float(r["repayment"] or 0) for r in schedule)
    outstanding = max(0, total_repayable - float(loan["total_paid"] or 0))
    if amount > outstanding + 0.01:
        db.close(); return error(f"Payment exceeds outstanding balance of KES {outstanding:,.2f}")

    db.execute(
        "INSERT INTO repayments (id,loan_id,member_id,amount,payment_date,method,reference,type,recorded_by) VALUES (?,?,?,?,?,?,?,?,?)",
        (rid, loan["id"], loan["member_id"], amount, d["payment_date"],
         method, ref, d.get("type","installment"), g.user["sub"])
    )
    adjust_account_opening_balance(db, amount)

    allocate_repayment_to_schedule(db, loan["id"], d["payment_date"])

    db.commit()
    repayment = row_to_dict(db.execute("SELECT * FROM repayments WHERE id=?", (rid,)).fetchone())
    db.close()
    audit(f"Recorded repayment {rid}", "Repayments", f"KES {amount} for loan {loan['id']}")
    return success({**repayment, "reference": ref}, "Repayment recorded", 201)

# ══════════════════════════════════════════════════════════════════════════════
# SAVINGS
# ══════════════════════════════════════════════════════════════════════════════