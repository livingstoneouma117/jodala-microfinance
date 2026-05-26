# Upgrade Roadmap (v3.x -> v4)

This document breaks the modernization work into deploy-safe phases.

## Phase 1 (Done in this update)
- Password hardening (complexity policy)
- Login rate limiting (anti-bruteforce)
- Excel export support (`.xlsx`) for reports
- Dark mode toggle with persistent user preference
- Member activity timeline (loans, savings, repayments)

## Phase 2 (Frontend Modernization) - Completed
Goal: move away from monolithic `index.html` to component architecture.

Current progress (implemented):
- Added `frontend/` React + Vite app
- Added reusable components:
  - `Dashboard`
  - `LoanForm`
  - `LoanList`
  - `MemberTable`
- Added shared UI primitives:
  - `DataTable` (with pagination)
  - `Modal`
  - `StatCard`
  - `Toast`
- Added missing feature pages:
  - `SavingsPage`
  - `RepaymentsPage`
  - `ReportsPage` (CSV/XLSX export)
  - `SettingsPage`
- Added dashboard charts (monthly repayment trend + loan status breakdown)
- Added Flask SPA serving route at `/v3` for built assets (`frontend/dist`)
- Kept legacy UI at `/` active to avoid deployment risk

Suggested stack:
- React + Vite + TypeScript
- React Query (API state)
- Zustand or Context (local UI state)
- Chart.js/Recharts for dashboard charts

Suggested component map:
- `DashboardPage`
- `LoansPage`
- `LoanFormModal`
- `LoanDetailsModal`
- `MembersPage`
- `MemberProfileModal`
- `SavingsPage`
- `RepaymentsPage`
- `ReportsPage`
- `SettingsPage`
- `Auth/LoginPage`
- Shared: `DataTable`, `StatCard`, `Modal`, `Toast`, `Pagination`

Migration approach:
1. Keep Flask API unchanged.
2. Create `frontend/` app and migrate one page at a time.
3. Serve built frontend from Flask static path.
4. Remove legacy inline JS only after parity is complete.

## Phase 3 (API Enhancement)
Goal: modular, typed API with better docs and async readiness.

Option A (low-risk first):
- Split `app.py` into Flask blueprints:
  - `routes/auth_routes.py`
  - `routes/loans_routes.py`
  - `routes/members_routes.py`
  - `routes/reports_routes.py`
  - `routes/savings_routes.py`
  - `routes/users_routes.py`
- Move shared utilities to `services/`.

Option B (higher-change):
- Migrate to FastAPI with Pydantic schemas.
- Keep SQLite initially; add SQLAlchemy models gradually.
- Expose OpenAPI for mobile/web integrations.

## Phase 4 (Realtime + Integrations)
- WebSocket/SSE notifications for approvals, repayments, account updates
- SMS/Email providers for status alerts
- Document audit + signature workflow

## Deployment Notes
- Keep Render deployment stable by shipping in small PRs.
- Add smoke tests for:
  - `/api/health`
  - login success/failure and lockout behavior
  - report export (CSV/XLSX)
