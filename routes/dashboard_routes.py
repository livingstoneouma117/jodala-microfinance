from api import Blueprint

from services.common import *

dashboard_bp = Blueprint("dashboard", __name__)
bp = dashboard_bp

@bp.route("/api/dashboard", methods=["GET"])
@login_required
def dashboard():
    db = get_db()
    refresh_loan_statuses(db)
    db.commit()

    active_loans   = db.execute("SELECT COUNT(*) FROM loans WHERE status='active'").fetchone()[0]
    overdue_loans  = db.execute("SELECT COUNT(*) FROM loans WHERE status='overdue'").fetchone()[0]
    approved_loans = db.execute("SELECT COUNT(*) FROM loans WHERE status='approved'").fetchone()[0]
    pending_loans  = db.execute("SELECT COUNT(*) FROM loans WHERE status='pending'").fetchone()[0]
    total_members  = db.execute("SELECT COUNT(*) FROM members WHERE member_type='member'").fetchone()[0]
    active_members = db.execute("SELECT COUNT(*) FROM members WHERE member_type='member' AND status='active'").fetchone()[0]
    total_savings  = db.execute("SELECT COALESCE(SUM(savings),0) FROM members WHERE member_type='member'").fetchone()[0]
    total_disbursed= db.execute("SELECT COALESCE(SUM(amount),0) FROM loans WHERE disbursed_date IS NOT NULL").fetchone()[0]
    total_repaid   = db.execute("SELECT COALESCE(SUM(amount),0) FROM repayments").fetchone()[0]
    total_penalties= db.execute("SELECT COALESCE(SUM(penalties),0) FROM loans").fetchone()[0]
    total_expenses = db.execute("SELECT COALESCE(SUM(amount),0) FROM expense_transactions").fetchone()[0]
    account_report = build_monthly_account_report(db)
    account_opening_balance = get_account_opening_balance(db)
    account_savings_collections = float(account_report["totals"]["savings_collections"] or 0)
    account_loan_repayments = float(account_report["totals"]["loan_repayments"] or 0)
    account_loan_disbursed = float(account_report["totals"]["loan_disbursed"] or 0)
    account_expenses = float(account_report["totals"]["expenses"] or 0)
    account_total_inflow = float(account_report["totals"]["inflow"] or 0)
    account_total_outflow = float(account_report["totals"]["outflow"] or 0)
    account_current_balance = account_opening_balance
    monthly_rows = account_report.get("months") or []
    current_month = monthly_rows[-1] if monthly_rows else {}
    report_month = date.today().strftime("%Y-%m")
    portfolio = db.execute("""
        SELECT
          COALESCE(SUM(total_repayable),0) AS total_repayable,
          COALESCE(SUM(outstanding),0) AS outstanding_portfolio,
          COALESCE(SUM(amount_in_arrears),0) AS amount_in_arrears,
          COALESCE(SUM(CASE WHEN days_in_arrears >= 30 THEN outstanding ELSE 0 END),0) AS par30_amount
        FROM (
          SELECT l.id,
                 COALESCE(s.total_repayable, l.amount) + COALESCE(l.penalties,0) AS total_repayable,
                 MAX(COALESCE(s.total_repayable, l.amount) + COALESCE(l.penalties,0) - l.total_paid, 0) AS outstanding,
                 COALESCE(s.amount_in_arrears,0) AS amount_in_arrears,
                 s.days_in_arrears AS days_in_arrears
          FROM loans l
          LEFT JOIN (
            SELECT loan_id,
                   SUM(repayment) AS total_repayable,
                   SUM(CASE WHEN paid=0 AND due_date < date('now') THEN repayment + COALESCE(penalty,0) ELSE 0 END) AS amount_in_arrears,
                   CAST(julianday(date('now')) - julianday(MIN(CASE WHEN paid=0 AND due_date < date('now') THEN due_date END)) AS INTEGER) AS days_in_arrears
            FROM loan_schedule
            GROUP BY loan_id
          ) s ON s.loan_id=l.id
          WHERE l.disbursed_date IS NOT NULL AND l.status IN ('active','overdue','completed')
        )
    """).fetchone()
    monthly_portfolio = db.execute("""
        SELECT
          COALESCE(SUM(total_repayable),0) AS total_repayable,
          COALESCE(SUM(outstanding),0) AS outstanding_portfolio,
          COALESCE(SUM(amount_in_arrears),0) AS amount_in_arrears,
          COALESCE(SUM(CASE WHEN days_in_arrears >= 30 THEN outstanding ELSE 0 END),0) AS par30_amount
        FROM (
          SELECT l.id,
                 COALESCE(s.total_repayable, l.amount) + COALESCE(l.penalties,0) AS total_repayable,
                 MAX(COALESCE(s.total_repayable, l.amount) + COALESCE(l.penalties,0) - l.total_paid, 0) AS outstanding,
                 COALESCE(s.amount_in_arrears,0) AS amount_in_arrears,
                 s.days_in_arrears AS days_in_arrears
          FROM loans l
          LEFT JOIN (
            SELECT loan_id,
                   SUM(repayment) AS total_repayable,
                   SUM(CASE WHEN paid=0 AND due_date < date('now') THEN repayment + COALESCE(penalty,0) ELSE 0 END) AS amount_in_arrears,
                   CAST(julianday(date('now')) - julianday(MIN(CASE WHEN paid=0 AND due_date < date('now') THEN due_date END)) AS INTEGER) AS days_in_arrears
            FROM loan_schedule
            GROUP BY loan_id
          ) s ON s.loan_id=l.id
          WHERE l.disbursed_date IS NOT NULL
            AND strftime('%Y-%m', l.disbursed_date)=?
        )
    """, (report_month,)).fetchone()
    due_today = db.execute("""
        SELECT COALESCE(SUM(s.repayment),0)
        FROM loan_schedule s
        JOIN loans l ON l.id=s.loan_id
        WHERE s.paid=0 AND s.due_date=date('now') AND l.status <> 'written_off'
    """).fetchone()[0]

    # Monthly repayments (last 6 months)
    monthly = db.execute("""
        SELECT strftime('%Y-%m', payment_date) as month, SUM(amount) as total
        FROM repayments
        GROUP BY month ORDER BY month DESC LIMIT 6
    """).fetchall()

    # Recent loans with member name
    recent_loans = rows_to_list(db.execute("""
        SELECT l.id, l.amount, l.status, l.applied_date, m.name as member_name
        FROM loans l JOIN members m ON l.member_id=m.id
        ORDER BY l.created_at DESC LIMIT 5
    """).fetchall())

    # Loan status breakdown
    loan_breakdown = rows_to_list(db.execute("""
        SELECT status, COUNT(*) as count, COALESCE(SUM(amount),0) as total
        FROM loans GROUP BY status
    """).fetchall())

    # Top borrowers
    top_borrowers = rows_to_list(db.execute("""
        SELECT m.name, COUNT(l.id) as loan_count, SUM(l.amount) as total_borrowed
        FROM loans l JOIN members m ON l.member_id=m.id
        GROUP BY l.member_id ORDER BY total_borrowed DESC LIMIT 5
    """).fetchall())

    collection_rate = round((total_repaid / total_disbursed * 100), 1) if total_disbursed else 0
    par_amount = float(portfolio["amount_in_arrears"] or 0)
    outstanding_portfolio = float(portfolio["outstanding_portfolio"] or 0)
    par_rate = round((par_amount / outstanding_portfolio * 100), 1) if outstanding_portfolio else 0
    par30_amount = float(portfolio["par30_amount"] or 0)
    par30_rate = round((par30_amount / outstanding_portfolio * 100), 1) if outstanding_portfolio else 0
    monthly_outstanding_portfolio = float(monthly_portfolio["outstanding_portfolio"] or 0)
    monthly_par_amount = float(monthly_portfolio["amount_in_arrears"] or 0)
    monthly_par_rate = round((monthly_par_amount / monthly_outstanding_portfolio * 100), 1) if monthly_outstanding_portfolio else 0
    monthly_par30_amount = float(monthly_portfolio["par30_amount"] or 0)
    monthly_par30_rate = round((monthly_par30_amount / monthly_outstanding_portfolio * 100), 1) if monthly_outstanding_portfolio else 0
    monthly_collection_rate = round((account_loan_repayments / account_loan_disbursed * 100), 1) if account_loan_disbursed else 0

    db.close()
    return success({
        "stats": {
            "active_loans":    active_loans,
            "overdue_loans":   overdue_loans,
            "approved_loans":  approved_loans,
            "pending_loans":   pending_loans,
            "total_members":   total_members,
            "active_members":  active_members,
            "total_savings":   total_savings,
            "total_disbursed": total_disbursed,
            "total_repaid":    total_repaid,
            "total_penalties": total_penalties,
            "total_expenses":  total_expenses,
            "account_opening_balance": account_opening_balance,
            "account_savings_collections": account_savings_collections,
            "account_loan_repayments": account_loan_repayments,
            "account_loan_disbursed": account_loan_disbursed,
            "account_expenses": account_expenses,
            "account_total_inflow": account_total_inflow,
            "account_total_outflow": account_total_outflow,
            "account_current_balance": account_current_balance,
            "collection_rate": collection_rate,
            "outstanding_portfolio": outstanding_portfolio,
            "amount_in_arrears": par_amount,
            "portfolio_at_risk": par_rate,
            "par30_amount": par30_amount,
            "par30_rate": par30_rate,
            "monthly_collection_rate": monthly_collection_rate,
            "monthly_outstanding_portfolio": monthly_outstanding_portfolio,
            "monthly_amount_in_arrears": monthly_par_amount,
            "monthly_portfolio_at_risk": monthly_par_rate,
            "monthly_par30_amount": monthly_par30_amount,
            "monthly_par30_rate": monthly_par30_rate,
            "due_today": due_today,
        },
        "monthly_repayments": [{"month": r["month"], "total": r["total"]} for r in reversed(monthly)],
        "monthly_summary": {
            "month": current_month.get("month"),
            "opening_balance": float(current_month.get("opening_balance") or account_current_balance or 0),
            "savings_collections": float(current_month.get("savings_collections") or 0),
            "loan_repayments": float(current_month.get("loan_repayments") or 0),
            "loan_disbursed": float(current_month.get("loan_disbursed") or 0),
            "expenses": float(current_month.get("expenses") or 0),
            "inflow": float(current_month.get("inflow") or 0),
            "outflow": float(current_month.get("outflow") or 0),
            "net": float(current_month.get("net") or 0),
            "closing_balance": float(current_month.get("closing_balance") or account_current_balance or 0),
        },
        "recent_loans":       recent_loans,
        "loan_breakdown":     loan_breakdown,
        "top_borrowers":      top_borrowers,
    })

# ══════════════════════════════════════════════════════════════════════════════
# MEMBERS
# ══════════════════════════════════════════════════════════════════════════════

