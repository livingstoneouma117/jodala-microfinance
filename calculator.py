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
    if term_months <= 0:
        return schedule

    balance  = float(principal)
    monthly_rate = float(annual_rate) / 100

    # Keep legacy flat-interest behavior, but guarantee exact totals/rounding.
    monthly_interest = principal * monthly_rate if monthly_rate > 0 else 0.0
    total_interest = monthly_interest * term_months
    total_repayable = principal + total_interest

    principal_base = round(principal / term_months, 2)
    interest_base = round(total_interest / term_months, 2) if total_interest > 0 else 0.0
    principal_alloc = 0.0
    interest_alloc = 0.0

    for i in range(1, term_months + 1):
        due_date = _add_months(start, i)

        if i < term_months:
            principal_pay = principal_base
            interest = interest_base
        else:
            # Last installment absorbs rounding remainder so totals stay exact.
            principal_pay = round(principal - principal_alloc, 2)
            interest = round(total_interest - interest_alloc, 2)

        principal_alloc += principal_pay
        interest_alloc += interest
        repayment = round(principal_pay + interest, 2)
        balance = round(max(0.0, principal - principal_alloc), 2)

        schedule.append({
            "loan_id":     loan_id,
            "installment": i,
            "due_date":    due_date.strftime("%Y-%m-%d"),
            "principal":   round(principal_pay, 2),
            "interest":    round(interest, 2),
            "repayment":   repayment,
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
    base_repayable = sum(float(r.get("repayment") or 0) for r in schedule)
    total_interest = sum(float(r.get("interest") or 0) for r in schedule)
    penalties = float(loan.get("penalties") or 0)
    total_repayable = base_repayable + penalties
    total_paid = float(loan.get("total_paid") or 0)
    paid_rows = [r for r in schedule if r.get("paid")]
    pending_rows = [r for r in schedule if not r.get("paid")]
    status = str(loan.get("status") or "").lower()
    is_written_off = status in {"written_off", "written off"}
    next_due = None if is_written_off else (pending_rows[0] if pending_rows else None)
    outstanding = 0.0 if is_written_off else max(0, total_repayable - total_paid)

    return {
        "base_repayable": round(base_repayable, 2),
        "total_repayable": round(total_repayable, 2),
        "total_interest": round(total_interest, 2),
        "total_paid": round(total_paid, 2),
        "outstanding": round(outstanding, 2),
        "installments_paid": len(paid_rows),
        "installments_left": 0 if is_written_off else len(pending_rows),
        "next_due": next_due,
        "penalties": round(penalties, 2),
        "written_off_amount": round(float(loan.get("written_off_amount") or 0), 2),
    }
