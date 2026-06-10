from api import Blueprint

from services.common import *

loans_bp = Blueprint("loans", __name__)
bp = loans_bp

def _loan_product_payload(d, existing=None):
    settings = get_settings_dict()
    name = (d.get("name") or (existing or {}).get("name") or "").strip()
    method = (d.get("method") or (existing or {}).get("method") or "reducing").strip().lower()
    if method not in {"reducing", "flat"}:
        raise ValueError("Method must be reducing or flat")
    if not name:
        raise ValueError("Product name is required")
    min_amount = float(d.get("min_amount", (existing or {}).get("min_amount", 0)) or 0)
    max_amount = float(d.get("max_amount", (existing or {}).get("max_amount", 0)) or 0)
    min_term = int(d.get("min_term", (existing or {}).get("min_term", 1)) or 1)
    max_term = int(d.get("max_term", (existing or {}).get("max_term", 1)) or 1)
    annual_rate = float(d.get("annual_rate", (existing or {}).get("annual_rate", 0)) or 0)
    penalty_default = float(settings.get("default_penalty_rate") or 5)
    penalty_rate = float(d.get("penalty_rate", (existing or {}).get("penalty_rate", penalty_default)) or penalty_default)
    active = 1 if bool(d.get("active", (existing or {}).get("active", 1))) else 0
    if min_amount < 0 or max_amount <= 0 or max_amount < min_amount:
        raise ValueError("Amounts must be valid and max amount must be at least min amount")
    if min_term <= 0 or max_term < min_term:
        raise ValueError("Terms must be valid and max term must be at least min term")
    if annual_rate < 0 or penalty_rate < 0:
        raise ValueError("Rates cannot be negative")
    return {
        "name": name,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "min_term": min_term,
        "max_term": max_term,
        "annual_rate": annual_rate,
        "method": method,
        "penalty_rate": penalty_rate,
        "active": active,
    }


@bp.route("/api/loan-products", methods=["GET"])
@login_required
def get_loan_products():
    include_inactive = request.args.get("include_inactive") in {"1", "true", "yes"}
    db = get_db()
    rows = rows_to_list(db.execute(
        "SELECT * FROM loan_products ORDER BY active DESC, name" if include_inactive else "SELECT * FROM loan_products WHERE active=1 ORDER BY name"
    ).fetchall())
    db.close()
    return success(rows)


@bp.route("/api/loan-products", methods=["POST"])
@login_required
@roles_required("admin")
def create_loan_product():
    try:
        payload = _loan_product_payload(request.json or {})
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    db = get_db()
    db.execute(
        """INSERT INTO loan_products (name,min_amount,max_amount,min_term,max_term,annual_rate,method,penalty_rate,active)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (payload["name"], payload["min_amount"], payload["max_amount"], payload["min_term"], payload["max_term"],
         payload["annual_rate"], payload["method"], payload["penalty_rate"], payload["active"])
    )
    db.commit()
    product = row_to_dict(db.execute("SELECT * FROM loan_products WHERE id=last_insert_rowid()").fetchone())
    db.close()
    audit(f"Created loan product {product['name']}", "Loan Products")
    return success(product, "Loan product created", 201)


@bp.route("/api/loan-products/<int:product_id>", methods=["PUT"])
@login_required
@roles_required("admin")
def update_loan_product(product_id):
    db = get_db()
    existing = row_to_dict(db.execute("SELECT * FROM loan_products WHERE id=?", (product_id,)).fetchone())
    if not existing:
        db.close(); return error("Loan product not found", 404)
    try:
        payload = _loan_product_payload(request.json or {}, existing)
    except (ValueError, TypeError) as exc:
        db.close(); return error(str(exc))
    db.execute(
        """UPDATE loan_products
           SET name=?, min_amount=?, max_amount=?, min_term=?, max_term=?, annual_rate=?, method=?, penalty_rate=?, active=?
           WHERE id=?""",
        (payload["name"], payload["min_amount"], payload["max_amount"], payload["min_term"], payload["max_term"],
         payload["annual_rate"], payload["method"], payload["penalty_rate"], payload["active"], product_id)
    )
    db.commit()
    product = row_to_dict(db.execute("SELECT * FROM loan_products WHERE id=?", (product_id,)).fetchone())
    db.close()
    audit(f"Updated loan product {product['name']}", "Loan Products")
    return success(product, "Loan product updated")


@bp.route("/api/loan-products/<int:product_id>/status", methods=["PATCH"])
@login_required
@roles_required("admin")
def set_loan_product_status(product_id):
    active = 1 if (request.json or {}).get("active") else 0
    db = get_db()
    product = row_to_dict(db.execute("SELECT * FROM loan_products WHERE id=?", (product_id,)).fetchone())
    if not product:
        db.close(); return error("Loan product not found", 404)
    db.execute("UPDATE loan_products SET active=? WHERE id=?", (active, product_id))
    db.commit()
    updated = row_to_dict(db.execute("SELECT * FROM loan_products WHERE id=?", (product_id,)).fetchone())
    db.close()
    audit(f"{'Activated' if active else 'Deactivated'} loan product {product['name']}", "Loan Products")
    return success(updated, "Loan product activated" if active else "Loan product deactivated")

# ══════════════════════════════════════════════════════════════════════════════
# LOANS
# ══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/loans", methods=["GET"])
@login_required
def get_loans():
    q      = request.args.get("q","").strip()
    status = request.args.get("status","all")
    page   = max(1, int(request.args.get("page",1)))
    limit  = int(request.args.get("limit",10))

    where  = []
    params = []
    if q:
        where.append("(l.id LIKE ? OR l.member_id LIKE ? OR m.name LIKE ? OR l.purpose LIKE ?)")
        params.extend([f"%{q}%"] * 4)
    if status == "open":
        # Backward compatibility for old clients that still send status=open.
        status = "all"
    if status != "all":
        where.append("l.status=?")
        params.append(status)

    clause = ("WHERE " + " AND ".join(where)) if where else ""
    db     = get_db()
    refresh_loan_statuses(db)
    db.commit()
    total  = db.execute(
        f"SELECT COUNT(*) FROM loans l JOIN members m ON l.member_id=m.id {clause}", params
    ).fetchone()[0]
    rows   = rows_to_list(db.execute(
        f"""SELECT l.*, m.name as member_name, m.phone as member_phone,
            u.name as officer_name,
            COALESCE(l.disbursed_date, l.approved_date, l.applied_date) as borrowed_date,
            CASE WHEN l.status='written_off' THEN NULL ELSE risk.next_due_date END as next_due_date,
            CASE WHEN l.status='written_off' THEN 0 ELSE COALESCE(risk.amount_in_arrears,0) END as amount_in_arrears,
            CASE WHEN l.status='written_off' THEN 0 ELSE COALESCE(risk.overdue_installments,0) END as overdue_installments,
            CASE WHEN l.status='written_off' THEN NULL ELSE risk.oldest_due_date END as oldest_due_date,
            CASE WHEN l.status='written_off' THEN 0 ELSE COALESCE(CAST(julianday(date('now')) - julianday(risk.oldest_due_date) AS INTEGER),0) END as days_in_arrears,
            CASE
                WHEN l.status='written_off' THEN 0
                WHEN l.restructure_snapshot_outstanding IS NOT NULL AND l.restructure_snapshot_paid IS NOT NULL
                    THEN MAX(l.restructure_snapshot_outstanding - (l.total_paid - COALESCE(l.restructure_snapshot_paid, 0)), 0)
                ELSE MAX(COALESCE(risk.total_repayable, l.amount) + COALESCE(l.penalties,0) - l.total_paid, 0)
            END as outstanding
            FROM loans l
            JOIN members m ON l.member_id=m.id
            LEFT JOIN users u ON l.officer_id=u.id
            LEFT JOIN (
                SELECT loan_id,
                       SUM(repayment) as total_repayable,
                       MIN(CASE WHEN paid=0 THEN due_date END) as next_due_date,
                       MIN(CASE WHEN paid=0 AND due_date < date('now') THEN due_date END) as oldest_due_date,
                       SUM(CASE WHEN paid=0 AND due_date < date('now') THEN repayment + COALESCE(penalty,0) ELSE 0 END) as amount_in_arrears,
                       COUNT(CASE WHEN paid=0 AND due_date < date('now') THEN 1 END) as overdue_installments
                FROM loan_schedule
                GROUP BY loan_id
            ) risk ON risk.loan_id=l.id
            {clause} ORDER BY l.created_at DESC LIMIT ? OFFSET ?""",
        params + [limit, (page-1)*limit]
    ).fetchall())
    db.close()
    return success({"loans": rows, "total": total, "page": page, "limit": limit, "pages": -(-total//limit)})



@bp.route("/api/loans/<loan_id>", methods=["GET"])
@login_required
def get_loan(loan_id):
    db   = get_db()
    refresh_loan_statuses(db)
    db.commit()
    loan = row_to_dict(db.execute(
        """SELECT l.*, m.name as member_name, m.phone as member_phone, m.email as member_email,
                  COALESCE(l.disbursed_date, l.approved_date, l.applied_date) as borrowed_date
           FROM loans l JOIN members m ON l.member_id=m.id
           WHERE l.id=?""", (loan_id,)
    ).fetchone())
    if not loan:
        db.close(); return error("Loan not found", 404)

    schedule = rows_to_list(db.execute(
        "SELECT * FROM loan_schedule WHERE loan_id=? ORDER BY installment", (loan_id,)
    ).fetchall())
    repays = rows_to_list(db.execute(
        "SELECT * FROM repayments WHERE loan_id=? ORDER BY payment_date DESC", (loan_id,)
    ).fetchall())
    guarantors = rows_to_list(db.execute(
        """SELECT g.*, gm.name AS guarantor_name, gm.phone AS guarantor_phone, gm.savings AS guarantor_savings
           FROM guarantors g
           JOIN members gm ON gm.id=g.guarantor_id
           WHERE (g.loan_id=? OR (g.loan_id IS NULL AND g.member_id=?))
           ORDER BY g.created_at DESC, g.id DESC""",
        (loan_id, loan.get("member_id")),
    ).fetchall())
    risk = loan_risk_snapshot(db, loan_id)
    db.close()

    summary = loan_summary(loan, schedule)
    return success({"loan": loan, "schedule": schedule, "repayments": repays, "guarantors": guarantors, "summary": summary, "risk": risk})



@bp.route("/api/loans/<loan_id>/statement", methods=["GET"])
@login_required
def loan_statement(loan_id):
    data = get_loan_statement_data(loan_id)
    if not data:
        return error("Loan not found", 404)
    if (request.args.get("format") or "").strip().lower() == "pdf" or request.args.get("download") in {"1", "true", "yes"}:
        pdf = build_statement_pdf(loan_id, data)
        return send_file(
            BytesIO(pdf),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"loan-statement-{loan_id}.pdf",
        )
    loan = data["loan"]
    schedule = data["schedule"]
    repays = data["repays"]
    settings = data["settings"]
    summary = data["summary"]
    schedule_rows = "".join(
        f"<tr><td>{r['installment']}</td><td>{escape(str(r['due_date']))}</td><td>{r['principal']:,.2f}</td><td>{r['interest']:,.2f}</td><td>{r['repayment']:,.2f}</td><td>{float(r.get('penalty') or 0):,.2f}</td><td>{r['balance']:,.2f}</td></tr>"
        for r in schedule
    ) or "<tr><td colspan='7'>Schedule will be available after approval.</td></tr>"
    repay_rows = "".join(
        f"<tr><td>{escape(str(r['payment_date']))}</td><td>{escape(str(r.get('reference') or r['id']))}</td><td>{escape(str(r['method']))}</td><td>{r['amount']:,.2f}</td></tr>"
        for r in repays
    ) or "<tr><td colspan='4'>No repayments recorded.</td></tr>"
    logo_image = settings.get("logo_image") or ""
    logo_url = settings.get("logo_url") or ""
    logo_src = logo_image or logo_url
    logo = f"<img src='{escape(logo_src)}' alt='Logo'/>" if logo_src else f"<div class='mark'>{escape(settings.get('logo_text') or 'SF')}</div>"
    html = f"""<!doctype html><html><head><meta charset='utf-8'><title>Loan Statement {escape(loan_id)}</title>
    <style>
    @page {{ size: A5; margin: 10mm; }}
    body {{ font-family: Arial, sans-serif; color:#172033; font-size:10px; }}
    .head {{ display:flex; justify-content:space-between; align-items:flex-start; border-bottom:2px solid #172033; padding-bottom:8px; margin-bottom:10px; }}
    .brand {{ display:flex; gap:8px; align-items:center; }}
    .mark {{ width:34px; height:34px; background:#172033; color:white; display:flex; align-items:center; justify-content:center; font-weight:700; border-radius:6px; }}
    img {{ max-width:42px; max-height:42px; object-fit:contain; }}
    h1 {{ font-size:15px; margin:0; }} h2 {{ font-size:11px; margin:10px 0 5px; }}
    .muted {{ color:#64748b; }} .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:6px; }}
    .box {{ border:1px solid #d7dde8; padding:6px; border-radius:5px; }}
    table {{ width:100%; border-collapse:collapse; margin-top:5px; }} th,td {{ border:1px solid #d7dde8; padding:4px; text-align:left; }}
    th {{ background:#eef2f7; }} .right {{ text-align:right; }} .print {{ position:fixed; right:12px; top:12px; }}
    @media print {{ .print {{ display:none; }} }}
    </style></head><body><button class='print' onclick='print()'>Print / Save PDF</button>
    <div class='head'><div class='brand'>{logo}<div><h1>{escape(settings.get('sacco_name') or 'SACCOFinance')}</h1>
    <div class='muted'>{escape(settings.get('address') or '')}</div><div class='muted'>{escape(settings.get('phone') or '')}</div></div></div>
    <div class='right'><strong>A5 Loan Statement</strong><div>{date.today().isoformat()}</div><div>{escape(loan_id)}</div></div></div>
    <div class='grid'>
    <div class='box'><strong>{'External Borrower' if loan.get('member_type') == 'borrower' else 'Member'}</strong><br>{escape(loan['member_name'])}<br>{escape(loan.get('member_phone') or '')}<br>{escape(loan.get('member_address') or '')}</div>
    <div class='box'><strong>Loan Summary</strong><br>Principal: KES {loan['amount']:,.2f}<br>Rate: {loan['annual_rate']}% p.m.<br>Term: {loan['term_months']} months<br>Penalties: KES {summary['penalties']:,.2f}<br>Status: {escape(loan['status'])}</div>
    <div class='box'>Total Repayable<br><strong>KES {summary['total_repayable']:,.2f}</strong></div>
    <div class='box'>Outstanding<br><strong>KES {summary['outstanding']:,.2f}</strong></div>
    </div>
    <h2>Repayment Schedule</h2><table><thead><tr><th>#</th><th>Due</th><th>Principal</th><th>Interest</th><th>Payment</th><th>Penalty</th><th>Balance</th></tr></thead><tbody>{schedule_rows}</tbody></table>
    <h2>Repayments</h2><table><thead><tr><th>Date</th><th>Reference</th><th>Method</th><th>Amount</th></tr></thead><tbody>{repay_rows}</tbody></table>
    <script>setTimeout(()=>window.print(),300)</script></body></html>"""
    return make_response(html)



@bp.route("/api/loans/<loan_id>/statement.pdf", methods=["GET"])
@login_required
def loan_statement_pdf(loan_id):
    data = get_loan_statement_data(loan_id)
    if not data:
        return error("Loan not found", 404)
    pdf = build_statement_pdf(loan_id, data)
    filename = f"loan-statement-{loan_id}.pdf"
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )



@bp.route("/api/loans", methods=["POST"])
@login_required
@roles_required("admin","officer")
def create_loan():
    d = request.json or {}
    required = ["member_id","amount","annual_rate","term_months","applied_date"]
    if not all(d.get(k) for k in required):
        return error("Required: member_id, amount, annual_rate, term_months, applied_date")
    borrowed_date = clean_date(d.get("applied_date"))

    db  = get_db()
    member = db.execute("SELECT id FROM members WHERE id=? AND status='active'", (d["member_id"],)).fetchone()
    if not member:
        db.close(); return error("Member not found or inactive")

    topup_loan = row_to_dict(db.execute(
        """SELECT * FROM loans
           WHERE member_id=? AND status IN ('active','overdue')
           ORDER BY COALESCE(disbursed_date, applied_date, created_at) DESC, created_at DESC
           LIMIT 1""",
        (d["member_id"],)
    ).fetchone())

    if topup_loan:
        added_amount = float(d["amount"])
        if added_amount <= 0:
            db.close(); return error("Top-up amount must be greater than zero")

        paid_installments = int(db.execute(
            "SELECT COUNT(*) FROM loan_schedule WHERE loan_id=? AND paid=1",
            (topup_loan["id"],)
        ).fetchone()[0] or 0)
        remaining_term = max(1, int(topup_loan.get("term_months") or 1) - paid_installments)
        base_amount = float(topup_loan.get("amount") or 0)
        new_amount = base_amount + added_amount
        new_status = topup_loan["status"]
        db.execute(
            """UPDATE loans
               SET amount=?, applied_date=?, disbursed_date=?, officer_id=?,
                   restructure_snapshot_outstanding=NULL, restructure_snapshot_paid=NULL
               WHERE id=?""",
            (new_amount,
             borrowed_date, borrowed_date if topup_loan["status"] in ("active", "overdue") else topup_loan.get("disbursed_date"),
             g.user["sub"], topup_loan["id"])
        )
        loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (topup_loan["id"],)).fetchone())
        loan["amount"] = new_amount
        loan["term_months"] = remaining_term

        if loan["status"] in ("active", "overdue"):
            start_date = borrowed_date
            rebuild_loan_schedule(db, loan, start_date)
            total_repayable = db.execute(
                "SELECT COALESCE(SUM(repayment),0) + COALESCE((SELECT penalties FROM loans WHERE id=?),0) FROM loan_schedule WHERE loan_id=?",
                (loan["id"], loan["id"])
            ).fetchone()[0]
            if float(loan.get("total_paid") or 0) >= float(total_repayable):
                new_status = "completed"
            db.execute("UPDATE loans SET status=? WHERE id=?", (new_status, loan["id"]))
            loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan["id"],)).fetchone())
            loan["amount"] = new_amount
            loan["term_months"] = remaining_term
            # Top-up on an active/overdue loan represents new funds released.
            adjust_account_opening_balance(db, -added_amount)

        db.commit()
        db.close()
        audit(
            f"Added top-up to loan {loan['id']}",
            "Loans",
            f"Added KES {added_amount}; new principal KES {new_amount} for {d['member_id']}"
        )
        return success(loan, f"Top-up added to existing loan {loan['id']}")

    for _ in range(3):
        lid = next_loan_id(db)
        try:
            db.execute(
                """INSERT INTO loans (id,member_id,product_id,amount,annual_rate,term_months,method,
                   purpose,status,applied_date,officer_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (lid, d["member_id"], d.get("product_id"), float(d["amount"]),
                 float(d["annual_rate"]), int(d["term_months"]), d.get("method","reducing"),
                 d.get("purpose"), "pending", borrowed_date, g.user["sub"])
            )
            break
        except sqlite3.IntegrityError:
            lid = None
    if not lid:
        db.close(); return error("Could not generate a new loan ID. Please try again.")
    db.commit()
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (lid,)).fetchone())
    db.close()
    audit(f"Created loan application {lid}", "Loans", f"KES {d['amount']} for {d['member_id']}")
    return success(loan, "Loan application submitted", 201)



@bp.route("/api/loans/<loan_id>", methods=["PUT"])
@login_required
@roles_required("admin","officer")
def update_loan_application(loan_id):
    d = request.json or {}
    required = ["member_id","amount","annual_rate","term_months","applied_date"]
    if not all(d.get(k) for k in required):
        return error("Required: member_id, amount, annual_rate, term_months, applied_date")
    borrowed_date = clean_date(d.get("applied_date"))

    db = get_db()
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    if not loan:
        db.close(); return error("Loan not found", 404)
    status = (loan.get("status") or "").lower()
    if status not in {"pending", "approved", "rejected"}:
        db.close(); return error("Only pending, approved, or rejected loans can be edited")
    if loan.get("disbursed_date"):
        db.close(); return error("Disbursed loans cannot be edited")

    member = db.execute("SELECT id FROM members WHERE id=? AND status='active'", (d["member_id"],)).fetchone()
    if not member:
        db.close(); return error("Member or external borrower not found or inactive")

    # Editing an approved/rejected loan returns it to pending so it can be reviewed again.
    new_status = "pending" if status in {"approved", "rejected"} else "pending"
    approved_date = None if status in {"approved", "rejected"} else loan.get("approved_date")
    approved_by = None if status in {"approved", "rejected"} else loan.get("approved_by")

    db.execute(
        """UPDATE loans
           SET member_id=?, product_id=?, amount=?, annual_rate=?, term_months=?,
               method=?, purpose=?, applied_date=?, officer_id=?, status=?, approved_date=?, approved_by=?
           WHERE id=?""",
        (d["member_id"], d.get("product_id"), float(d["amount"]), float(d["annual_rate"]),
         int(d["term_months"]), d.get("method","reducing"), d.get("purpose"),
         borrowed_date, g.user["sub"], new_status, approved_date, approved_by, loan_id)
    )
    db.commit()
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    db.close()
    audit(f"Updated loan application {loan_id}", "Loans", f"KES {d['amount']} for {d['member_id']}")
    if status in {"approved", "rejected"}:
        return success(loan, "Loan updated and moved to pending for review")
    return success(loan, "Loan application updated")



@bp.route("/api/loans/<loan_id>", methods=["DELETE"])
@login_required
@roles_required("admin","officer")
def delete_loan(loan_id):
    db = get_db()
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    if not loan:
        db.close(); return error("Loan not found", 404)

    status = (loan.get("status") or "").lower()
    if status not in {"pending", "approved", "rejected"}:
        db.close(); return error("Only pending, approved, or rejected loans can be deleted")
    if loan.get("disbursed_date"):
        db.close(); return error("Disbursed loans cannot be deleted")

    repayment_count = db.execute(
        "SELECT COUNT(*) FROM repayments WHERE loan_id=?",
        (loan_id,),
    ).fetchone()[0]
    if repayment_count > 0:
        db.close(); return error("Loans with repayments cannot be deleted")

    db.execute("DELETE FROM loan_schedule WHERE loan_id=?", (loan_id,))
    db.execute("DELETE FROM repayments WHERE loan_id=?", (loan_id,))
    db.execute("DELETE FROM notifications WHERE message LIKE ?", (f"%{loan_id}%",))
    db.execute("DELETE FROM loans WHERE id=?", (loan_id,))
    db.commit()
    db.close()
    audit(f"Deleted loan {loan_id}", "Loans", f"Status was {status}")
    return success(msg="Loan deleted")



@bp.route("/api/loans/<loan_id>/approve", methods=["POST"])
@login_required
@roles_required("admin")
def approve_loan(loan_id):
    db  = get_db()
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    if not loan:
        db.close(); return error("Loan not found", 404)
    if loan["status"] == "approved":
        db.close(); return success(msg="Loan already approved")
    if loan["status"] != "pending":
        db.close(); return error("Only pending loans can be approved")

    payload = request.json or {}
    approved_date = clean_date(payload.get("approved_date"), date.today().isoformat())
    if int(loan["term_months"]) <= 0:
        db.close(); return error("Loan term must be at least 1 month")
    if float(loan["amount"]) <= 0:
        db.close(); return error("Loan amount must be greater than zero")
    db.execute(
        "UPDATE loans SET status='approved', approved_date=?, approved_by=? WHERE id=?",
        (approved_date, g.user["sub"], loan_id)
    )

    # Notification
    db.execute(
        "INSERT INTO notifications (user_id,type,message) VALUES (?,?,?)",
        (loan["officer_id"] or g.user["sub"], "approved", f"Loan {loan_id} approved — KES {loan['amount']:,.0f}")
    )
    db.commit(); db.close()
    audit(f"Approved loan {loan_id}", "Loans", f"KES {loan['amount']}")
    return success(msg="Loan approved. Disburse when funds are released.")



@bp.route("/api/loans/<loan_id>/disburse", methods=["POST"])
@login_required
@roles_required("admin","officer","accountant")
def disburse_loan(loan_id):
    d = request.json or {}
    disbursed_date = clean_date(d.get("disbursed_date"), date.today().isoformat())
    db  = get_db()
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    if not loan:
        db.close(); return error("Loan not found", 404)
    if loan["status"] == "active":
        db.close(); return success(msg="Loan already disbursed")
    if loan["status"] != "approved":
        db.close(); return error("Only approved loans can be disbursed")
    if float(loan["amount"]) <= 0 or int(loan["term_months"]) <= 0:
        db.close(); return error("Loan amount and term must be valid before disbursement")

    db.execute(
        "UPDATE loans SET status='active', disbursed_date=?, notes=COALESCE(NULLIF(?,''),notes) WHERE id=?",
        (disbursed_date, d.get("reference") or d.get("notes") or "", loan_id)
    )
    adjust_account_opening_balance(db, -float(loan["amount"] or 0))
    loan_for_schedule = {**loan, "status": "active", "disbursed_date": disbursed_date}
    rebuild_loan_schedule(db, loan_for_schedule, disbursed_date)
    db.execute(
        "INSERT INTO notifications (user_id,type,message) VALUES (?,?,?)",
        (loan["officer_id"] or g.user["sub"], "disbursed", f"Loan {loan_id} disbursed — KES {loan['amount']:,.0f}")
    )
    db.commit(); db.close()
    audit(f"Disbursed loan {loan_id}", "Loans", f"KES {loan['amount']} on {disbursed_date}")
    return success(msg="Loan disbursed and repayment schedule generated")



@bp.route("/api/loans/<loan_id>/reject", methods=["POST"])
@login_required
@roles_required("admin")
def reject_loan(loan_id):
    d    = request.json or {}
    db   = get_db()
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    if not loan or loan["status"] != "pending":
        db.close(); return error("Loan not found or not pending")
    db.execute("UPDATE loans SET status='rejected', notes=? WHERE id=?", (d.get("reason",""), loan_id))
    db.commit(); db.close()
    audit(f"Rejected loan {loan_id}", "Loans", d.get("reason",""))
    return success(msg="Loan rejected")


@bp.route("/api/loans/<loan_id>/write-off", methods=["POST"])
@login_required
@roles_required("admin", "accountant")
def write_off_loan(loan_id):
    d = request.json or {}
    reason = (d.get("reason") or "").strip()
    if not reason:
        return error("Write-off reason is required")
    write_off_date = clean_date(d.get("write_off_date"), date.today().isoformat())

    db = get_db()
    refresh_loan_statuses(db)
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    if not loan:
        db.close(); return error("Loan not found", 404)

    status = (loan.get("status") or "").lower()
    if status == "written_off":
        db.close(); return success(loan, "Loan already written off")
    if status not in {"active", "overdue"}:
        db.close(); return error("Only active or overdue loans with an outstanding balance can be written off")

    schedule = rows_to_list(db.execute("SELECT * FROM loan_schedule WHERE loan_id=? ORDER BY installment", (loan_id,)).fetchall())
    summary = loan_summary(loan, schedule)
    outstanding = float(summary.get("outstanding") or 0)
    if outstanding <= 0.01:
        db.close(); return error("Loan has no outstanding balance to write off")

    existing_notes = (loan.get("notes") or "").strip()
    writeoff_note = f"[{write_off_date}] Written off KES {outstanding:,.2f}: {reason}"
    notes = f"{existing_notes}\\n{writeoff_note}" if existing_notes else writeoff_note

    db.execute(
        """UPDATE loans
           SET status='written_off', penalties=0, written_off_amount=?, written_off_date=?,
               written_off_reason=?, written_off_by=?, notes=?
           WHERE id=?""",
        (round(outstanding, 2), write_off_date, reason, g.user["sub"], notes, loan_id),
    )
    db.execute("UPDATE loan_schedule SET penalty=0 WHERE loan_id=? AND paid=0", (loan_id,))
    db.execute(
        "INSERT INTO notifications (user_id,type,message) VALUES (?,?,?)",
        (loan.get("officer_id") or g.user["sub"], "write_off", f"Loan {loan_id} written off - KES {outstanding:,.0f}"),
    )
    db.commit()
    updated = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    db.close()
    audit(f"Wrote off loan {loan_id}", "Loans", f"KES {outstanding:,.2f}; {reason}")
    return success({"loan": updated, "written_off_amount": round(outstanding, 2)}, "Loan written off")



@bp.route("/api/loans/<loan_id>/guarantors", methods=["GET"])
@login_required
def get_loan_guarantors(loan_id):
    db = get_db()
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    if not loan:
        db.close(); return error("Loan not found", 404)
    rows = rows_to_list(db.execute(
        """SELECT g.*, gm.name AS guarantor_name, gm.phone AS guarantor_phone, gm.savings AS guarantor_savings
           FROM guarantors g JOIN members gm ON gm.id=g.guarantor_id
           WHERE (g.loan_id=? OR (g.loan_id IS NULL AND g.member_id=?))
           ORDER BY g.created_at DESC, g.id DESC""",
        (loan_id, loan["member_id"]),
    ).fetchall())
    db.close()
    return success(rows)


@bp.route("/api/loans/<loan_id>/guarantors", methods=["POST"])
@login_required
@roles_required("admin", "officer")
def add_loan_guarantor(loan_id):
    d = request.json or {}
    guarantor_id = (d.get("guarantor_id") or "").strip()
    if not guarantor_id:
        return error("Guarantor member is required")
    amount = float(d.get("amount") or 0)
    if amount < 0:
        return error("Guarantee amount cannot be negative")
    db = get_db()
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    if not loan:
        db.close(); return error("Loan not found", 404)
    if guarantor_id == loan["member_id"]:
        db.close(); return error("Borrower cannot guarantee their own loan")
    guarantor = row_to_dict(db.execute("SELECT * FROM members WHERE id=? AND member_type='member' AND status='active'", (guarantor_id,)).fetchone())
    if not guarantor:
        db.close(); return error("Active guarantor member not found")
    duplicate = db.execute(
        "SELECT id FROM guarantors WHERE guarantor_id=? AND (loan_id=? OR (loan_id IS NULL AND member_id=?))",
        (guarantor_id, loan_id, loan["member_id"]),
    ).fetchone()
    if duplicate:
        db.close(); return error("Guarantor already attached to this loan")
    db.execute(
        """INSERT INTO guarantors (loan_id,member_id,guarantor_id,amount,status,notes)
           VALUES (?,?,?,?,?,?)""",
        (loan_id, loan["member_id"], guarantor_id, amount, d.get("status") or "active", d.get("notes") or ""),
    )
    db.commit()
    row = row_to_dict(db.execute("SELECT * FROM guarantors WHERE id=last_insert_rowid()").fetchone())
    db.close()
    audit(f"Added guarantor {guarantor_id} to loan {loan_id}", "Loans")
    return success(row, "Guarantor added", 201)


@bp.route("/api/loans/<loan_id>/guarantors/<int:guarantor_row_id>", methods=["DELETE"])
@login_required
@roles_required("admin", "officer")
def remove_loan_guarantor(loan_id, guarantor_row_id):
    db = get_db()
    row = row_to_dict(db.execute("SELECT * FROM guarantors WHERE id=? AND loan_id=?", (guarantor_row_id, loan_id)).fetchone())
    if not row:
        db.close(); return error("Guarantor not found", 404)
    db.execute("DELETE FROM guarantors WHERE id=?", (guarantor_row_id,))
    db.commit(); db.close()
    audit(f"Removed guarantor {row.get('guarantor_id')} from loan {loan_id}", "Loans")
    return success(msg="Guarantor removed")


@bp.route("/api/loans/<loan_id>/restructure", methods=["POST"])
@login_required
@roles_required("admin", "officer")
def restructure_loan(loan_id):
    d = request.json or {}
    db = get_db()
    refresh_loan_statuses(db)
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    if not loan:
        db.close(); return error("Loan not found", 404)
    if loan.get("status") not in {"active", "overdue"}:
        db.close(); return error("Only active or overdue loans can be restructured")
    schedule = rows_to_list(db.execute("SELECT * FROM loan_schedule WHERE loan_id=? ORDER BY installment", (loan_id,)).fetchall())
    if not schedule:
        db.close(); return error("Loan has no schedule to restructure")
    summary = loan_summary(loan, schedule)
    outstanding = max(0, float(summary.get("outstanding") or 0))
    if outstanding <= 0:
        if float(summary.get("penalties") or 0) > 0:
            db.close(); return error("Only penalty balance remains. Record a penalty payment instead of restructuring.")
        db.close(); return error("Loan is already fully paid")
    old_term = int(loan.get("term_months") or 0)
    old_rate = float(loan.get("annual_rate") or 0)
    old_method = str(loan.get("method") or "reducing")
    old_status = str(loan.get("status") or "").lower()
    try:
        term_months = int(d.get("term_months") or loan.get("term_months") or 1)
        method = (d.get("method") or loan.get("method") or "reducing").strip().lower()
    except (TypeError, ValueError):
        db.close(); return error("Term and rate must be valid numbers")
    if term_months <= 0:
        db.close(); return error("Term must be at least 1 month")
    if method not in {"reducing", "flat"}:
        db.close(); return error("Method must be reducing or flat")
    effective_date = clean_date(d.get("effective_date"), date.today().isoformat())
    snapshot_paid = float(loan.get("total_paid") or 0)
    paid_count = db.execute("SELECT COUNT(*) FROM loan_schedule WHERE loan_id=? AND paid=1", (loan_id,)).fetchone()[0]
    db.execute("DELETE FROM loan_schedule WHERE loan_id=? AND paid=0", (loan_id,))
    next_installment = int(db.execute("SELECT COALESCE(MAX(installment),0)+1 FROM loan_schedule WHERE loan_id=?", (loan_id,)).fetchone()[0] or 1)
    restructured_rate = 0.0
    new_schedule = build_schedule(loan_id, outstanding, restructured_rate, term_months, method, effective_date)
    for idx, row in enumerate(new_schedule, start=next_installment):
        db.execute(
            "INSERT INTO loan_schedule (loan_id,installment,due_date,principal,interest,repayment,balance) VALUES (?,?,?,?,?,?,?)",
            (loan_id, idx, row["due_date"], row["principal"], row["interest"], row["repayment"], row["balance"]),
        )
    note = (d.get("notes") or "").strip()
    note_line = f"Restructured on {effective_date}: term {term_months} months, rate 0.0%, method {method}. Interest was waived after restructure."
    if note:
        note_line += f" {note}"
    combined_notes = "\n".join([item for item in [loan.get("notes"), note_line] if item])
    db.execute(
        "UPDATE loans SET annual_rate=?, term_months=?, method=?, status='active', notes=?, restructure_snapshot_outstanding=?, restructure_snapshot_paid=? WHERE id=?",
        (restructured_rate, term_months, method, combined_notes, outstanding, snapshot_paid, loan_id),
    )
    allocate_repayment_to_schedule(db, loan_id, effective_date)
    db.commit()
    updated = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    db.close()
    audit(
        f"Restructured loan {loan_id}",
        "Loans",
        (
            f"Status {old_status} -> active; term {old_term} -> {term_months} months; "
            f"rate {old_rate}% -> 0.0%; method {old_method} -> {method}; "
            f"effective {effective_date}; outstanding KES {outstanding:,.2f}; "
            f"paid installments kept {paid_count}; new installments {len(new_schedule)}"
        ),
    )
    return success(updated, "Loan restructured")


@bp.route("/api/loans/<loan_id>/schedule", methods=["GET"])
@login_required
def get_loan_schedule(loan_id):
    db       = get_db()
    refresh_loan_statuses(db)
    db.commit()
    schedule = rows_to_list(db.execute(
        "SELECT * FROM loan_schedule WHERE loan_id=? ORDER BY installment", (loan_id,)
    ).fetchall())
    db.close()
    return success(schedule)

# ══════════════════════════════════════════════════════════════════════════════
# REPAYMENTS
# ══════════════════════════════════════════════════════════════════════════════
