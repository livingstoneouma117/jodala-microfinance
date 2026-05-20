from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import Base, engine, SessionLocal
from .models import AppSetting, User
from .auth import hash_password
from .routers import (
    auth as auth_router,
    dashboard, clients, loans, repayments,
    savings, disbursements, schedules, reports, users, members, settings as settings_router,
    mpesa, sms, ai,
)

app = FastAPI(title="Jodala Chama Productivity System")

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")
app.state.templates = templates

@app.middleware("http")
async def disable_style_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.endswith("/static/style.css"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

def template_settings():
    db = SessionLocal()
    try:
        return db.query(AppSetting).filter(AppSetting.id == 1).first()
    finally:
        db.close()

templates.env.globals["app_settings"] = template_settings

# Create tables and seed admin user
Base.metadata.create_all(bind=engine)

def ensure_setting_columns():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(app_settings)"))}
        additions = {
            "chama_registration_no": "VARCHAR(80) NOT NULL DEFAULT ''",
            "org_short_name": "VARCHAR(40) NOT NULL DEFAULT 'SACCO'",
            "org_tagline": "VARCHAR(120) NOT NULL DEFAULT 'SACCO Management System'",
            "org_type": "VARCHAR(40) NOT NULL DEFAULT 'SACCO'",
            "org_country": "VARCHAR(80) NOT NULL DEFAULT 'Kenya'",
            "meeting_day": "VARCHAR(20) NOT NULL DEFAULT ''",
            "theme": "VARCHAR(20) NOT NULL DEFAULT 'dark'",
            "monthly_contribution": "NUMERIC(12, 2) NOT NULL DEFAULT 0",
            "late_payment_fee": "NUMERIC(12, 2) NOT NULL DEFAULT 0",
            "loan_approval_policy": "VARCHAR(30) NOT NULL DEFAULT 'treasurer'",
            "mpesa_balance": "NUMERIC(12, 2) NOT NULL DEFAULT 0",
            "email_host": "VARCHAR(120) NOT NULL DEFAULT ''",
            "email_port": "INTEGER NOT NULL DEFAULT 587",
            "email_username": "VARCHAR(120) NOT NULL DEFAULT ''",
            "email_password": "VARCHAR(255) NOT NULL DEFAULT ''",
            "email_use_tls": "INTEGER NOT NULL DEFAULT 1",
            "sms_username": "VARCHAR(120) NOT NULL DEFAULT ''",
            "sms_api_key": "VARCHAR(255) NOT NULL DEFAULT ''",
            "sms_sender_id": "VARCHAR(30) NOT NULL DEFAULT ''",
            "ai_api_key": "VARCHAR(255) NOT NULL DEFAULT ''",
            "ai_model": "VARCHAR(80) NOT NULL DEFAULT 'gpt-5.4-mini'",
            "reminder_auto_enabled": "INTEGER NOT NULL DEFAULT 0",
            "reminder_channel": "VARCHAR(20) NOT NULL DEFAULT 'sms'",
            "reminder_time": "VARCHAR(10) NOT NULL DEFAULT '08:00'",
            "mpesa_environment": "VARCHAR(20) NOT NULL DEFAULT 'sandbox'",
            "mpesa_shortcode": "VARCHAR(20) NOT NULL DEFAULT ''",
            "mpesa_paybill": "VARCHAR(20) NOT NULL DEFAULT ''",
            "mpesa_consumer_key": "VARCHAR(120) NOT NULL DEFAULT ''",
            "mpesa_consumer_secret": "VARCHAR(120) NOT NULL DEFAULT ''",
            "mpesa_passkey": "VARCHAR(255) NOT NULL DEFAULT ''",
            "mpesa_callback_url": "VARCHAR(255) NOT NULL DEFAULT ''",
        }
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE app_settings ADD COLUMN {name} {ddl}"))

ensure_setting_columns()

def ensure_user_columns():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
        additions = {
            "full_name": "VARCHAR(120) NOT NULL DEFAULT ''",
            "phone": "VARCHAR(30) NOT NULL DEFAULT ''",
            "email": "VARCHAR(120) NOT NULL DEFAULT ''",
            "can_view": "BOOLEAN NOT NULL DEFAULT 1",
            "can_edit": "BOOLEAN NOT NULL DEFAULT 0",
            "can_manage_users": "BOOLEAN NOT NULL DEFAULT 0",
            "status": "VARCHAR(20) NOT NULL DEFAULT 'active'",
            "last_login_at": "DATETIME",
        }
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))

ensure_user_columns()

def ensure_client_columns():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(clients)"))}
        additions = {
            "loan_id": "VARCHAR(30) NOT NULL DEFAULT ''",
            "email": "VARCHAR(120) NOT NULL DEFAULT ''",
        }
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE clients ADD COLUMN {name} {ddl}"))
        conn.execute(text("UPDATE clients SET loan_id = 'LN' || printf('%03d', id)"))

ensure_client_columns()

def ensure_member_columns():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(members)"))}
        additions = {
            "savings_balance": "NUMERIC(12, 2) NOT NULL DEFAULT 0",
        }
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE members ADD COLUMN {name} {ddl}"))

ensure_member_columns()

def ensure_savings_columns():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(savings)"))}
        if "member_id" not in columns:
            conn.execute(text("ALTER TABLE savings ADD COLUMN member_id INTEGER NOT NULL DEFAULT 0"))

ensure_savings_columns()

def seed_admin():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == settings.admin_username).first()
        if not user:
            db.add(User(
                username=settings.admin_username,
                full_name="Admin",
                password_hash=hash_password(settings.admin_password),
                role="admin",
                can_view=True,
                can_edit=True,
                can_manage_users=True,
                status="active",
            ))
            db.commit()
        elif not user.password_hash.startswith("$pbkdf2-sha256$"):
            user.password_hash = hash_password(settings.admin_password)
            db.commit()
        if user.role == "admin" and (not user.can_view or not user.can_edit or not user.can_manage_users):
            user.can_view = True
            user.can_edit = True
            user.can_manage_users = True
            db.commit()
    finally:
        db.close()

seed_admin()

def seed_settings():
    db = SessionLocal()
    try:
        if not db.query(AppSetting).filter(AppSetting.id == 1).first():
            db.add(AppSetting(
                id=1,
                business_name="Jodala",
                currency="KES",
                timezone="Africa/Nairobi",
                theme="dark",
                contact_phone="",
                contact_email="",
                address="",
                default_interest_rate=10,
                default_loan_term_months=12,
                mpesa_balance=0,
            ))
            db.commit()
    finally:
        db.close()

seed_settings()

app.include_router(auth_router.router)
app.include_router(dashboard.router)
app.include_router(clients.router, prefix="/clients", tags=["clients"])
app.include_router(loans.router, prefix="/loans", tags=["loans"])
app.include_router(repayments.router, prefix="/repayments", tags=["repayments"])
app.include_router(savings.router, prefix="/savings", tags=["savings"])
app.include_router(disbursements.router, prefix="/disbursements", tags=["disbursements"])
app.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(members.router, prefix="/members", tags=["members"])
app.include_router(settings_router.router, prefix="/settings", tags=["settings"])
app.include_router(mpesa.router, prefix="/mpesa", tags=["mpesa"])
app.include_router(sms.router, prefix="/sms", tags=["sms"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])

