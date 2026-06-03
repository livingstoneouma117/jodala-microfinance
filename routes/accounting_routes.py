from api import Blueprint

from services.common import *

accounting_bp = Blueprint("accounting", __name__)
bp = accounting_bp

@bp.route("/api/accounting/chart-of-accounts", methods=["GET"])
@login_required
def accounting_chart_of_accounts():
    return success(ACCOUNTING_ACCOUNTS)



@bp.route("/api/accounting/journal-entries", methods=["GET"])
@login_required
def accounting_journal_entries():
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    source = request.args.get("source", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    limit = int(request.args.get("limit", 15))
    db = get_db()
    entries = _filter_journal(build_accounting_journal(db), date_from, date_to, source)
    db.close()
    total = len(entries)
    start = (page - 1) * limit
    return success({
        "entries": entries[start:start + limit],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": -(-total // limit) if limit else 1,
    })



@bp.route("/api/accounting/general-ledger", methods=["GET"])
@login_required
def accounting_general_ledger():
    account_code = request.args.get("account_code", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    db = get_db()
    entries = _filter_journal(build_accounting_journal(db), date_from, date_to)
    db.close()
    rows = []
    running = 0.0
    for entry in entries:
        for line in entry["lines"]:
            if account_code and line["account_code"] != account_code:
                continue
            running += float(line.get("debit") or 0) - float(line.get("credit") or 0)
            rows.append({
                "entry_id": entry["id"],
                "entry_date": entry["entry_date"],
                "source": entry["source"],
                "source_id": entry["source_id"],
                "description": entry["description"],
                **line,
                "running_balance": round(running, 2),
            })
    return success({
        "account_code": account_code,
        "account": ACCOUNT_BY_CODE.get(account_code),
        "lines": rows,
    })



@bp.route("/api/accounting/trial-balance", methods=["GET"])
@login_required
def accounting_trial_balance():
    db = get_db()
    data = build_trial_balance(
        db,
        request.args.get("date_from", "").strip(),
        request.args.get("date_to", "").strip(),
    )
    db.close()
    return success(data)



@bp.route("/api/accounting/profit-loss", methods=["GET"])
@login_required
def accounting_profit_loss():
    db = get_db()
    data = build_profit_loss(
        db,
        request.args.get("date_from", "").strip(),
        request.args.get("date_to", "").strip(),
    )
    db.close()
    return success(data)



@bp.route("/api/accounting/balance-sheet", methods=["GET"])
@login_required
def accounting_balance_sheet():
    db = get_db()
    data = build_balance_sheet(db, request.args.get("date_to", "").strip())
    db.close()
    return success(data)



@bp.route("/api/accounting/cash-flow", methods=["GET"])
@login_required
def accounting_cash_flow():
    db = get_db()
    data = build_cash_flow_statement(
        db,
        request.args.get("date_from", "").strip(),
        request.args.get("date_to", "").strip(),
    )
    db.close()
    return success(data)

# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════

