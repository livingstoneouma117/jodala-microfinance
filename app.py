from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

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

FRONTEND_DIR = Path(__file__).resolve().parent
REACT_DIST_DIR = FRONTEND_DIR / "frontend" / "dist"

app = FastAPI(title="SACCOFinance LMS", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _serve_index(directory: Path) -> FileResponse:
    return FileResponse(directory / "index.html")


app.include_router(auth_bp.router)
app.include_router(members_bp.router)
app.include_router(loans_bp.router)
app.include_router(repayments_bp.router)
app.include_router(savings_bp.router)
app.include_router(expenses_bp.router)
app.include_router(reports_bp.router)
app.include_router(accounting_bp.router)
app.include_router(settings_bp.router)
app.include_router(dashboard_bp.router)


@app.options("/{path:path}", include_in_schema=False)
async def options_passthrough(path: str):
    return Response(status_code=204)


@app.get("/", include_in_schema=False)
async def index():
    return _serve_index(FRONTEND_DIR)


@app.get("/manifest.webmanifest", include_in_schema=False)
async def manifest():
    return FileResponse(FRONTEND_DIR / "manifest.webmanifest")


@app.get("/service-worker.js", include_in_schema=False)
async def service_worker():
    return FileResponse(FRONTEND_DIR / "service-worker.js")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(FRONTEND_DIR / "favicon.ico")


@app.get("/icons/{path:path}", include_in_schema=False)
async def icon_asset(path: str):
    asset = FRONTEND_DIR / "icons" / path
    if asset.exists():
        return FileResponse(asset)
    return Response(status_code=404)


@app.get("/v3", include_in_schema=False)
@app.get("/v3/{path:path}", include_in_schema=False)
async def index_v3(path: str = ""):
    asset = REACT_DIST_DIR / path if path else None
    if asset and asset.exists():
        return FileResponse(asset)
    return _serve_index(REACT_DIST_DIR)


@app.post("/api/calculate")
async def calculate(req: Request):
    d = await req.json() if req else {}
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


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "3.0.0", "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    debug_mode = os.environ.get("DEBUG", "false").strip().lower() == "true"
    print(f"SACCOFinance API running on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=debug_mode, log_level="info")
