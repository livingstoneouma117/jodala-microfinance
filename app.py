from flask import Flask, jsonify, request, send_from_directory, make_response
import os
from datetime import date, datetime

from database import init_db
from services.common import *
from routes.auth_routes import auth_bp
from routes.members_routes import members_bp
from routes.loans_routes import loans_bp
from routes.repayments_routes import repayments_bp
from routes.savings_routes import savings_bp
from routes.expenses_routes import expenses_bp
from routes.reports_routes import reports_bp
from routes.accounting_routes import accounting_bp
from routes.settings_routes import settings_bp
from routes.dashboard_routes import dashboard_bp

FRONTEND_DIR = os.path.dirname(__file__)
REACT_DIST_DIR = os.path.join(FRONTEND_DIR, "frontend", "dist")
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

# Manual CORS (no flask-cors available)
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    return response

@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        return make_response("", 204)

app.register_blueprint(auth_bp)
app.register_blueprint(members_bp)
app.register_blueprint(loans_bp)
app.register_blueprint(repayments_bp)
app.register_blueprint(savings_bp)
app.register_blueprint(expenses_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(accounting_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(dashboard_bp)

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/v3", defaults={"path": ""})
@app.route("/v3/<path:path>")
def index_v3(path):
    if path and os.path.exists(os.path.join(REACT_DIST_DIR, path)):
        return send_from_directory(REACT_DIST_DIR, path)
    return send_from_directory(REACT_DIST_DIR, "index.html")

# LOAN CALCULATOR (public - no auth)
@app.route("/api/calculate", methods=["POST"])
def calculate():
    d = request.json or {}
    try:
        principal = float(d["amount"])
        annual_rate = float(d["annual_rate"])
        term_months = int(d["term_months"])
        method = d.get("method", "reducing")
        start = d.get("start_date", date.today().isoformat())
    except (KeyError, ValueError, TypeError):
        return error("amount, annual_rate, term_months required")

    schedule = build_schedule("CALC", principal, annual_rate, term_months, method, start)
    total_repayable = sum(r["repayment"] for r in schedule)
    total_interest = sum(r["interest"] for r in schedule)
    return success({
        "monthly_repayment": schedule[0]["repayment"] if schedule else 0,
        "total_repayable": round(total_repayable, 2),
        "total_interest": round(total_interest, 2),
        "schedule": schedule[:6],
    })

# HEALTH CHECK
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "3.0.0", "timestamp": datetime.utcnow().isoformat()})

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    debug_mode = os.environ.get("DEBUG", "false").strip().lower() == "true"
    print(f"SACCOFinance API running on http://localhost:{port}")
    app.run(debug=debug_mode, port=port, host="0.0.0.0")