from api import Blueprint

from services.common import *

reports_bp = Blueprint("reports", __name__)
bp = reports_bp

@bp.route("/api/reports/portfolio", methods=["GET"])
@login_required
def report_portfolio():
    db = get_db()
    refresh_loan_statuses(db)
    db.commit()
    rows = rows_to_list(db.execute(
        """SELECT l.*, m.name as member_name,
           COALESCE(risk.total_repayable, l.amount) + COALESCE(l.penalties,0) as total_repayable,
           CASE WHEN l.status='written_off' THEN 0 ELSE MAX(COALESCE(risk.total_repayable, l.amount) + COALESCE(l.penalties,0) - l.total_paid, 0) END as outstanding,
           CASE WHEN l.status='written_off' THEN 0 ELSE COALESCE(risk.amount_in_arrears,0) END as amount_in_arrears,
           COALESCE(risk.overdue_installments,0) as overdue_installments,
           COALESCE(CAST(julianday(date('now')) - julianday(risk.oldest_due_date) AS INTEGER),0) as days_in_arrears,
           risk.next_due_date
           FROM loans l
           JOIN members m ON l.member_id=m.id
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
           ORDER BY l.disbursed_date DESC"""
    ).fetchall())
    totals = db.execute(
        """SELECT
           COALESCE(SUM(amount),0) as total_disbursed,
           COALESCE(SUM(total_paid),0) as total_repaid,
           COALESCE(SUM(CASE WHEN status='written_off' THEN 0 ELSE total_repayable END),0) as total_repayable,
           COALESCE(SUM(CASE WHEN status='written_off' THEN 0 ELSE MAX(total_repayable - total_paid, 0) END),0) as total_outstanding,
           COALESCE(SUM(CASE WHEN status='written_off' THEN 0 ELSE amount_in_arrears END),0) as amount_in_arrears,
           COALESCE(SUM(CASE WHEN status='written_off' THEN 0 WHEN days_in_arrears >= 30 THEN MAX(total_repayable - total_paid, 0) ELSE 0 END),0) as par30_amount,
           COALESCE(SUM(penalties),0) as total_penalties,
           COUNT(*) as total_loans
           FROM (
               SELECT l.id, l.amount, l.total_paid, l.penalties, l.disbursed_date, l.status,
                       COALESCE(risk.total_repayable, l.amount) + COALESCE(l.penalties,0) as total_repayable,
                       COALESCE(risk.amount_in_arrears,0) as amount_in_arrears,
                       risk.days_in_arrears
               FROM loans l
               LEFT JOIN (
                 SELECT loan_id,
                        SUM(repayment) as total_repayable,
                        SUM(CASE WHEN paid=0 AND due_date < date('now') THEN repayment + COALESCE(penalty,0) ELSE 0 END) as amount_in_arrears,
                        CAST(julianday(date('now')) - julianday(MIN(CASE WHEN paid=0 AND due_date < date('now') THEN due_date END)) AS INTEGER) as days_in_arrears
                 FROM loan_schedule
                 GROUP BY loan_id
               ) risk ON risk.loan_id=l.id
               WHERE l.disbursed_date IS NOT NULL
           )"""
    ).fetchone()
    db.close()
    return success({"loans": rows, "totals": dict(totals)})



@bp.route("/api/reports/savings", methods=["GET"])
@login_required
def report_savings():
    db = get_db()
    rows = rows_to_list(db.execute(
        """SELECT m.id, m.name, m.status, sa.balance,
           COALESCE(SUM(CASE WHEN st.type='deposit' THEN st.amount ELSE 0 END),0) as total_deposits,
           COALESCE(SUM(CASE WHEN st.type='withdrawal' THEN st.amount ELSE 0 END),0) as total_withdrawals
           FROM members m
           LEFT JOIN savings_accounts sa ON m.id=sa.member_id
           LEFT JOIN savings_transactions st ON m.id=st.member_id
           WHERE m.member_type='member'
           GROUP BY m.id ORDER BY sa.balance DESC"""
    ).fetchall())
    db.close()
    return success(rows)



@bp.route("/api/reports/account-monthly", methods=["GET"])
@login_required
def report_account_monthly():
    db = get_db()
    data = build_monthly_account_report(db)
    db.close()
    return success(data)



@bp.route("/api/dividends", methods=["GET"])
@login_required
def list_dividends():
    year = request.args.get("year")
    where = []
    params = []
    if year:
        where.append("dr.year=?")
        params.append(int(year))
    clause = "WHERE " + " AND ".join(where) if where else ""
    db = get_db()
    runs = rows_to_list(db.execute(
        f"""SELECT dr.*, u.name AS created_by_name,
                  COUNT(da.id) AS member_count,
                  COALESCE(SUM(da.dividend_amount),0) AS allocated_total
           FROM dividend_runs dr
           LEFT JOIN dividend_allocations da ON da.run_id=dr.id
           LEFT JOIN users u ON u.id=dr.created_by
           {clause}
           GROUP BY dr.id
           ORDER BY dr.year DESC, dr.created_at DESC""",
        params,
    ).fetchall())
    selected = None
    allocations = []
    if runs:
        selected = runs[0]
        allocations = rows_to_list(db.execute(
            """SELECT da.*, m.name AS member_name, m.phone AS member_phone
               FROM dividend_allocations da JOIN members m ON m.id=da.member_id
               WHERE da.run_id=? ORDER BY da.dividend_amount DESC""",
            (selected["id"],),
        ).fetchall())
    db.close()
    return success({"runs": runs, "selected": selected, "allocations": allocations})


@bp.route("/api/dividends/calculate", methods=["POST"])
@login_required
@roles_required("admin", "accountant")
def calculate_dividends():
    d = request.json or {}
    try:
        year = int(d.get("year") or date.today().year)
        surplus = float(d.get("surplus") or 0)
    except (TypeError, ValueError):
        return error("Year and surplus must be valid numbers")
    if surplus <= 0:
        return error("Surplus must be greater than zero")
    basis = (d.get("basis") or "savings_balance").strip().lower()
    if basis != "savings_balance":
        return error("Only savings_balance dividend basis is currently supported")
    db = get_db()
    members = rows_to_list(db.execute(
        """SELECT m.id, m.name, COALESCE(sa.balance, m.savings, 0) AS basis_amount
           FROM members m LEFT JOIN savings_accounts sa ON sa.member_id=m.id
           WHERE m.member_type='member' AND m.status='active'
           ORDER BY m.name"""
    ).fetchall())
    total_basis = sum(float(member.get("basis_amount") or 0) for member in members)
    if total_basis <= 0:
        db.close(); return error("No member savings balance available for dividend allocation")
    db.execute(
        "INSERT INTO dividend_runs (year,surplus,basis,total_basis,status,created_by) VALUES (?,?,?,?,?,?)",
        (year, surplus, basis, total_basis, "draft", g.user["sub"]),
    )
    run_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    allocations = []
    remaining = round(surplus, 2)
    eligible = [member for member in members if float(member.get("basis_amount") or 0) > 0]
    for index, member in enumerate(eligible):
        basis_amount = float(member.get("basis_amount") or 0)
        amount = remaining if index == len(eligible) - 1 else round((basis_amount / total_basis) * surplus, 2)
        remaining = round(remaining - amount, 2)
        db.execute(
            "INSERT INTO dividend_allocations (run_id,member_id,basis_amount,dividend_amount) VALUES (?,?,?,?)",
            (run_id, member["id"], basis_amount, amount),
        )
        allocations.append({"member_id": member["id"], "member_name": member["name"], "basis_amount": basis_amount, "dividend_amount": amount})
    db.commit()
    run = row_to_dict(db.execute("SELECT * FROM dividend_runs WHERE id=?", (run_id,)).fetchone())
    db.close()
    audit(f"Calculated dividends for {year}", "Dividends", f"Surplus KES {surplus}")
    return success({"run": run, "allocations": allocations}, "Dividend allocation calculated", 201)


@bp.route("/api/dividends/<int:run_id>/status", methods=["PATCH"])
@login_required
@roles_required("admin", "accountant")
def update_dividend_status(run_id):
    status = ((request.json or {}).get("status") or "").strip().lower()
    if status not in {"draft", "approved", "paid", "cancelled"}:
        return error("Status must be draft, approved, paid, or cancelled")
    db = get_db()
    run = row_to_dict(db.execute("SELECT * FROM dividend_runs WHERE id=?", (run_id,)).fetchone())
    if not run:
        db.close(); return error("Dividend run not found", 404)
    db.execute("UPDATE dividend_runs SET status=? WHERE id=?", (status, run_id))
    if status == "paid":
        db.execute("UPDATE dividend_allocations SET paid=1 WHERE run_id=?", (run_id,))
    db.commit(); db.close()
    audit(f"Set dividend run {run_id} to {status}", "Dividends")
    return success(msg="Dividend status updated")


@bp.route("/api/reports/export/<report_type>", methods=["GET"])
@login_required
def export_report(report_type):
    import csv, io
    db = get_db()
    refresh_loan_statuses(db)
    db.commit()
    export_format = (request.args.get("format") or "csv").strip().lower()
    rows = []
    headers = []

    if report_type == "loans":
        headers = ["ID","Member","Amount","Rate%","Term","Method","Status","Disbursed","Paid","Outstanding","Penalties"]
        rows = rows_to_list(db.execute(
            """SELECT l.id,m.name,l.amount,l.annual_rate,l.term_months,l.method,l.status,l.disbursed_date,l.total_paid,
                      CASE WHEN l.status='written_off' THEN 0 ELSE MAX(COALESCE(SUM(s.repayment), l.amount)+COALESCE(l.penalties,0)-l.total_paid, 0) END as outstanding,l.penalties
               FROM loans l
               JOIN members m ON l.member_id=m.id
               LEFT JOIN loan_schedule s ON s.loan_id=l.id
               GROUP BY l.id"""
        ).fetchall())
    elif report_type == "repayments":
        headers = ["ID","Loan","Member","Amount","Date","Method","Reference","Type"]
        rows = rows_to_list(db.execute(
            "SELECT r.id,r.loan_id,m.name,r.amount,r.payment_date,r.method,r.reference,r.type FROM repayments r JOIN members m ON r.member_id=m.id ORDER BY r.payment_date DESC"
        ).fetchall())
    elif report_type == "savings":
        headers = ["Member ID","Member","Balance","Status"]
        rows = rows_to_list(db.execute(
            "SELECT m.id,m.name,sa.balance,m.status FROM members m LEFT JOIN savings_accounts sa ON m.id=sa.member_id WHERE m.member_type='member' ORDER BY sa.balance DESC"
        ).fetchall())
    elif report_type == "expenses":
        headers = ["ID","Date","Account","Account Code","Amount","Payee","Reference","Notes","Recorded By"]
        rows = rows_to_list(db.execute(
            """SELECT et.id, et.expense_date, ea.name, ea.code, et.amount, et.payee, et.reference, et.notes, u.name
               FROM expense_transactions et
               JOIN expense_accounts ea ON et.account_id=ea.id
               LEFT JOIN users u ON et.recorded_by=u.id
               ORDER BY et.expense_date DESC, et.created_at DESC"""
        ).fetchall())
    elif report_type == "account-monthly":
        headers = ["Month","Opening Balance","Savings Collections","Loan Repayments","Total Inflow","Loans Disbursed","Expenses","Total Outflow","Net Movement","Closing Balance"]
        data = build_monthly_account_report(db)
        for row in data.get("months", []):
            rows.append({
                "Month": row.get("month"),
                "Opening Balance": row.get("opening_balance"),
                "Savings Collections": row.get("savings_collections"),
                "Loan Repayments": row.get("loan_repayments"),
                "Total Inflow": row.get("inflow"),
                "Loans Disbursed": row.get("loan_disbursed"),
                "Expenses": row.get("expenses"),
                "Total Outflow": row.get("outflow"),
                "Net Movement": row.get("net"),
                "Closing Balance": row.get("closing_balance"),
            })
    elif report_type == "members":
        headers = ["ID","Name","Phone","Email","National ID","Status","Joined","Savings"]
        rows = rows_to_list(db.execute("SELECT id,name,phone,email,national_id,status,joined_date,savings FROM members WHERE member_type='member'").fetchall())
    elif report_type == "dividends":
        headers = ["Run ID","Year","Member ID","Member","Basis Amount","Dividend Amount","Paid","Status"]
        rows = rows_to_list(db.execute(
            """SELECT dr.id AS 'Run ID', dr.year AS Year, da.member_id AS 'Member ID', m.name AS Member,
                      da.basis_amount AS 'Basis Amount', da.dividend_amount AS 'Dividend Amount', da.paid AS Paid, dr.status AS Status
               FROM dividend_allocations da
               JOIN dividend_runs dr ON dr.id=da.run_id
               JOIN members m ON m.id=da.member_id
               ORDER BY dr.year DESC, da.dividend_amount DESC"""
        ).fetchall())
    else:
        db.close(); return error("Unknown report type")

    # CSV output is the default and remains backward-compatible.
    if export_format not in ("csv", "xlsx"):
        db.close()
        return error("Unsupported export format. Use csv or xlsx.")

    db.close()
    from api import Response
    audit(f"Exported {report_type} report", "Reports")
    if export_format == "xlsx":
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
        except Exception:
            return error("Excel export dependency missing. Install openpyxl.")

        wb = Workbook()
        ws = wb.active
        ws.title = (report_type or "report")[:31]
        ws.append(headers)
        header_fill = PatternFill(start_color="E5EEF9", end_color="E5EEF9", fill_type="solid")
        for idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=idx)
            cell.font = Font(bold=True)
            cell.fill = header_fill

        for row in rows:
            if isinstance(row, dict):
                ws.append([row.get(h) for h in headers])
            else:
                ws.append(list(row))

        # Set readable default widths.
        for col in ws.columns:
            max_len = max((len(str(c.value or "")) for c in col), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(42, max(12, max_len + 2))

        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)
        return send_file(
            stream,
            as_attachment=True,
            download_name=f"{report_type}-report.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h) for h in headers] if isinstance(row, dict) else list(row))
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment;filename={report_type}-report.csv"}
    )


# ══════════════════════════════════════════════════════════════════════════════
# ACCOUNTING
# ══════════════════════════════════════════════════════════════════════════════

