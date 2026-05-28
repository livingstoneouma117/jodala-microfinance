from flask import g, jsonify, make_response, request, send_file
import base64
import json
import os
import re
import sqlite3
import time as pytime
from datetime import date, datetime
from html import escape
from io import BytesIO

from auth import decode_token, gen_id, generate_token, hash_password, login_required, normalize_permissions, roles_required
from calculator import build_schedule, calculate_penalty, loan_summary
from database import get_db, hash_password as db_hash, init_db
def row_to_dict(row) -> dict:
    return dict(row) if row else {}

def rows_to_list(rows) -> list:
    return [dict(r) for r in rows]

def audit(action: str, module: str, details: str = ""):
    try:
        user = g.get("user", {})
        db   = get_db()
        db.execute(
            "INSERT INTO audit_logs (user_id,user_name,action,module,details,ip_address) VALUES (?,?,?,?,?,?)",
            (user.get("sub"), user.get("name","System"), action, module, details,
             request.remote_addr or "unknown"),
        )
        db.commit(); db.close()
    except Exception:
        pass

def success(data=None, msg="OK", code=200):
    return jsonify({"success": True,  "message": msg, "data": data}), code

def error(msg="Error", code=400):
    return jsonify({"success": False, "error": msg}), code


PASSWORD_POLICY_MESSAGE = (
    "Password must be at least 8 characters and include uppercase, lowercase, number, and special character."
)
VALID_USER_ROLES = {"admin", "officer", "accountant", "cashier"}


def validate_password_strength(password: str) -> str | None:
    pwd = str(password or "")
    if len(pwd) < 8:
        return PASSWORD_POLICY_MESSAGE
    if not re.search(r"[A-Z]", pwd):
        return PASSWORD_POLICY_MESSAGE
    if not re.search(r"[a-z]", pwd):
        return PASSWORD_POLICY_MESSAGE
    if not re.search(r"\d", pwd):
        return PASSWORD_POLICY_MESSAGE
    if not re.search(r"[^A-Za-z0-9]", pwd):
        return PASSWORD_POLICY_MESSAGE
    return None


def validate_user_role(role: str) -> str | None:
    if (role or "").strip().lower() not in VALID_USER_ROLES:
        return "Role must be one of: admin, officer, accountant, cashier"
    return None


def _int_env(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return max(minimum, default)


LOGIN_MAX_ATTEMPTS = _int_env("LOGIN_MAX_ATTEMPTS", 5, 1)
LOGIN_WINDOW_SECONDS = _int_env("LOGIN_WINDOW_SECONDS", 600, 60)
LOGIN_BLOCK_SECONDS = _int_env("LOGIN_BLOCK_SECONDS", 900, 60)
_LOGIN_ATTEMPTS: dict[str, dict] = {}


def _cleanup_login_attempts(now_ts: float) -> None:
    expired = []
    for key, rec in _LOGIN_ATTEMPTS.items():
        blocked_until = float(rec.get("blocked_until", 0) or 0)
        last_seen = float(rec.get("last_seen", 0) or 0)
        if blocked_until and blocked_until > now_ts:
            continue
        if now_ts - last_seen > LOGIN_WINDOW_SECONDS * 2:
            expired.append(key)
    for key in expired:
        _LOGIN_ATTEMPTS.pop(key, None)


def _login_attempt_key(username: str) -> str:
    xff = (request.headers.get("X-Forwarded-For") or "").strip()
    ip = (xff.split(",")[0].strip() if xff else "") or (request.remote_addr or "unknown")
    return f"{ip}:{username.lower().strip()}"


def _login_block_remaining_seconds(attempt_key: str) -> int:
    now_ts = pytime.time()
    rec = _LOGIN_ATTEMPTS.get(attempt_key)
    if not rec:
        return 0
    blocked_until = float(rec.get("blocked_until", 0) or 0)
    if blocked_until <= now_ts:
        return 0
    return int(blocked_until - now_ts)


def _record_failed_login(attempt_key: str) -> int:
    now_ts = pytime.time()
    rec = _LOGIN_ATTEMPTS.get(attempt_key, {"attempts": 0, "window_start": now_ts, "blocked_until": 0, "last_seen": now_ts})
    window_start = float(rec.get("window_start", now_ts) or now_ts)
    if now_ts - window_start > LOGIN_WINDOW_SECONDS:
        rec["attempts"] = 0
        rec["window_start"] = now_ts
        rec["blocked_until"] = 0
    rec["attempts"] = int(rec.get("attempts", 0) or 0) + 1
    rec["last_seen"] = now_ts
    if rec["attempts"] >= LOGIN_MAX_ATTEMPTS:
        rec["blocked_until"] = now_ts + LOGIN_BLOCK_SECONDS
    _LOGIN_ATTEMPTS[attempt_key] = rec
    _cleanup_login_attempts(now_ts)
    return _login_block_remaining_seconds(attempt_key)


def _clear_login_attempts(attempt_key: str) -> None:
    _LOGIN_ATTEMPTS.pop(attempt_key, None)

def get_settings_dict():
    db = get_db()
    rows = rows_to_list(db.execute("SELECT key,value FROM app_settings").fetchall())
    db.close()
    settings = {
        "sacco_name": "SACCOFinance",
        "logo_text": "SF",
        "logo_image": "",
        "logo_url": "",
        "address": "",
        "phone": "",
        "account_opening_balance": "0",
    }
    settings.update({r["key"]: r["value"] for r in rows})
    return settings

def get_account_opening_balance(db) -> float:
    opening_balance_row = db.execute(
        "SELECT value FROM app_settings WHERE key='account_opening_balance'"
    ).fetchone()
    try:
        return float((opening_balance_row["value"] if opening_balance_row else 0) or 0)
    except (TypeError, ValueError):
        return 0.0

def set_account_opening_balance(db, value: float) -> float:
    new_value = float(value or 0)
    db.execute(
        "INSERT INTO app_settings (key,value,updated_at) VALUES (?,?,datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
        ("account_opening_balance", str(new_value)),
    )
    return new_value

def adjust_account_opening_balance(db, delta: float) -> float:
    current = get_account_opening_balance(db)
    return set_account_opening_balance(db, current + float(delta or 0))

def build_monthly_account_report(db) -> dict:
    monthly_raw = rows_to_list(db.execute(
        """
        SELECT month,
               COALESCE(SUM(savings_collections),0) AS savings_collections,
               COALESCE(SUM(loan_repayments),0) AS loan_repayments,
               COALESCE(SUM(loan_disbursed),0) AS loan_disbursed,
               COALESCE(SUM(expenses),0) AS expenses
        FROM (
            SELECT strftime('%Y-%m', txn_date) AS month,
                   amount AS savings_collections,
                   0 AS loan_repayments,
                   0 AS loan_disbursed,
                   0 AS expenses
            FROM savings_transactions
            WHERE type='deposit'

            UNION ALL

            SELECT strftime('%Y-%m', payment_date) AS month,
                   0 AS savings_collections,
                   amount AS loan_repayments,
                   0 AS loan_disbursed,
                   0 AS expenses
            FROM repayments

            UNION ALL

            SELECT strftime('%Y-%m', disbursed_date) AS month,
                   0 AS savings_collections,
                   0 AS loan_repayments,
                   amount AS loan_disbursed,
                   0 AS expenses
            FROM loans
            WHERE disbursed_date IS NOT NULL

            UNION ALL

            SELECT strftime('%Y-%m', expense_date) AS month,
                   0 AS savings_collections,
                   0 AS loan_repayments,
                   0 AS loan_disbursed,
                   amount AS expenses
            FROM expense_transactions
        )
        WHERE month IS NOT NULL AND month != ''
        GROUP BY month
        ORDER BY month ASC
        """
    ).fetchall())

    current_balance = get_account_opening_balance(db)
    if not monthly_raw:
        return {
            "opening_balance": current_balance,
            "closing_balance": current_balance,
            "months": [],
            "totals": {
                "savings_collections": 0.0,
                "loan_repayments": 0.0,
                "inflow": 0.0,
                "loan_disbursed": 0.0,
                "expenses": 0.0,
                "outflow": 0.0,
                "net": 0.0,
            },
        }

    by_month = {r["month"]: r for r in monthly_raw if r.get("month")}
    overall_net = 0.0
    for row in by_month.values():
        savings = float(row.get("savings_collections") or 0)
        repaid = float(row.get("loan_repayments") or 0)
        disbursed = float(row.get("loan_disbursed") or 0)
        expenses = float(row.get("expenses") or 0)
        overall_net += (savings + repaid) - (disbursed + expenses)

    opening_balance = current_balance - overall_net
    month_keys = sorted(by_month.keys())
    start_month = datetime.strptime(f"{month_keys[0]}-01", "%Y-%m-%d").date()
    end_month = datetime.strptime(f"{month_keys[-1]}-01", "%Y-%m-%d").date()

    def next_month(d: date) -> date:
        if d.month == 12:
            return date(d.year + 1, 1, 1)
        return date(d.year, d.month + 1, 1)

    rows = []
    running_balance = opening_balance
    totals = {
        "savings_collections": 0.0,
        "loan_repayments": 0.0,
        "inflow": 0.0,
        "loan_disbursed": 0.0,
        "expenses": 0.0,
        "outflow": 0.0,
        "net": 0.0,
    }
    cursor = start_month
    while cursor <= end_month:
        month_key = cursor.strftime("%Y-%m")
        source = by_month.get(month_key, {})
        savings_collections = float(source.get("savings_collections") or 0)
        loan_repayments = float(source.get("loan_repayments") or 0)
        loan_disbursed = float(source.get("loan_disbursed") or 0)
        expenses = float(source.get("expenses") or 0)
        inflow = savings_collections + loan_repayments
        outflow = loan_disbursed + expenses
        net = inflow - outflow
        opening = running_balance
        closing = opening + net

        rows.append({
            "month": month_key,
            "opening_balance": opening,
            "savings_collections": savings_collections,
            "loan_repayments": loan_repayments,
            "inflow": inflow,
            "loan_disbursed": loan_disbursed,
            "expenses": expenses,
            "outflow": outflow,
            "net": net,
            "closing_balance": closing,
        })

        totals["savings_collections"] += savings_collections
        totals["loan_repayments"] += loan_repayments
        totals["inflow"] += inflow
        totals["loan_disbursed"] += loan_disbursed
        totals["expenses"] += expenses
        totals["outflow"] += outflow
        totals["net"] += net

        running_balance = closing
        cursor = next_month(cursor)

    return {
        "opening_balance": opening_balance,
        "closing_balance": running_balance,
        "months": rows,
        "totals": totals,
    }


ACCOUNTING_ACCOUNTS = [
    {"code": "1000", "name": "Main Cash / Bank", "type": "asset"},
    {"code": "1100", "name": "Loan Portfolio Receivable", "type": "asset"},
    {"code": "2100", "name": "Member Savings Liability", "type": "liability"},
    {"code": "3000", "name": "Opening Capital / Equity", "type": "equity"},
    {"code": "4000", "name": "Interest Income", "type": "income"},
    {"code": "5100", "name": "Operating Expenses", "type": "expense"},
]
ACCOUNT_BY_CODE = {a["code"]: a for a in ACCOUNTING_ACCOUNTS}


def _journal_line(account_code: str, debit: float = 0, credit: float = 0) -> dict:
    account = ACCOUNT_BY_CODE[account_code]
    return {
        "account_code": account_code,
        "account_name": account["name"],
        "account_type": account["type"],
        "debit": round(float(debit or 0), 2),
        "credit": round(float(credit or 0), 2),
    }


def _add_journal_entry(entries: list, source: str, source_id: str, entry_date: str, description: str, lines: list) -> None:
    clean_lines = [line for line in lines if float(line.get("debit") or 0) or float(line.get("credit") or 0)]
    if not clean_lines:
        return
    total_debit = round(sum(float(line["debit"] or 0) for line in clean_lines), 2)
    total_credit = round(sum(float(line["credit"] or 0) for line in clean_lines), 2)
    entries.append({
        "id": f"JE{len(entries) + 1:06d}",
        "source": source,
        "source_id": source_id,
        "entry_date": clean_date(entry_date),
        "description": description,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balanced": abs(total_debit - total_credit) < 0.01,
        "lines": clean_lines,
    })


def _repayment_allocations(db) -> dict:
    schedules = {}
    for row in rows_to_list(db.execute(
        "SELECT loan_id, installment, principal, interest FROM loan_schedule ORDER BY loan_id, installment"
    ).fetchall()):
        schedules.setdefault(row["loan_id"], []).append({
            "principal_remaining": float(row.get("principal") or 0),
            "interest_remaining": float(row.get("interest") or 0),
        })

    allocations = {}
    repayments = rows_to_list(db.execute(
        "SELECT id, loan_id, amount FROM repayments ORDER BY loan_id, payment_date, created_at"
    ).fetchall())
    for repayment in repayments:
        remaining = float(repayment.get("amount") or 0)
        principal = 0.0
        interest = 0.0
        for slot in schedules.get(repayment["loan_id"], []):
            if remaining <= 0:
                break
            pay_interest = min(remaining, slot["interest_remaining"])
            slot["interest_remaining"] -= pay_interest
            interest += pay_interest
            remaining -= pay_interest
            if remaining <= 0:
                break
            pay_principal = min(remaining, slot["principal_remaining"])
            slot["principal_remaining"] -= pay_principal
            principal += pay_principal
            remaining -= pay_principal
        if remaining > 0:
            principal += remaining
        allocations[repayment["id"]] = {
            "principal": round(principal, 2),
            "interest": round(interest, 2),
        }
    return allocations


def build_accounting_journal(db) -> list:
    entries = []

    for row in rows_to_list(db.execute(
        """SELECT st.*, m.name AS member_name
           FROM savings_transactions st
           JOIN members m ON m.id=st.member_id
           ORDER BY st.txn_date, st.created_at"""
    ).fetchall()):
        amount = float(row.get("amount") or 0)
        if row.get("type") == "withdrawal":
            _add_journal_entry(entries, "savings_withdrawal", row["id"], row["txn_date"],
                f"Savings withdrawal - {row.get('member_name') or row['member_id']}",
                [_journal_line("2100", debit=amount), _journal_line("1000", credit=amount)])
        else:
            _add_journal_entry(entries, "savings_deposit", row["id"], row["txn_date"],
                f"Savings deposit - {row.get('member_name') or row['member_id']}",
                [_journal_line("1000", debit=amount), _journal_line("2100", credit=amount)])

    for row in rows_to_list(db.execute(
        """SELECT l.*, m.name AS member_name
           FROM loans l JOIN members m ON m.id=l.member_id
           WHERE l.disbursed_date IS NOT NULL
           ORDER BY l.disbursed_date, l.created_at"""
    ).fetchall()):
        amount = float(row.get("amount") or 0)
        _add_journal_entry(entries, "loan_disbursement", row["id"], row["disbursed_date"],
            f"Loan disbursement - {row.get('member_name') or row['member_id']}",
            [_journal_line("1100", debit=amount), _journal_line("1000", credit=amount)])

    allocations = _repayment_allocations(db)
    for row in rows_to_list(db.execute(
        """SELECT r.*, m.name AS member_name
           FROM repayments r JOIN members m ON m.id=r.member_id
           ORDER BY r.payment_date, r.created_at"""
    ).fetchall()):
        amount = float(row.get("amount") or 0)
        allocation = allocations.get(row["id"], {"principal": amount, "interest": 0})
        principal = min(amount, float(allocation.get("principal") or 0))
        interest = max(0.0, amount - principal)
        _add_journal_entry(entries, "loan_repayment", row["id"], row["payment_date"],
            f"Loan repayment {row['loan_id']} - {row.get('member_name') or row['member_id']}",
            [
                _journal_line("1000", debit=amount),
                _journal_line("1100", credit=principal),
                _journal_line("4000", credit=interest),
            ])

    for row in rows_to_list(db.execute(
        """SELECT et.*, ea.name AS account_name
           FROM expense_transactions et
           JOIN expense_accounts ea ON ea.id=et.account_id
           ORDER BY et.expense_date, et.created_at"""
    ).fetchall()):
        amount = float(row.get("amount") or 0)
        _add_journal_entry(entries, "expense", row["id"], row["expense_date"],
            f"Expense - {row.get('account_name') or 'Operating expense'}",
            [_journal_line("5100", debit=amount), _journal_line("1000", credit=amount)])

    cash_delta = 0.0
    for entry in entries:
        for line in entry["lines"]:
            if line["account_code"] == "1000":
                cash_delta += float(line["debit"] or 0) - float(line["credit"] or 0)
    current_cash = get_account_opening_balance(db)
    opening_cash = round(current_cash - cash_delta, 2)
    if abs(opening_cash) >= 0.01:
        if opening_cash > 0:
            lines = [_journal_line("1000", debit=opening_cash), _journal_line("3000", credit=opening_cash)]
        else:
            lines = [_journal_line("3000", debit=abs(opening_cash)), _journal_line("1000", credit=abs(opening_cash))]
        _add_journal_entry(entries, "opening_balance", "OPENING", "1900-01-01",
            "Opening balance brought forward", lines)

    entries.sort(key=lambda e: (e["entry_date"], e["source"], e["source_id"]))
    for idx, entry in enumerate(entries, start=1):
        entry["id"] = f"JE{idx:06d}"
    return entries


def _filter_journal(entries: list, date_from: str = "", date_to: str = "", source: str = "") -> list:
    if date_from:
        date_from = clean_date(date_from)
        entries = [entry for entry in entries if entry["entry_date"] >= date_from]
    if date_to:
        date_to = clean_date(date_to)
        entries = [entry for entry in entries if entry["entry_date"] <= date_to]
    if source:
        entries = [entry for entry in entries if entry["source"] == source]
    return entries


def _account_balances(entries: list) -> dict:
    balances = {
        account["code"]: {
            **account,
            "debit": 0.0,
            "credit": 0.0,
            "net": 0.0,
            "balance": 0.0,
        }
        for account in ACCOUNTING_ACCOUNTS
    }
    for entry in entries:
        for line in entry["lines"]:
            row = balances[line["account_code"]]
            row["debit"] += float(line.get("debit") or 0)
            row["credit"] += float(line.get("credit") or 0)
    for row in balances.values():
        row["debit"] = round(row["debit"], 2)
        row["credit"] = round(row["credit"], 2)
        row["net"] = round(row["debit"] - row["credit"], 2)
        if row["type"] in ("asset", "expense"):
            row["balance"] = row["net"]
        else:
            row["balance"] = round(row["credit"] - row["debit"], 2)
    return balances


def build_trial_balance(db, date_from: str = "", date_to: str = "") -> dict:
    entries = _filter_journal(build_accounting_journal(db), date_from, date_to)
    rows = []
    total_debit = 0.0
    total_credit = 0.0
    for row in _account_balances(entries).values():
        net = float(row["net"] or 0)
        debit_balance = net if net > 0 else 0.0
        credit_balance = abs(net) if net < 0 else 0.0
        total_debit += debit_balance
        total_credit += credit_balance
        rows.append({**row, "debit_balance": round(debit_balance, 2), "credit_balance": round(credit_balance, 2)})
    return {
        "rows": rows,
        "totals": {
            "debit": round(total_debit, 2),
            "credit": round(total_credit, 2),
            "balanced": abs(total_debit - total_credit) < 0.01,
        },
    }


def build_profit_loss(db, date_from: str = "", date_to: str = "") -> dict:
    balances = _account_balances(_filter_journal(build_accounting_journal(db), date_from, date_to))
    income_rows = [row for row in balances.values() if row["type"] == "income" and abs(row["balance"]) >= 0.01]
    expense_rows = [row for row in balances.values() if row["type"] == "expense" and abs(row["balance"]) >= 0.01]
    income = sum(float(row["balance"] or 0) for row in income_rows)
    expenses = sum(float(row["balance"] or 0) for row in expense_rows)
    return {
        "income": income_rows,
        "expenses": expense_rows,
        "totals": {
            "income": round(income, 2),
            "expenses": round(expenses, 2),
            "net_profit": round(income - expenses, 2),
        },
    }


def build_balance_sheet(db, date_to: str = "") -> dict:
    entries = _filter_journal(build_accounting_journal(db), "", date_to)
    balances = _account_balances(entries)
    assets = [row for row in balances.values() if row["type"] == "asset" and abs(row["balance"]) >= 0.01]
    liabilities = [row for row in balances.values() if row["type"] == "liability" and abs(row["balance"]) >= 0.01]
    equity = [row for row in balances.values() if row["type"] == "equity" and abs(row["balance"]) >= 0.01]
    pnl = build_profit_loss(db, "", date_to)
    retained = pnl["totals"]["net_profit"]
    if abs(retained) >= 0.01:
        equity.append({
            "code": "3900",
            "name": "Retained Earnings / Current Profit",
            "type": "equity",
            "debit": 0.0,
            "credit": 0.0,
            "net": -retained,
            "balance": retained,
        })
    total_assets = sum(float(row["balance"] or 0) for row in assets)
    total_liabilities = sum(float(row["balance"] or 0) for row in liabilities)
    total_equity = sum(float(row["balance"] or 0) for row in equity)
    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "totals": {
            "assets": round(total_assets, 2),
            "liabilities": round(total_liabilities, 2),
            "equity": round(total_equity, 2),
            "liabilities_and_equity": round(total_liabilities + total_equity, 2),
            "balanced": abs(total_assets - (total_liabilities + total_equity)) < 0.01,
        },
    }


def build_cash_flow_statement(db, date_from: str = "", date_to: str = "") -> dict:
    entries = _filter_journal(build_accounting_journal(db), date_from, date_to)
    by_month = {}
    for entry in entries:
        if entry["source"] == "opening_balance":
            continue
        month = entry["entry_date"][:7]
        row = by_month.setdefault(month, {
            "month": month,
            "operating": 0.0,
            "investing": 0.0,
            "financing": 0.0,
            "net_cash_flow": 0.0,
        })
        cash_line = next((line for line in entry["lines"] if line["account_code"] == "1000"), None)
        cash_delta = float(cash_line.get("debit") or 0) - float(cash_line.get("credit") or 0) if cash_line else 0.0
        if entry["source"] == "loan_repayment":
            interest = sum(float(line.get("credit") or 0) for line in entry["lines"] if line["account_code"] == "4000")
            principal = cash_delta - interest
            row["operating"] += interest
            row["investing"] += principal
        elif entry["source"] == "expense":
            row["operating"] += cash_delta
        elif entry["source"] == "loan_disbursement":
            row["investing"] += cash_delta
        elif entry["source"] in ("savings_deposit", "savings_withdrawal"):
            row["financing"] += cash_delta
        row["net_cash_flow"] += cash_delta

    rows = []
    totals = {"operating": 0.0, "investing": 0.0, "financing": 0.0, "net_cash_flow": 0.0}
    for row in [by_month[key] for key in sorted(by_month.keys())]:
        for key in totals:
            row[key] = round(row[key], 2)
            totals[key] += row[key]
        rows.append(row)
    return {"months": rows, "totals": {k: round(v, 2) for k, v in totals.items()}}

def pdf_escape(value) -> str:
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def pdf_clean(value) -> str:
    return str(value if value is not None else "").encode("latin-1", "replace").decode("latin-1")

def pdf_money(value) -> str:
    return f"KES {float(value or 0):,.2f}"

def pdf_date(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    try:
        return datetime.fromisoformat(raw[:10]).strftime("%d %b %Y")
    except Exception:
        return raw[:10]

def pdf_text(content, x, y, size=9, font="F1", color=(24, 32, 51), align="left", max_chars=None):
    text = pdf_clean(content)
    if max_chars and len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "..."
    width = len(text) * size * 0.48
    if align == "right":
        x = x - width
    elif align == "center":
        x = x - (width / 2)
    r, g, b = [c / 255 for c in color]
    return f"BT /{font} {size} Tf {r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {y:.2f} Td ({pdf_escape(text)}) Tj ET"

def pdf_rect(x, y, w, h, fill=None, stroke=None, line_width=0.6):
    ops = ["q"]
    if fill:
        r, g, b = [c / 255 for c in fill]
        ops.append(f"{r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
    if stroke:
        r, g, b = [c / 255 for c in stroke]
        ops.append(f"{line_width:.2f} w {r:.3f} {g:.3f} {b:.3f} RG {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")
    ops.append("Q")
    return "\n".join(ops)

def pdf_line(x1, y1, x2, y2, color=(216, 222, 232), line_width=0.6):
    r, g, b = [c / 255 for c in color]
    return f"q {line_width:.2f} w {r:.3f} {g:.3f} {b:.3f} RG {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S Q"

def pdf_jpeg_from_data_url(value):
    match = re.match(r"^data:image/jpeg;base64,(.+)$", str(value or ""), re.I)
    if not match:
        return None
    try:
        return base64.b64decode(match.group(1), validate=True)
    except Exception:
        return None

def make_pdf_from_pages(page_streams, title="Loan Statement", logo_image="") -> bytes:
    page_count = len(page_streams)
    logo_bytes = pdf_jpeg_from_data_url(logo_image)
    font_start = 3 + page_count
    image_start = font_start + 2
    content_start = image_start + (1 if logo_bytes else 0)
    page_refs = " ".join(f"{3 + i} 0 R" for i in range(page_count))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{page_refs}] /Count {page_count} >>".encode("ascii"),
    ]
    for i in range(page_count):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_start} 0 R /F2 {font_start + 1} 0 R >> "
            f"{('/XObject << /Logo ' + str(image_start) + ' 0 R >>') if logo_bytes else ''} >> "
            f"/Contents {content_start + i} 0 R >>"
        .encode("ascii"))
    objects.extend([
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ])
    if logo_bytes:
        objects.append(
            b"<< /Type /XObject /Subtype /Image /Width 512 /Height 512 "
            b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length "
            + str(len(logo_bytes)).encode("ascii") + b" >>\nstream\n" + logo_bytes + b"\nendstream"
        )
    for stream_text in page_streams:
        stream = stream_text.encode("latin-1", "replace")
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")

    pdf = BytesIO()
    pdf.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(pdf.tell())
        pdf.write(f"{i} 0 obj\n".encode("ascii"))
        pdf.write(obj)
        pdf.write(b"\nendobj\n")
    xref = pdf.tell()
    pdf.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.write(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.write(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii"))
    return pdf.getvalue()

def make_simple_pdf(lines, title="Loan Statement") -> bytes:
    y = 790
    ops = [pdf_text(title, 50, y, 14, "F2")]
    y -= 22
    for line in lines:
        ops.append(pdf_text(line, 50, y, 10))
        y -= 14
    return make_pdf_from_pages(["\n".join(ops)], title)

def get_loan_statement_data(loan_id):
    db = get_db()
    loan = row_to_dict(db.execute(
        """SELECT l.*, m.name as member_name, m.phone as member_phone, m.address as member_address, m.member_type
           FROM loans l JOIN members m ON l.member_id=m.id WHERE l.id=?""", (loan_id,)
    ).fetchone())
    if not loan:
        db.close()
        return None
    schedule = rows_to_list(db.execute("SELECT * FROM loan_schedule WHERE loan_id=? ORDER BY installment", (loan_id,)).fetchall())
    repays = rows_to_list(db.execute("SELECT * FROM repayments WHERE loan_id=? ORDER BY payment_date", (loan_id,)).fetchall())
    db.close()
    return {
        "loan": loan,
        "schedule": schedule,
        "repays": repays,
        "settings": get_settings_dict(),
        "summary": loan_summary(loan, schedule),
    }

def build_statement_pdf(loan_id, data) -> bytes:
    loan = data["loan"]
    summary = data["summary"]
    settings = data["settings"]
    brand = settings.get("sacco_name") or "SACCOFinance"
    pages = []
    ops = []
    margin = 42
    width = 511
    blue = (23, 32, 51)
    muted = (100, 116, 139)
    border = (214, 221, 232)
    soft = (247, 249, 252)
    accent = (37, 99, 235)

    def add_header(page_no=1):
        o = [
            pdf_rect(0, 782, 595, 60, fill=blue),
            pdf_rect(margin, 798, 34, 34, fill=accent),
            ("q 34 0 0 34 %.2f %.2f cm /Logo Do Q" % (margin, 798)) if pdf_jpeg_from_data_url(settings.get("logo_image")) else pdf_text((settings.get("logo_text") or brand[:2]).upper()[:3], margin + 17, 810, 11, "F2", (255, 255, 255), "center"),
            pdf_text(brand, 86, 818, 16, "F2", (255, 255, 255), max_chars=34),
            pdf_text(settings.get("address") or "Loan management statement", 86, 803, 8, "F1", (213, 226, 255), max_chars=58),
            pdf_text(settings.get("phone") or "", 86, 791, 8, "F1", (213, 226, 255), max_chars=42),
            pdf_text("LOAN STATEMENT", 553, 818, 12, "F2", (255, 255, 255), "right"),
            pdf_text(f"Statement No: {loan_id}", 553, 803, 8, "F1", (213, 226, 255), "right"),
            pdf_text(f"Issued: {pdf_date(date.today().isoformat())}", 553, 791, 8, "F1", (213, 226, 255), "right"),
        ]
        if page_no > 1:
            o.append(pdf_text(f"Page {page_no}", 553, 766, 8, "F1", muted, "right"))
        return o

    def add_footer(o, page_no):
        o.extend([
            pdf_line(margin, 34, margin + width, 34, border),
            pdf_text("This statement is system-generated and reflects transactions recorded at the time of issue.", margin, 20, 7.5, "F1", muted),
            pdf_text(f"Page {page_no}", margin + width, 20, 7.5, "F1", muted, "right"),
        ])

    def section_title(o, title, y):
        o.append(pdf_text(title.upper(), margin, y, 9, "F2", blue))
        o.append(pdf_line(margin, y - 7, margin + width, y - 7, border))
        return y - 20

    def info_pair(o, label, value, x, y, w=222):
        o.append(pdf_text(label.upper(), x, y, 6.8, "F2", muted, max_chars=24))
        o.append(pdf_text(value or "-", x, y - 13, 9, "F1", blue, max_chars=max(18, int(w / 4.6))))

    ops.extend(add_header())
    y = 748
    ops.append(pdf_rect(margin, y - 78, width, 78, fill=soft, stroke=border))
    info_pair(ops, "Borrower", loan.get("member_name"), margin + 14, y - 24)
    info_pair(ops, "Phone", loan.get("member_phone"), margin + 280, y - 24)
    info_pair(ops, "Address", loan.get("member_address"), margin + 14, y - 56)
    info_pair(ops, "Customer Type", "External Borrower" if loan.get("member_type") == "borrower" else "Member", margin + 280, y - 56)

    y = 640
    cards = [
        ("Principal", pdf_money(loan.get("amount"))),
        ("Total Repayable", pdf_money(summary.get("total_repayable"))),
        ("Total Paid", pdf_money(summary.get("total_paid"))),
        ("Outstanding", pdf_money(summary.get("outstanding"))),
    ]
    card_w = (width - 18) / 4
    for i, (label, value) in enumerate(cards):
        x = margin + i * (card_w + 6)
        ops.append(pdf_rect(x, y - 58, card_w, 58, fill=(255, 255, 255), stroke=border))
        ops.append(pdf_text(label.upper(), x + 10, y - 19, 6.8, "F2", muted, max_chars=18))
        ops.append(pdf_text(value, x + 10, y - 39, 10.5, "F2", blue, max_chars=18))

    y = 548
    y = section_title(ops, "Loan Details", y)
    details = [
        ("Loan ID", loan_id),
        ("Status", loan.get("status")),
        ("Annual Rate", f"{loan.get('annual_rate')}% p.a."),
        ("Term", f"{loan.get('term_months')} months"),
        ("Penalties", pdf_money(summary.get("penalties"))),
        ("Statement Date", pdf_date(date.today().isoformat())),
    ]
    for idx, (label, value) in enumerate(details):
        x = margin + (idx % 3) * 170
        row_y = y - (idx // 3) * 34
        info_pair(ops, label, value, x, row_y, 150)

    y = 444
    y = section_title(ops, "Repayment Schedule", y)
    cols = [
        ("#", margin + 8, 28, "left"),
        ("Due Date", margin + 42, 78, "left"),
        ("Principal", margin + 156, 74, "right"),
        ("Interest", margin + 245, 64, "right"),
        ("Payment", margin + 330, 74, "right"),
        ("Balance", margin + 438, 74, "right"),
    ]
    def table_header(o, y_pos):
        o.append(pdf_rect(margin, y_pos - 18, width, 18, fill=(235, 240, 247), stroke=border))
        for label, x, _, align in cols:
            o.append(pdf_text(label, x, y_pos - 12, 7.5, "F2", blue, align))
        return y_pos - 18

    page_no = 1
    y = table_header(ops, y)
    row_h = 18
    schedule = data["schedule"]
    if schedule:
        for row in schedule:
            if y < 82:
                add_footer(ops, page_no)
                pages.append("\n".join(ops))
                page_no += 1
                ops = add_header(page_no)
                y = 752
                y = section_title(ops, "Repayment Schedule Continued", y)
                y = table_header(ops, y)
            fill = (255, 255, 255) if int(row.get("installment") or 0) % 2 else (250, 252, 255)
            ops.append(pdf_rect(margin, y - row_h, width, row_h, fill=fill, stroke=border, line_width=0.35))
            values = [
                row.get("installment"),
                pdf_date(row.get("due_date")),
                f"{float(row.get('principal') or 0):,.2f}",
                f"{float(row.get('interest') or 0):,.2f}",
                f"{float(row.get('repayment') or 0):,.2f}",
                f"{float(row.get('balance') or 0):,.2f}",
            ]
            for value, (_, x, _, align) in zip(values, cols):
                ops.append(pdf_text(value, x, y - 12, 7.5, "F1", blue, align, max_chars=16))
            y -= row_h
    else:
        ops.append(pdf_rect(margin, y - 28, width, 28, fill=(255, 255, 255), stroke=border))
        ops.append(pdf_text("Schedule will be available after approval.", margin + 10, y - 18, 8, "F1", muted))
        y -= 34

    y -= 22
    if y < 170:
        add_footer(ops, page_no)
        pages.append("\n".join(ops))
        page_no += 1
        ops = add_header(page_no)
        y = 752
    y = section_title(ops, "Repayments Received", y)
    repay_cols = [
        ("Date", margin + 8, "left"),
        ("Reference", margin + 124, "left"),
        ("Method", margin + 314, "left"),
        ("Amount", margin + 500, "right"),
    ]
    ops.append(pdf_rect(margin, y - 18, width, 18, fill=(235, 240, 247), stroke=border))
    for label, x, align in repay_cols:
        ops.append(pdf_text(label, x, y - 12, 7.5, "F2", blue, align))
    y -= 18
    if data["repays"]:
        for idx, row in enumerate(data["repays"]):
            if y < 82:
                add_footer(ops, page_no)
                pages.append("\n".join(ops))
                page_no += 1
                ops = add_header(page_no)
                y = 752
                y = section_title(ops, "Repayments Received Continued", y)
            fill = (255, 255, 255) if idx % 2 == 0 else (250, 252, 255)
            ops.append(pdf_rect(margin, y - row_h, width, row_h, fill=fill, stroke=border, line_width=0.35))
            repay_values = [
                pdf_date(row.get("payment_date")),
                row.get("reference") or row.get("id"),
                row.get("method"),
                f"{float(row.get('amount') or 0):,.2f}",
            ]
            for value, (_, x, align) in zip(repay_values, repay_cols):
                ops.append(pdf_text(value, x, y - 12, 7.5, "F1", blue, align, max_chars=30))
            y -= row_h
    else:
        ops.append(pdf_rect(margin, y - 28, width, 28, fill=(255, 255, 255), stroke=border))
        ops.append(pdf_text("No repayments recorded.", margin + 10, y - 18, 8, "F1", muted))

    add_footer(ops, page_no)
    pages.append("\n".join(ops))
    return make_pdf_from_pages(pages, f"Loan Statement {loan_id}", settings.get("logo_image") or "")

def next_loan_id(db) -> str:
    row = db.execute("""
        SELECT COALESCE(MAX(CAST(SUBSTR(id, 3) AS INTEGER)), 0) AS last_no
        FROM loans
        WHERE id GLOB 'LN[0-9]*'
    """).fetchone()
    return f"LN{int(row['last_no']) + 1:03d}"

def clean_date(value, fallback=None) -> str:
    raw = (value or fallback or date.today().isoformat())
    raw = str(raw).strip()[:10]
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return date.today().isoformat()

def refresh_loan_statuses(db) -> None:
    today = date.today().isoformat()
    db.execute(
        """UPDATE loans
           SET status='overdue'
           WHERE status='active'
             AND EXISTS (
                 SELECT 1 FROM loan_schedule s
                 WHERE s.loan_id=loans.id AND s.paid=0 AND s.due_date < ?
             )""",
        (today,),
    )
    db.execute(
        """UPDATE loans
           SET status='active'
           WHERE status='overdue'
             AND NOT EXISTS (
                 SELECT 1 FROM loan_schedule s
                 WHERE s.loan_id=loans.id AND s.paid=0 AND s.due_date < ?
             )""",
        (today,),
    )

def allocate_repayment_to_schedule(db, loan_id: str, paid_date: str | None = None) -> None:
    paid_date = clean_date(paid_date)
    total_paid = db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM repayments WHERE loan_id=?",
        (loan_id,),
    ).fetchone()[0]
    db.execute("UPDATE loan_schedule SET paid=0, paid_date=NULL WHERE loan_id=?", (loan_id,))
    rows = rows_to_list(db.execute(
        "SELECT id,repayment FROM loan_schedule WHERE loan_id=? ORDER BY installment",
        (loan_id,),
    ).fetchall())
    remaining = float(total_paid or 0)
    for row in rows:
        due = float(row["repayment"] or 0)
        if remaining + 0.01 >= due:
            db.execute("UPDATE loan_schedule SET paid=1, paid_date=? WHERE id=?", (paid_date, row["id"]))
            remaining -= due
        else:
            break
    total_repayable = db.execute(
        "SELECT COALESCE(SUM(repayment),0) FROM loan_schedule WHERE loan_id=?",
        (loan_id,),
    ).fetchone()[0]
    loan = row_to_dict(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone())
    if loan:
        status = loan["status"]
        if total_repayable and float(total_paid or 0) + 0.01 >= float(total_repayable):
            status = "completed"
        elif status == "completed" and float(total_paid or 0) + 0.01 < float(total_repayable):
            status = "active"
        db.execute("UPDATE loans SET total_paid=?, status=? WHERE id=?", (total_paid, status, loan_id))
        refresh_loan_statuses(db)

def loan_risk_snapshot(db, loan_id: str) -> dict:
    today = date.today().isoformat()
    row = row_to_dict(db.execute(
        """SELECT
             COALESCE(SUM(CASE WHEN paid=0 AND due_date < ? THEN repayment ELSE 0 END),0) AS amount_in_arrears,
             COALESCE(COUNT(CASE WHEN paid=0 AND due_date < ? THEN 1 END),0) AS overdue_installments,
             MIN(CASE WHEN paid=0 AND due_date < ? THEN due_date END) AS oldest_due_date,
             MIN(CASE WHEN paid=0 THEN due_date END) AS next_due_date
           FROM loan_schedule WHERE loan_id=?""",
        (today, today, today, loan_id),
    ).fetchone())
    oldest = row.get("oldest_due_date")
    days = 0
    if oldest:
        try:
            days = max(0, (date.today() - date.fromisoformat(oldest[:10])).days)
        except Exception:
            days = 0
    return {
        "amount_in_arrears": float(row.get("amount_in_arrears") or 0),
        "overdue_installments": int(row.get("overdue_installments") or 0),
        "oldest_due_date": oldest,
        "next_due_date": row.get("next_due_date"),
        "days_in_arrears": days,
    }

def rebuild_loan_schedule(db, loan: dict, start_date: str) -> None:
    db.execute("DELETE FROM loan_schedule WHERE loan_id=?", (loan["id"],))
    schedule = build_schedule(
        loan["id"], loan["amount"], loan["annual_rate"],
        loan["term_months"], loan["method"], start_date
    )
    for row in schedule:
        db.execute(
            "INSERT INTO loan_schedule (loan_id,installment,due_date,principal,interest,repayment,balance) VALUES (?,?,?,?,?,?,?)",
            (row["loan_id"], row["installment"], row["due_date"],
             row["principal"], row["interest"], row["repayment"], row["balance"])
        )

    if not schedule:
        return
    allocate_repayment_to_schedule(db, loan["id"], start_date)
