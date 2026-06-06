from api import Blueprint

from services.common import *

members_bp = Blueprint("members", __name__)
bp = members_bp


def _normalize_region(value):
    text = (value or "").strip()
    return text.title() if text else None

@bp.route("/api/members", methods=["GET"])
@login_required
def get_members():
    q      = request.args.get("q","").strip()
    status = request.args.get("status","all")
    page   = max(1, int(request.args.get("page",1)))
    limit  = int(request.args.get("limit",10))

    where  = []
    params = []
    if q:
        where.append("(m.name LIKE ? OR m.national_id LIKE ? OR m.phone LIKE ? OR m.email LIKE ?)")
        params.extend([f"%{q}%"] * 4)
    member_type = request.args.get("type","member")
    if member_type in ("member", "borrower"):
        where.append("m.member_type=?")
        params.append(member_type)
    if status != "all":
        where.append("m.status=?")
        params.append(status)

    clause = ("WHERE " + " AND ".join(where)) if where else ""
    db     = get_db()
    total  = db.execute(f"SELECT COUNT(*) FROM members m {clause}", params).fetchone()[0]
    rows   = rows_to_list(db.execute(
        f"SELECT m.*, u.name as created_by_name FROM members m LEFT JOIN users u ON m.created_by=u.id {clause} ORDER BY m.created_at DESC LIMIT ? OFFSET ?",
        params + [limit, (page-1)*limit]
    ).fetchall())
    db.close()
    return success({"members": rows, "total": total, "page": page, "limit": limit, "pages": -(-total//limit)})



@bp.route("/api/members/<member_id>", methods=["GET"])
@login_required
def get_member(member_id):
    db     = get_db()
    member = row_to_dict(db.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone())
    if not member:
        db.close(); return error("Member not found", 404)

    loans       = rows_to_list(db.execute(
        "SELECT * FROM loans WHERE member_id=? ORDER BY created_at DESC", (member_id,)
    ).fetchall())
    savings_txn = rows_to_list(db.execute(
        "SELECT * FROM savings_transactions WHERE member_id=? ORDER BY txn_date DESC LIMIT 20", (member_id,)
    ).fetchall())
    repayments = rows_to_list(db.execute(
        "SELECT * FROM repayments WHERE member_id=? ORDER BY payment_date DESC LIMIT 30", (member_id,)
    ).fetchall())
    db.close()
    return success({"member": member, "loans": loans, "savings_transactions": savings_txn, "repayments": repayments})



@bp.route("/api/members", methods=["POST"])
@login_required
@roles_required("admin","officer")
def create_member():
    d = request.json or {}
    required = ["name","joined_date"]
    if not all(d.get(k) for k in required):
        return error("Name and join date are required")

    member_type = d.get("member_type", "member")
    prefix = "B" if member_type == "borrower" else "M"
    mid = gen_id(prefix)
    national_id = d.get("national_id") or gen_id(f"{prefix}ID")
    db  = get_db()
    try:
        db.execute(
            """INSERT INTO members (id,name,phone,email,national_id,gender,dob,region,status,joined_date,savings,created_by,member_type)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (mid, d["name"], d.get("phone"), d.get("email"), national_id,
                d.get("gender"), d.get("dob"), _normalize_region(d.get("region")), d.get("status","active"),
                d["joined_date"], 0, g.user["sub"], member_type)
        )
        db.execute("INSERT INTO savings_accounts (member_id,balance) VALUES (?,?)", (mid, 0))
        db.commit()
    except sqlite3.IntegrityError:
        db.close(); return error("National ID already exists")

    audit(f"Registered {member_type} {mid}", "Members", d["name"])
    member = row_to_dict(db.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone())
    db.close()
    return success(member, "Record registered", 201)



@bp.route("/api/members/<member_id>", methods=["PUT"])
@login_required
@roles_required("admin","officer")
def update_member(member_id):
    d  = request.json or {}
    db = get_db()
    db.execute(
        """UPDATE members SET name=COALESCE(?,name), phone=COALESCE(?,phone),
           email=COALESCE(?,email), gender=COALESCE(?,gender), dob=COALESCE(?,dob),
           region=COALESCE(?,region), status=COALESCE(?,status)
           WHERE id=?""",
        (d.get("name"), d.get("phone"), d.get("email"), d.get("gender"),
         d.get("dob"), _normalize_region(d.get("region")), d.get("status"), member_id)
    )
    db.commit()
    member = row_to_dict(db.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone())
    db.close()
    audit(f"Updated member {member_id}", "Members")
    return success(member, "Member updated")



@bp.route("/api/members/<member_id>/status", methods=["PATCH"])
@login_required
@roles_required("admin")
def toggle_member_status(member_id):
    d      = request.json or {}
    status = d.get("status","active")
    db     = get_db()
    db.execute("UPDATE members SET status=? WHERE id=?", (status, member_id))
    db.commit(); db.close()
    audit(f"Changed member {member_id} status to {status}", "Members")
    return success(msg=f"Member status set to {status}")



@bp.route("/api/members/<member_id>", methods=["DELETE"])
@login_required
@roles_required("admin")
def delete_member(member_id):
    db = get_db()
    member = row_to_dict(db.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone())
    if not member:
        db.close(); return error("Record not found", 404)
    loan_ids = [r["id"] for r in db.execute("SELECT id FROM loans WHERE member_id=?", (member_id,)).fetchall()]
    try:
        for lid in loan_ids:
            db.execute("DELETE FROM loan_schedule WHERE loan_id=?", (lid,))
            db.execute("DELETE FROM repayments WHERE loan_id=?", (lid,))
        db.execute("DELETE FROM loans WHERE member_id=?", (member_id,))
        db.execute("DELETE FROM savings_transactions WHERE member_id=?", (member_id,))
        db.execute("DELETE FROM savings_accounts WHERE member_id=?", (member_id,))
        db.execute("DELETE FROM guarantors WHERE member_id=? OR guarantor_id=?", (member_id, member_id))
        db.execute("DELETE FROM members WHERE id=?", (member_id,))
        db.commit()
    except sqlite3.IntegrityError:
        db.close(); return error("Unable to delete record with linked activity", 409)
    db.close()
    audit(f"Deleted {member.get('member_type','member')} {member_id}", "Members", member.get("name",""))
    return success(msg="Record deleted")



@bp.route("/api/borrowers", methods=["GET"])
@login_required
def get_borrowers():
    q      = request.args.get("q","").strip()
    status = request.args.get("status","all")
    page   = max(1, int(request.args.get("page",1)))
    limit  = int(request.args.get("limit",10))
    where  = ["m.member_type='borrower'"]
    params = []
    if q:
        where.append("(m.name LIKE ? OR m.national_id LIKE ? OR m.phone LIKE ? OR m.email LIKE ?)")
        params.extend([f"%{q}%"] * 4)
    if status != "all":
        where.append("m.status=?")
        params.append(status)
    clause = "WHERE " + " AND ".join(where)
    db     = get_db()
    total  = db.execute(f"SELECT COUNT(*) FROM members m {clause}", params).fetchone()[0]
    rows   = rows_to_list(db.execute(
        f"SELECT m.*, u.name as created_by_name FROM members m LEFT JOIN users u ON m.created_by=u.id {clause} ORDER BY m.created_at DESC LIMIT ? OFFSET ?",
        params + [limit, (page-1)*limit]
    ).fetchall())
    db.close()
    return success({"borrowers": rows, "total": total, "page": page, "limit": limit, "pages": -(-total//limit)})



@bp.route("/api/borrowers", methods=["POST"])
@login_required
@roles_required("admin","officer")
def create_borrower():
    d = request.json or {}
    d = {**d, "member_type": "borrower", "joined_date": d.get("joined_date") or date.today().isoformat()}
    if not d.get("name"):
        return error("Name is required")
    bid = gen_id("B")
    national_id = d.get("national_id") or gen_id("BID")
    db = get_db()
    try:
        db.execute(
            """INSERT INTO members (id,name,phone,email,national_id,gender,dob,region,status,joined_date,savings,created_by,member_type)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (bid, d["name"], d.get("phone"), d.get("email"), national_id,
             d.get("gender"), d.get("dob"), _normalize_region(d.get("region")), d.get("status","active"),
             d["joined_date"], 0, g.user["sub"], "borrower")
        )
        db.execute("INSERT INTO savings_accounts (member_id,balance) VALUES (?,?)", (bid, 0))
        db.commit()
    except sqlite3.IntegrityError:
        db.close(); return error("Borrower already exists")
    borrower = row_to_dict(db.execute("SELECT * FROM members WHERE id=?", (bid,)).fetchone())
    db.close()
    audit(f"Registered borrower {bid}", "Borrowers", d["name"])
    return success(borrower, "Borrower registered", 201)

# ══════════════════════════════════════════════════════════════════════════════
# LOAN PRODUCTS
# ══════════════════════════════════════════════════════════════════════════════

