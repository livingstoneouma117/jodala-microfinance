"""
SACCOFinance LMS - Loan calculation engine
"""
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import calendar


def _add_months(dt: date, months: int) -> date:
    """Add months to a date, handling month-end correctly."""
    month = dt.month - 1 + months
    year  = dt.year + month // 12
    month = month % 12 + 1
    day   = min(dt.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def build_schedule(loan_id: str, principal: float, annual_rate: float,
                   term_months: int, method: str, start_date: str) -> list[dict]:
    """
    Returns a list of schedule rows for a loan.
    method: 'flat' | 'reducing'
    """
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    schedule = []
    balance  = principal
    monthly_rate = annual_rate / 100
    monthly_interest = principal * monthly_rate
    total_interest = monthly_interest * term_months
    total_repayable = principal + total_interest
    principal_part = principal / term_months
    interest_part = monthly_interest
    monthly_repayment = total_repayable / term_months

    for i in range(1, term_months + 1):
        due_date = _add_months(start, i)

        interest      = interest_part
        principal_pay = principal_part
        balance       = max(0, balance - principal_pay)

        schedule.append({
            "loan_id":     loan_id,
            "installment": i,
            "due_date":    due_date.strftime("%Y-%m-%d"),
            "principal":   round(principal_pay, 2),
            "interest":    round(interest, 2),
            "repayment":   round(monthly_repayment, 2),
            "balance":     round(balance, 2),
        })

    return schedule


def calculate_penalty(schedule_row: dict, penalty_rate_pct: float = 5.0) -> float:
    """
    Calculate penalty for an overdue installment.
    penalty_rate_pct is % of outstanding repayment per month overdue.
    """
    if schedule_row["paid"]:
        return 0.0
    due    = datetime.strptime(schedule_row["due_date"], "%Y-%m-%d").date()
    today  = date.today()
    if today <= due:
        return 0.0
    days_overdue   = (today - due).days
    months_overdue = max(1, days_overdue // 30)
    penalty        = (schedule_row["repayment"] * penalty_rate_pct / 100) * months_overdue
    return round(penalty, 2)


def loan_summary(loan: dict, schedule: list[dict]) -> dict:
    """Compute derived loan metrics."""
    total_repayable = sum(r["repayment"] for r in schedule)
    total_interest  = sum(r["interest"]  for r in schedule)
    paid_rows       = [r for r in schedule if r.get("paid")]
    pending_rows    = [r for r in schedule if not r.get("paid")]
    next_due        = pending_rows[0] if pending_rows else None

    return {
        "total_repayable":  round(total_repayable, 2),
        "total_interest":   round(total_interest, 2),
        "total_paid":       loan.get("total_paid", 0),
        "outstanding":      round(max(0, total_repayable - loan.get("total_paid", 0)), 2),
        "installments_paid":len(paid_rows),
        "installments_left":len(pending_rows),
        "next_due":         next_due,
        "penalties":        loan.get("penalties", 0),
    }
