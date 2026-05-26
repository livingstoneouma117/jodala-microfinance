# Jodala Frontend v3 (React)

This folder contains the componentized frontend migration baseline.

## Included Components
- Dashboard
- LoanForm
- LoanList
- MemberTable
- DataTable
- Modal
- StatCard
- Toast notifications

## Local Development
1. cd frontend
2. npm install
3. npm run dev

The Vite dev server proxies /api/* to http://localhost:5000.

## Build and Serve From Flask
Option A (npm/Vite):
1. npm run build
2. Start Flask app
3. Open http://localhost:5000/v3

Option B (Python-only build, used by Render):
1. python build_frontend.py
2. Start Flask app
3. Open http://localhost:5000/v3

Flask serves built files from frontend/dist.
