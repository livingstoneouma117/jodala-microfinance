# Jodala Microfinance LMS (v3.0)

Jodala Microfinance LMS is a Flask + SQLite web app used to manage members, borrowers, loans, repayments, savings, expenses, and monthly account reporting.

## Tech Stack
- Backend: Python, Flask
- Frontend: Vanilla HTML, CSS, JavaScript (single-page UI in `index.html`)
- Database: SQLite
- Auth: JWT (PyJWT)

## What It Covers
- Staff login with role-based permissions (admin, officer, accountant, cashier)
- Member and external borrower records
- Loan lifecycle: application, approval, disbursement, repayment, completion
- Savings deposits and withdrawals
- Expense accounts and expense tracking
- Main account tracking (loan outflows, repayments/savings inflows, expenses outflows)
- Monthly reports and audit logs

## Project Layout
- `app.py`: Flask API routes and app bootstrapping
- `auth.py`: token generation/validation and auth decorators
- `database.py`: schema creation, migrations, bootstrap helpers
- `calculator.py`: loan schedule and summary calculations
- `index.html`: frontend UI and client-side logic
- `frontend/`: React componentized migration (`Dashboard`, `LoanForm`, `LoanList`, `MemberTable`)
- `requirements.txt`: Python dependencies
- `render.yaml`: Render deployment config

## Local Setup (Windows PowerShell)
1. `cd "C:\Users\USER\OneDrive\Desktop\jodala chama"`
2. `python -m venv .venv`
3. `.\.venv\Scripts\Activate.ps1`
4. `pip install -r requirements.txt`
5. `$env:DEBUG="true"`
6. `python app.py`

Open `http://localhost:5000`.

## Frontend Modernization (v3 React)
The existing UI at `/` remains active while migration happens in `/v3`.

1. `cd frontend`
2. `npm install`
3. `npm run build`
4. Start Flask (`python app.py`)
5. Open `http://localhost:5000/v3`

For local React development with hot reload:
1. `cd frontend`
2. `npm install`
3. `npm run dev`
4. Keep Flask running on `http://localhost:5000` for API proxy calls.

Phase 2 pages now available in v3:
- Dashboard (stats + charts)
- Loans (LoanForm modal + details modal)
- Members (profile/activity modal)
- Savings
- Repayments
- Reports (CSV/XLSX export)
- Settings

## Local Setup (Linux/macOS)
1. `cd /path/to/jodala chama`
2. `python3 -m venv .venv`
3. `source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. `DEBUG=true python app.py`

Open `http://localhost:5000`.

## Environment Variables
- `DB_PATH`: SQLite file path. Default is local `sacco.db`.
- `SECRET_KEY`: JWT signing secret.
- `JWT_ALGORITHM`: JWT algorithm (default `HS256`).
- `JWT_EXP_HOURS`: token expiry in hours (default `24`).
- `DEBUG`: Flask debug mode (`true` or `false`).
- `PORT`: server port (default `5000`).
- `SEED_DEMO_DATA`: seed sample data (`true` or `false`).
- `BOOTSTRAP_ADMIN`: auto-create admin user (`true` or `false`).
- `BOOTSTRAP_ADMIN_NAME`, `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_ADMIN_ROLE`: bootstrap admin settings.

## Deployment (Render)
This repo includes `render.yaml` for deployment.

Current production setup uses:
- Web service runtime: Python
- Start command: `python app.py`
- Health endpoint: `GET /api/health`
- Persistent disk path: `/var/data`
- Production DB path: `/var/data/sacco.db`

## API Health Check
- Endpoint: `GET /api/health`
- Response includes app status, version, and timestamp.

## Notes
- If `SEED_DEMO_DATA=true`, demo users and sample records may be inserted.
- For production, keep `SEED_DEMO_DATA=false` and set a strong `SECRET_KEY`.
- Create/update your admin credentials via bootstrap environment variables.
