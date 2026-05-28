from flask import Blueprint

from services.common import *

loans_bp = Blueprint("loans", __name__)
bp = loans_bp

@bp.route("/api/loan-products", methods=["GET"])
@login_required
def get_loan_products():
    db   = get_db()
    rows = rows_to_list(db.execute("SELECT * FROM loan_products WHERE active=1").fetchall())
    db.close()
    return success(rows)

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
            risk.next_due_date,
            COALESCE(risk.amount_in_arrears,0) as amount_in_arrears,
            COALESCE(risk.overdue_installments,0) as overdue_installments,
            risk.oldest_due_date,
            COALESCE(CAST(julianday(date('now')) - julianday(risk.oldest_due_date) AS INTEGER),0) as days_in_arrears,
            MAX(COALESCE(risk.total_repayable, l.amount) - l.total_paid, 0) as outstanding
            FROM loans l
            JOIN members m ON l.member_id=m.id
            LEFT JOIN users u ON l.officer_id=u.id
            LEFT JOIN (
                SELECT loan_id,
                       SUM(repayment) as total_repayable,
                       MIN(CASE WHEN paid=0 THEN due_date END) as next_due_date,
                       MIN(CASE WHEN paid=0 AND due_date < date('now') THEN due_date END) as oldest_due_date,
                       SUM(CASE WHEN paid=0 AND due_date < date('now') THEN repayment ELSE 0 END) as amount_in_arrears,
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
    risk = loan_risk_snapshot(db, loan_id)
    db.close()

    summary = loan_summary(loan, schedule)
    return success({"loan": loan, "schedule": schedule, "repayments": repays, "summary": summary, "risk": risk})



@bp.route("/api/loans/<loan_id>/statement", methods=["GET"])
@login_required
def loan_statement(loan_id):
    data = get_loan_statement_data(loan_id)
    if not data:
        return error("Loan not found", 404)
    loan = data["loan"]
    schedule = data["schedule"]
    repays = data["repays"]
    settings = data["settings"]
    summary = data["summary"]
    schedule_rows = "".join(
        f"<tr><td>{r['installment']}</td><td>{escape(str(r['due_date']))}</td><td>{r['principal']:,.2f}</td><td>{r['interest']:,.2f}</td><td>{r['repayment']:,.2f}</td><td>{r['balance']:,.2f}</td></tr>"
        for r in schedule
    ) or "<tr><td colspan='6'>Schedule will be available after approval.</td></tr>"
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
    <div class='box'><strong>Loan Summary</strong><br>Principal: KES {loan['amount']:,.2f}<br>Rate: {loan['annual_rate']}% p.a.<br>Term: {loan['term_months']} months<br>Status: {escape(loan['status'])}</div>
    <div class='box'>Total Repayable<br><strong>KES {summary['total_repayable']:,.2f}</strong></div>
    <div class='box'>Outstanding<br><strong>KES {summary['outstanding']:,.2f}</strong></div>
    </div>
    <h2>Repayment Schedule</h2><table><thead><tr><th>#</th><th>Due</th><th>Principal</th><th>Interest</th><th>Payment</th><th>Balance</th></tr></thead><tbody>{schedule_rows}</tbody></table>
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
           WHERE member_id=? AND status IN ('pending','active','overdue')
           ORDER BY created_at ASC LIMIT 1""",
        (d["member_id"],)
    ).fetchone())

    if topup_loan:
        added_amount = float(d["amount"])
        if added_amount <= 0:
            db.close(); return error("Top-up amount must be greater than zero")

        new_amount = float(topup_loan["amount"]) + added_amount
        new_status = topup_loan["status"]
        db.execute(
            """UPDATE loans
               SET amount=?, annual_rate=?, term_months=?, method=?,
                   purpose=?, applied_date=?, disbursed_date=?, officer_id=?
               WHERE id=?""",
            (new_amount, float(d["annual_rate"]), int(d["term_months"]),
             d.get("method", topup_loan.get("method") or "reducing"),
             d.get("purpose", topup_loan.get("purpose")),
             borrowed_date, borrowed_date if topup_loan["status"] in ("active", "overdue") else topup_loan.get("disbursed_date"),
             g.user["sub"], topup_loan["id"])
        )
        loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (topup_loan["id"],)).fetchone())

        if loan["status"] in ("active", "overdue"):
            start_date = borrowed_date
            rebuild_loan_schedule(db, loan, start_date)
            total_repayable = db.execute(
                "SELECT COALESCE(SUM(repayment),0) FROM loan_schedule WHERE loan_id=?",
                (loan["id"],)
            ).fetchone()[0]
            if float(loan.get("total_paid") or 0) >= float(total_repayable):
                new_status = "completed"
            db.execute("UPDATE loans SET status=? WHERE id=?", (new_status, loan["id"]))
            loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan["id"],)).fetchone())
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

    payload = request.get_json(silent=True) or {}
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



@bp.route("/api/loans/<loan_id>/schedule", methods=["GET"])
@login_required
def get_loan_schedule(loan_id):
    db       = get_db()
    schedule = rows_to_list(db.execute(
        "SELECT * FROM loan_schedule WHERE loan_id=? ORDER BY installment", (loan_id,)
    ).fetchall())
    db.close()
    return success(schedule)

# ══════════════════════════════════════════════════════════════════════════════
# REPAYMENTS
# ══════════════════════════════════════════════════════════════════════════════