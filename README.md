# SACCOFinance LMS v3.0
### Microfinance Loan Management System

A full-stack web application for SACCOs, cooperatives, and small lending businesses.
Built with **Python Flask** (backend) + **Vanilla HTML/CSS/JS** (frontend) + **SQLite** (database).

---

## 📋 Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Quick Start](#quick-start)
- [Deployment](#deployment)
- [User Roles](#user-roles)
- [Loan Calculation Logic](#loan-calculation-logic)

---

## ✨ Features

### Authentication & Security
- JWT-based authentication (24-hour expiry)
- SHA-256 password hashing
- Role-based access control (Admin, Officer, Accountant, Cashier)
- CORS headers for API access
- Audit logging on all write operations

### Member Management
- Register members with full KYC details (name, phone, email, national ID, gender, DOB, address)
- Search and filter by name, ID, phone, or email
- View member profiles with loan history and savings transactions
- Status management: Active / Suspended / Blacklisted
- Paginated member listing

### Loan Management
- Multi-product loan support (Business, Emergency, Asset Finance, School Fees)
- Two interest calculation methods:
  - **Flat Rate**: Interest calculated on original principal throughout
  - **Reducing Balance**: Interest calculated on outstanding balance each period
- Full amortization schedule generation at disbursement
- Loan lifecycle: Pending → Approved/Disbursed → Active → Completed (or Overdue)
- Loan rejection with reason tracking
- Penalty calculation for overdue installments
- Real-time loan preview (monthly repayment, total interest, total repayable)

### Savings Management
- Individual savings accounts per member
- Deposit and withdrawal recording
- Mandatory vs Voluntary savings categories
- Auto-reference number generation (DEP-XXXX / WDR-XXXX)
- Running balance tracking per transaction
- Savings transaction history with search/filter

### Repayment Management
- Record repayments against any active/overdue loan
- Payment methods: Cash, M-Pesa, Bank Transfer
- Auto-reference generation per method (QK-XXXX, BNK-XXXX, CSH-XXXX)
- Auto-mark schedule installments as paid
- Loan auto-completion when fully repaid
- Outstanding balance and next installment display

### Dashboard & Reports
- Live KPI stats: Active loans, Members, Total Savings, Overdue Loans
- Monthly repayments bar chart (last 6 months)
- Loan status donut chart
- Top borrowers leaderboard
- Recent loan applications feed
- Collection rate calculation

### Export & Reports
- Portfolio summary report (all loans with outstanding balances)
- Savings summary report (deposits, withdrawals, balances per member)
- CSV export for: Loans, Repayments, Savings, Members
- Audit log with module filtering

### Notifications
- System notifications for: approvals, disbursements, overdue alerts, reminders
- Unread badge count in sidebar
- Mark individual or all as read

### User Management (Admin only)
- Create system users with roles
- View all users and their access levels

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT BROWSER                           │
│                  Vanilla HTML + CSS + JavaScript                │
│           (Served by Flask static file handler)                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/REST (JSON)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLASK REST API (Port 5000)                   │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │  auth.py    │  │  app.py      │  │  calculator.py     │    │
│  │  JWT tokens │  │  All routes  │  │  Amortization      │    │
│  │  Password   │  │  CORS        │  │  Flat / Reducing   │    │
│  │  hashing    │  │  Middleware  │  │  Penalty calc      │    │
│  └─────────────┘  └──────────────┘  └────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   database.py                           │   │
│  │              SQLite via sqlite3 (built-in)              │   │
│  │              WAL mode + Foreign keys ON                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### File Structure
```
sacco-lms/
├── backend/
│   ├── app.py              # Flask app & all API routes (~900 lines)
│   ├── auth.py             # JWT auth, decorators, password utils
│   ├── calculator.py       # Loan schedule & penalty calculation
│   ├── database.py         # SQLite init, schema, seed data
│   ├── requirements.txt    # Python dependencies
│   └── sacco.db            # SQLite database (auto-created)
├── frontend/
│   └── index.html          # Complete SPA (~1,400 lines)
├── start.sh                # One-command startup script
└── README.md               # This file
```

---

## 🗄️ Database Schema

### users
| Column     | Type    | Description                          |
|------------|---------|--------------------------------------|
| id         | INTEGER | Primary key                          |
| name       | TEXT    | Full name                            |
| email      | TEXT    | Unique login email                   |
| password   | TEXT    | SHA-256 hashed password              |
| role       | TEXT    | admin / officer / accountant / cashier|
| active     | INTEGER | 1 = active, 0 = disabled             |
| created_at | TEXT    | ISO datetime                         |

### members
| Column      | Type  | Description                          |
|-------------|-------|--------------------------------------|
| id          | TEXT  | M + 8-char hex (e.g. M3A1B2C3D)     |
| name        | TEXT  | Full name                            |
| phone       | TEXT  | Phone number                         |
| email       | TEXT  | Email address                        |
| national_id | TEXT  | Unique national ID                   |
| gender      | TEXT  | M / F / O                            |
| dob         | TEXT  | Date of birth                        |
| address     | TEXT  | Physical address                     |
| status      | TEXT  | active / suspended / blacklisted     |
| joined_date | TEXT  | ISO date                             |
| savings     | REAL  | Current savings balance (denormalized)|
| created_by  | INT   | FK → users.id                        |

### loans
| Column        | Type  | Description                          |
|---------------|-------|--------------------------------------|
| id            | TEXT  | L + 8-char hex                       |
| member_id     | TEXT  | FK → members.id                      |
| product_id    | INT   | FK → loan_products.id                |
| amount        | REAL  | Principal amount                     |
| annual_rate   | REAL  | Annual interest rate (%)             |
| term_months   | INT   | Loan term in months                  |
| method        | TEXT  | flat / reducing                      |
| purpose       | TEXT  | Loan purpose description             |
| status        | TEXT  | pending/active/overdue/completed/rejected |
| applied_date  | TEXT  | Application date                     |
| approved_date | TEXT  | Approval date                        |
| disbursed_date| TEXT  | Disbursement date                    |
| approved_by   | INT   | FK → users.id                        |
| officer_id    | INT   | FK → users.id                        |
| total_paid    | REAL  | Running total of payments received   |
| penalties     | REAL  | Total penalties accumulated          |

### loan_schedule
| Column      | Type  | Description                          |
|-------------|-------|--------------------------------------|
| id          | INT   | Primary key                          |
| loan_id     | TEXT  | FK → loans.id                        |
| installment | INT   | Installment number (1, 2, 3...)      |
| due_date    | TEXT  | Expected payment date                |
| principal   | REAL  | Principal component                  |
| interest    | REAL  | Interest component                   |
| repayment   | REAL  | Total repayment due                  |
| balance     | REAL  | Remaining balance after this payment |
| paid        | INT   | 0 = unpaid, 1 = paid                 |
| paid_date   | TEXT  | Actual payment date                  |
| penalty     | REAL  | Penalty amount for this row          |

### repayments
| Column       | Type  | Description                          |
|--------------|-------|--------------------------------------|
| id           | TEXT  | R + 8-char hex                       |
| loan_id      | TEXT  | FK → loans.id                        |
| member_id    | TEXT  | FK → members.id                      |
| amount       | REAL  | Amount paid                          |
| payment_date | TEXT  | Date of payment                      |
| method       | TEXT  | cash / mpesa / bank                  |
| reference    | TEXT  | Receipt/transaction reference        |
| type         | TEXT  | installment / penalty / partial      |
| recorded_by  | INT   | FK → users.id                        |

### savings_accounts
| Column    | Type  | Description                          |
|-----------|-------|--------------------------------------|
| id        | INT   | Primary key                          |
| member_id | TEXT  | FK → members.id (unique)             |
| balance   | REAL  | Current balance                      |

### savings_transactions
| Column        | Type  | Description                          |
|---------------|-------|--------------------------------------|
| id            | TEXT  | ST + 8-char hex                      |
| member_id     | TEXT  | FK → members.id                      |
| type          | TEXT  | deposit / withdrawal                 |
| amount        | REAL  | Transaction amount                   |
| category      | TEXT  | mandatory / voluntary                |
| txn_date      | TEXT  | Transaction date                     |
| reference     | TEXT  | Auto-generated or provided reference |
| balance_after | REAL  | Account balance after transaction    |
| recorded_by   | INT   | FK → users.id                        |

### notifications
| Column     | Type  | Description                          |
|------------|-------|--------------------------------------|
| id         | INT   | Primary key                          |
| user_id    | INT   | FK → users.id (NULL = all users)     |
| type       | TEXT  | overdue/approved/reminder/disbursed  |
| message    | TEXT  | Notification message                 |
| read       | INT   | 0 = unread, 1 = read                 |

### audit_logs
| Column     | Type  | Description                          |
|------------|-------|--------------------------------------|
| id         | INT   | Primary key                          |
| user_id    | INT   | FK → users.id                        |
| user_name  | TEXT  | Denormalized user name               |
| action     | TEXT  | What was done                        |
| module     | TEXT  | Loans/Members/Savings/Repayments etc |
| details    | TEXT  | Additional context                   |
| ip_address | TEXT  | Client IP address                    |
| created_at | TEXT  | ISO datetime                         |

---

## 🔌 API Endpoints

### Authentication
| Method | Endpoint                  | Description                | Auth |
|--------|---------------------------|----------------------------|------|
| POST   | /api/auth/login           | Login & get JWT token      | ❌   |
| GET    | /api/auth/me              | Get current user info      | ✅   |
| POST   | /api/auth/change-password | Change password            | ✅   |

### Dashboard
| Method | Endpoint       | Description              | Roles    |
|--------|----------------|--------------------------|----------|
| GET    | /api/dashboard | Full dashboard stats     | All      |

### Members
| Method | Endpoint                    | Description              | Roles         |
|--------|-----------------------------|--------------------------|---------------|
| GET    | /api/members                | List members (paginated) | All           |
| POST   | /api/members                | Register new member      | Admin/Officer |
| GET    | /api/members/:id            | Get member + history     | All           |
| PUT    | /api/members/:id            | Update member details    | Admin/Officer |
| PATCH  | /api/members/:id/status     | Change member status     | Admin         |

### Loans
| Method | Endpoint                    | Description              | Roles         |
|--------|-----------------------------|--------------------------|---------------|
| GET    | /api/loans                  | List loans (paginated)   | All           |
| POST   | /api/loans                  | Submit loan application  | Admin/Officer |
| GET    | /api/loans/:id              | Loan detail + schedule   | All           |
| POST   | /api/loans/:id/approve      | Approve & disburse       | Admin         |
| POST   | /api/loans/:id/reject       | Reject application       | Admin         |
| GET    | /api/loans/:id/schedule     | Get repayment schedule   | All           |
| GET    | /api/loan-products          | Available loan products  | All           |

### Repayments
| Method | Endpoint         | Description              | Roles               |
|--------|------------------|--------------------------|---------------------|
| GET    | /api/repayments  | List repayments          | All                 |
| POST   | /api/repayments  | Record repayment         | Admin/Officer/Cashier|

### Savings
| Method | Endpoint                      | Description              | Roles         |
|--------|-------------------------------|--------------------------|---------------|
| GET    | /api/savings                  | Savings balances         | All           |
| GET    | /api/savings/transactions     | Transaction history      | All           |
| POST   | /api/savings/deposit          | Record deposit           | All except... |
| POST   | /api/savings/withdraw         | Process withdrawal       | All except... |

### Reports & Export
| Method | Endpoint                         | Description              | Roles |
|--------|----------------------------------|--------------------------|-------|
| GET    | /api/reports/portfolio           | Loan portfolio report    | All   |
| GET    | /api/reports/savings             | Savings summary          | All   |
| GET    | /api/reports/export/:type        | CSV download             | All   |

Types: `loans`, `repayments`, `savings`, `members`

### Notifications
| Method | Endpoint                        | Description              | Roles |
|--------|---------------------------------|--------------------------|-------|
| GET    | /api/notifications              | Get notifications        | All   |
| POST   | /api/notifications/read-all     | Mark all as read         | All   |
| PATCH  | /api/notifications/:id/read     | Mark one as read         | All   |

### System
| Method | Endpoint           | Description              | Roles |
|--------|--------------------|--------------------------|-------|
| GET    | /api/audit-logs    | Audit trail              | Admin/Accountant |
| GET    | /api/users         | List system users        | Admin |
| POST   | /api/users         | Create system user       | Admin |
| POST   | /api/calculate     | Loan preview calculator  | ❌    |
| GET    | /api/health        | Health check             | ❌    |

### Request/Response Format

All API responses follow this format:
```json
{
  "success": true,
  "message": "OK",
  "data": { ... }
}
```

Error responses:
```json
{
  "success": false,
  "error": "Error message here"
}
```

Authentication header:
```
Authorization: Bearer <jwt_token>
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- pip

### Installation

```bash
# 1. Clone or download the project
git clone <repo-url> sacco-lms
cd sacco-lms

# 2. Install Python dependencies
pip install -r backend/requirements.txt

# 3. Start the server (auto-seeds database on first run)
bash start.sh

# OR manually:
cd backend
python3 app.py
```

The app will be available at **http://localhost:5000**

### Demo Credentials

| Role        | Email                       | Password    |
|-------------|-----------------------------|-------------|
| Admin       | admin@sacco.co.ke           | admin123    |
| Loan Officer| officer@sacco.co.ke         | officer123  |
| Accountant  | accountant@sacco.co.ke      | acc123      |
| Cashier     | cashier@sacco.co.ke         | cashier123  |

---

## 🚢 Deployment

### Production with Gunicorn

```bash
pip install gunicorn
cd backend
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### With Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Environment Variables (Production)

Create `backend/.env`:
```env
SECRET_KEY=your-very-long-random-secret-key-here
DB_PATH=/var/lib/sacco/sacco.db
DEBUG=false
PORT=5000
```

Update `auth.py` to read from environment:
```python
import os
SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-dev-key")
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt gunicorn
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "backend.app:app"]
```

```bash
docker build -t sacco-lms .
docker run -p 5000:5000 -v $(pwd)/data:/app/backend sacco-lms
```

### PostgreSQL Migration (Production)

For high-volume production use, replace SQLite with PostgreSQL:
1. Install `psycopg2-binary`
2. Replace `sqlite3.connect()` with `psycopg2.connect(DATABASE_URL)`
3. Update `?` placeholders to `%s`
4. Add connection pooling with `psycopg2.pool`

---

## 👥 User Roles

| Feature              | Admin | Officer | Accountant | Cashier |
|----------------------|-------|---------|------------|---------|
| Dashboard            | ✅    | ✅      | ✅         | ✅      |
| View Members         | ✅    | ✅      | ✅         | ✅      |
| Register Members     | ✅    | ✅      | ❌         | ❌      |
| Blacklist Members    | ✅    | ❌      | ❌         | ❌      |
| Apply for Loans      | ✅    | ✅      | ❌         | ❌      |
| Approve/Reject Loans | ✅    | ❌      | ❌         | ❌      |
| Record Repayments    | ✅    | ✅      | ✅         | ✅      |
| Record Savings       | ✅    | ✅      | ✅         | ✅      |
| View Reports         | ✅    | ✅      | ✅         | ✅      |
| Export CSV           | ✅    | ✅      | ✅         | ✅      |
| Audit Logs           | ✅    | ❌      | ✅         | ❌      |
| User Management      | ✅    | ❌      | ❌         | ❌      |

---

## 📐 Loan Calculation Logic

### Reducing Balance (Most common for secured loans)

Each month, interest is calculated on the **remaining balance**:

```
monthly_rate = annual_rate / 12 / 100

monthly_repayment = principal × monthly_rate × (1 + monthly_rate)^n
                    ───────────────────────────────────────────────
                           (1 + monthly_rate)^n - 1

For each period:
  interest      = remaining_balance × monthly_rate
  principal_pay = monthly_repayment - interest
  balance       = balance - principal_pay
```

**Example**: KES 100,000 @ 18% p.a., 12 months
- Monthly repayment: **KES 9,168**
- Total interest: **KES 10,016**
- Total repayable: **KES 110,016**

### Flat Rate

Interest is calculated on the **original principal** for all periods:

```
monthly_interest  = (principal × annual_rate / 100) / 12
monthly_principal = principal / term_months
monthly_repayment = monthly_principal + monthly_interest
```

**Example**: KES 100,000 @ 18% p.a., 12 months
- Monthly repayment: **KES 9,833**
- Total interest: **KES 18,000**
- Total repayable: **KES 118,000**

### Penalty Calculation

```
penalty = (monthly_repayment × penalty_rate%) × months_overdue
```

Default penalty rate: **5% per month overdue**

---

## 🔒 Security Notes

1. **Change the SECRET_KEY** in `auth.py` before production deployment
2. **Use HTTPS** in production (with Nginx + Let's Encrypt)
3. **Backup the SQLite database** daily (`cp sacco.db sacco.db.backup`)
4. **Set DEBUG=False** in production
5. Consider migrating to **PostgreSQL** for multi-user concurrent access

---

## 📱 M-Pesa Integration (Optional Extension)

To add real M-Pesa Daraja API integration:

```python
# In app.py, add M-Pesa STK Push
import requests, base64, datetime

def mpesa_stk_push(phone, amount, account_ref):
    # Get access token
    token_url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    token_res = requests.get(token_url, auth=(CONSUMER_KEY, CONSUMER_SECRET))
    token = token_res.json()['access_token']

    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(f"{SHORTCODE}{PASSKEY}{timestamp}".encode()).decode()

    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": "https://yourdomain.com/api/mpesa/callback",
        "AccountReference": account_ref,
        "TransactionDesc": "Loan Repayment"
    }
    res = requests.post("https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
                        json=payload, headers={"Authorization": f"Bearer {token}"})
    return res.json()
```

---

## 📄 License

MIT License — Free for commercial and personal use.

---

*Built with ❤️ for African microfinance institutions*
