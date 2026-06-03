"""
SACCOFinance LMS - Database Layer (SQLite)
"""
import sqlite3
import os
from datetime import datetime

from security import hash_password

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "sacco.db")
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB_PATH)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # ── Users ────────────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        username    TEXT UNIQUE,
        email       TEXT UNIQUE NOT NULL,
        password    TEXT NOT NULL,
        role        TEXT NOT NULL DEFAULT 'cashier',
        permissions TEXT NOT NULL DEFAULT '[]',
        active      INTEGER NOT NULL DEFAULT 1,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )""")

    # ── Members ──────────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id            TEXT PRIMARY KEY,
        name          TEXT NOT NULL,
        phone         TEXT,
        email         TEXT,
        national_id   TEXT UNIQUE NOT NULL,
        gender        TEXT,
        dob           TEXT,
        address       TEXT,
        status        TEXT NOT NULL DEFAULT 'active',
        joined_date   TEXT NOT NULL,
        savings       REAL NOT NULL DEFAULT 0,
        member_type   TEXT NOT NULL DEFAULT 'member',
        created_by    INTEGER,
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (created_by) REFERENCES users(id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key        TEXT PRIMARY KEY,
        value      TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS login_attempts (
        attempt_key   TEXT PRIMARY KEY,
        attempts      INTEGER NOT NULL DEFAULT 0,
        window_start  REAL NOT NULL DEFAULT 0,
        blocked_until REAL NOT NULL DEFAULT 0,
        last_seen     REAL NOT NULL DEFAULT 0,
        updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
    )""")

    _migrate_schema(c)

    # ── Guarantors ───────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS guarantors (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        loan_id      TEXT,
        member_id    TEXT NOT NULL,
        guarantor_id TEXT NOT NULL,
        amount       REAL NOT NULL DEFAULT 0,
        status       TEXT NOT NULL DEFAULT 'active',
        notes        TEXT,
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (loan_id)      REFERENCES loans(id),
        FOREIGN KEY (member_id)    REFERENCES members(id),
        FOREIGN KEY (guarantor_id) REFERENCES members(id)
    )""")

    # ── Loan Products ────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS loan_products (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        min_amount      REAL NOT NULL,
        max_amount      REAL NOT NULL,
        min_term        INTEGER NOT NULL,
        max_term        INTEGER NOT NULL,
        annual_rate     REAL NOT NULL,
        method          TEXT NOT NULL DEFAULT 'reducing',
        penalty_rate    REAL NOT NULL DEFAULT 5,
        active          INTEGER NOT NULL DEFAULT 1
    )""")

    # ── Loans ────────────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS loans (
        id              TEXT PRIMARY KEY,
        member_id       TEXT NOT NULL,
        product_id      INTEGER,
        amount          REAL NOT NULL,
        annual_rate     REAL NOT NULL,
        term_months     INTEGER NOT NULL,
        method          TEXT NOT NULL DEFAULT 'reducing',
        purpose         TEXT,
        status          TEXT NOT NULL DEFAULT 'pending',
        applied_date    TEXT NOT NULL,
        approved_date   TEXT,
        disbursed_date  TEXT,
        approved_by     INTEGER,
        officer_id      INTEGER,
        total_paid      REAL NOT NULL DEFAULT 0,
        penalties       REAL NOT NULL DEFAULT 0,
        notes           TEXT,
        written_off_amount REAL NOT NULL DEFAULT 0,
        written_off_date   TEXT,
        written_off_reason TEXT,
        written_off_by     INTEGER,
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (member_id)   REFERENCES members(id),
        FOREIGN KEY (approved_by) REFERENCES users(id),
        FOREIGN KEY (officer_id)  REFERENCES users(id),
        FOREIGN KEY (written_off_by) REFERENCES users(id)
    )""")

    # ── Loan Schedule ────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS loan_schedule (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        loan_id      TEXT NOT NULL,
        installment  INTEGER NOT NULL,
        due_date     TEXT NOT NULL,
        principal    REAL NOT NULL,
        interest     REAL NOT NULL,
        repayment    REAL NOT NULL,
        balance      REAL NOT NULL,
        paid         INTEGER NOT NULL DEFAULT 0,
        paid_date    TEXT,
        penalty      REAL NOT NULL DEFAULT 0,
        FOREIGN KEY (loan_id) REFERENCES loans(id)
    )""")

    # ── Repayments ───────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS repayments (
        id          TEXT PRIMARY KEY,
        loan_id     TEXT NOT NULL,
        member_id   TEXT NOT NULL,
        amount      REAL NOT NULL,
        payment_date TEXT NOT NULL,
        method      TEXT NOT NULL DEFAULT 'cash',
        reference   TEXT,
        type        TEXT NOT NULL DEFAULT 'installment',
        recorded_by INTEGER,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (loan_id)      REFERENCES loans(id),
        FOREIGN KEY (member_id)    REFERENCES members(id),
        FOREIGN KEY (recorded_by)  REFERENCES users(id)
    )""")

    # ── Savings Accounts ─────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS savings_accounts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id   TEXT UNIQUE NOT NULL,
        balance     REAL NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (member_id) REFERENCES members(id)
    )""")

    # ── Savings Transactions ─────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS savings_transactions (
        id          TEXT PRIMARY KEY,
        member_id   TEXT NOT NULL,
        type        TEXT NOT NULL,
        amount      REAL NOT NULL,
        category    TEXT NOT NULL DEFAULT 'voluntary',
        txn_date    TEXT NOT NULL,
        reference   TEXT,
        balance_after REAL NOT NULL DEFAULT 0,
        recorded_by INTEGER,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (member_id)   REFERENCES members(id),
        FOREIGN KEY (recorded_by) REFERENCES users(id)
    )""")

    # ── Expense Accounts ─────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS expense_accounts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        code        TEXT UNIQUE,
        name        TEXT NOT NULL UNIQUE,
        description TEXT,
        active      INTEGER NOT NULL DEFAULT 1,
        created_by  INTEGER,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (created_by) REFERENCES users(id)
    )""")

    # ── Expense Transactions ─────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS expense_transactions (
        id           TEXT PRIMARY KEY,
        account_id   INTEGER NOT NULL,
        amount       REAL NOT NULL CHECK (amount > 0),
        expense_date TEXT NOT NULL,
        reference    TEXT,
        payee        TEXT,
        notes        TEXT,
        recorded_by  INTEGER,
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (account_id) REFERENCES expense_accounts(id),
        FOREIGN KEY (recorded_by) REFERENCES users(id)
    )""")

    # ── Notifications ────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        type        TEXT NOT NULL,
        message     TEXT NOT NULL,
        read        INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")



    # ── Dividends / Profit Sharing ─────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS dividend_runs (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        year         INTEGER NOT NULL,
        surplus      REAL NOT NULL,
        basis        TEXT NOT NULL DEFAULT 'savings_balance',
        total_basis  REAL NOT NULL DEFAULT 0,
        status       TEXT NOT NULL DEFAULT 'draft',
        created_by   INTEGER,
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (created_by) REFERENCES users(id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS dividend_allocations (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          INTEGER NOT NULL,
        member_id       TEXT NOT NULL,
        basis_amount    REAL NOT NULL DEFAULT 0,
        dividend_amount REAL NOT NULL DEFAULT 0,
        paid            INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (run_id)    REFERENCES dividend_runs(id),
        FOREIGN KEY (member_id) REFERENCES members(id)
    )""")

    # ── Audit Logs ───────────────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        user_name   TEXT,
        action      TEXT NOT NULL,
        module      TEXT NOT NULL,
        details     TEXT,
        ip_address  TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    _migrate_schema(c)
    conn.commit()
    if _env_bool("SEED_DEMO_DATA", False):
        _seed_data(conn)
    _ensure_bootstrap_admin(conn)
    _ensure_default_expense_accounts(conn)
    conn.close()
    print("Database initialized")


def _seed_data(conn):
    c = conn.cursor()

    # Check if already seeded
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] > 0:
        return

    print("Seeding database...")

    # Seed users
    users = [
        ("Admin User",    "admin",      "admin@sacco.co.ke",      hash_password("admin123"),   "admin"),
        ("Alice Njeri",   "officer",    "officer@sacco.co.ke",    hash_password("officer123"), "officer"),
        ("Bob Kipchoge",  "accountant", "accountant@sacco.co.ke", hash_password("acc123"),     "accountant"),
        ("Carol Mwangi",  "cashier",    "cashier@sacco.co.ke",    hash_password("cashier123"), "cashier"),
    ]
    c.executemany("INSERT INTO users (name,username,email,password,role) VALUES (?,?,?,?,?)", users)

    # Seed loan products
    products = [
        ("Business Loan",  10000, 500000, 3, 36, 18, "reducing", 5),
        ("Emergency Loan", 5000,  50000,  1, 6,  20, "flat",     5),
        ("Asset Finance",  50000, 1000000,6, 60, 15, "reducing", 3),
        ("School Fees",    5000,  100000, 1, 12, 18, "flat",     5),
    ]
    c.executemany(
        "INSERT INTO loan_products (name,min_amount,max_amount,min_term,max_term,annual_rate,method,penalty_rate) VALUES (?,?,?,?,?,?,?,?)",
        products,
    )

    # Seed members
    members = [
        ("M001","Grace Wanjiku",  "0712345678","grace@email.com",  "12345678","F","1988-05-12","Nairobi","active",  "2023-01-15",45000,1),
        ("M002","James Otieno",   "0723456789","james@email.com",  "23456789","M","1985-03-22","Kisumu", "active",  "2023-02-10",120000,1),
        ("M003","Faith Chebet",   "0734567890","faith@email.com",  "34567890","F","1992-07-18","Eldoret","active",  "2023-03-20",67500,2),
        ("M004","Peter Kamau",    "0745678901","peter@email.com",  "45678901","M","1979-11-30","Nakuru", "suspended","2023-04-05",23000,2),
        ("M005","Mary Achieng",   "0756789012","mary@email.com",   "56789012","F","1995-02-14","Mombasa","active",  "2023-05-12",89000,1),
        ("M006","David Mutua",    "0767890123","david@email.com",  "67890123","M","1990-08-25","Nairobi","active",  "2023-06-01",34000,2),
        ("M007","Ruth Wambua",    "0778901234","ruth@email.com",   "78901234","F","1987-12-05","Thika",  "active",  "2023-07-10",78000,1),
    ]
    c.executemany(
        "INSERT INTO members (id,name,phone,email,national_id,gender,dob,address,status,joined_date,savings,created_by,member_type) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [m + ("member",) for m in members],
    )

    settings = [
        ("sacco_name", "SACCOFinance Chama"),
        ("logo_text", "SF"),
        ("logo_url", ""),
        ("address", "Nairobi, Kenya"),
        ("phone", "0712345678"),
        ("account_opening_balance", "0"),
        ("default_penalty_rate", "5"),
        ("penalty_grace_days", "0"),
    ]
    c.executemany("INSERT OR REPLACE INTO app_settings (key,value) VALUES (?,?)", settings)

    # Seed expense accounts
    expense_accounts = [
        ("EXP-001", "Office Rent", "Monthly office rent"),
        ("EXP-002", "Utilities", "Water, electricity, internet"),
        ("EXP-003", "Transport", "Field visits and transport"),
        ("EXP-004", "Office Supplies", "Stationery and office consumables"),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO expense_accounts (code,name,description,active,created_by) VALUES (?,?,?,?,?)",
        [(code, name, desc, 1, 1) for code, name, desc in expense_accounts],
    )

    # Seed savings accounts
    c.executemany(
        "INSERT INTO savings_accounts (member_id,balance) VALUES (?,?)",
        [(m[0], m[10]) for m in members],
    )

    # Seed savings transactions
    stxns = [
        ("ST001","M001","deposit",  5000, "mandatory","2024-01-15","DEP001",50000,3),
        ("ST002","M002","deposit", 10000,"mandatory","2024-01-15","DEP002",130000,3),
        ("ST003","M001","deposit",  3000,"voluntary","2024-02-10","DEP003",53000,3),
        ("ST004","M003","deposit",  7500,"mandatory","2024-02-15","DEP004",75000,3),
        ("ST005","M005","deposit", 15000,"voluntary","2024-03-01","DEP005",104000,3),
        ("ST006","M001","withdrawal",8000,"voluntary","2024-03-20","WDR001",45000,4),
        ("ST007","M007","deposit", 12000,"mandatory","2024-04-01","DEP006",90000,3),
    ]
    c.executemany(
        "INSERT INTO savings_transactions (id,member_id,type,amount,category,txn_date,reference,balance_after,recorded_by) VALUES (?,?,?,?,?,?,?,?,?)",
        stxns,
    )

    # Build loan schedule helper
    def build_schedule(loan_id, principal, rate, months, method, start):
        rows = []
        balance = principal
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(start, "%Y-%m-%d")

        for i in range(1, months + 1):
            # Add ~30 days per installment
            due_dt = start_dt.replace(
                month=((start_dt.month - 1 + i) % 12) + 1,
                year=start_dt.year + ((start_dt.month - 1 + i) // 12),
            )
            due = due_dt.strftime("%Y-%m-%d")
            if method == "flat":
                interest = principal * rate / 100
                principal_part = principal / months
                repayment = principal_part + interest
                balance -= principal_part
            else:
                monthly_rate = rate / 100
                interest = principal * monthly_rate
                principal_part = principal / months
                repayment = principal_part + interest
                balance -= principal_part
            rows.append((loan_id, i, due, round(repayment - interest if method != "flat" else principal/months, 2),
                         round(interest, 2), round(repayment, 2), round(max(0, balance), 2)))
        return rows

    # Seed loans
    loans_data = [
        ("L001","M001",1,100000,18,12,"reducing","Business expansion","active",
         "2024-01-10","2024-01-15","2024-01-20",1,2,42000,0),
        ("L002","M002",3,250000,15,24,"reducing","Asset purchase","active",
         "2024-02-05","2024-02-10","2024-02-15",1,2,95000,2500),
        ("L003","M003",4,50000,20,6,"flat","School fees","completed",
         "2023-06-01","2023-06-05","2023-06-08",1,3,55000,0),
        ("L004","M005",2,75000,18,9,"flat","Medical expenses","overdue",
         "2023-12-01","2023-12-05","2023-12-10",1,2,18000,4500),
        ("L005","M004",2,30000,22,6,"flat","Emergency","pending",
         "2024-06-01",None,None,None,None,0,0),
        ("L006","M006",1,80000,18,12,"reducing","Shop renovation","active",
         "2024-03-01","2024-03-05","2024-03-10",1,2,24000,0),
        ("L007","M007",1,120000,18,18,"reducing","Business capital","active",
         "2024-04-01","2024-04-05","2024-04-10",1,2,18000,0),
    ]
    c.executemany(
        """INSERT INTO loans
           (id,member_id,product_id,amount,annual_rate,term_months,method,purpose,
            status,applied_date,approved_date,disbursed_date,approved_by,officer_id,
            total_paid,penalties)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        loans_data,
    )

    # Build schedules for disbursed loans
    for loan in loans_data:
        lid, mid, pid, amt, rate, months, method, purpose, status = loan[:9]
        disbursed = loan[11]
        if disbursed:
            rows = build_schedule(lid, amt, rate, months, method, disbursed)
            c.executemany(
                "INSERT INTO loan_schedule (loan_id,installment,due_date,principal,interest,repayment,balance) VALUES (?,?,?,?,?,?,?)",
                rows,
            )

    # Seed repayments
    repayments = [
        ("R001","L001","M001",9500,"2024-02-20","cash",     "CSH001","installment",4),
        ("R002","L001","M001",9500,"2024-03-20","mpesa",    "QK12345","installment",4),
        ("R003","L001","M001",9500,"2024-04-20","mpesa",    "QK12346","installment",4),
        ("R004","L001","M001",9500,"2024-05-20","bank",     "BNK001","installment",4),
        ("R005","L002","M002",12200,"2024-03-15","bank",    "BNK002","installment",4),
        ("R006","L002","M002",12200,"2024-04-15","mpesa",   "QK22222","installment",4),
        ("R007","L002","M002",12200,"2024-05-15","mpesa",   "QK33333","installment",4),
        ("R008","L004","M005",9000,"2024-01-10","mpesa",    "QK99001","installment",4),
        ("R009","L004","M005",9000,"2024-02-10","cash",     "CSH002","installment",4),
        ("R010","L006","M006",8000,"2024-04-10","mpesa",    "QK44444","installment",4),
        ("R011","L006","M006",8000,"2024-05-10","mpesa",    "QK55555","installment",4),
        ("R012","L007","M007",8100,"2024-05-10","cash",     "CSH003","installment",4),
    ]
    c.executemany(
        "INSERT INTO repayments (id,loan_id,member_id,amount,payment_date,method,reference,type,recorded_by) VALUES (?,?,?,?,?,?,?,?,?)",
        repayments,
    )

    # Seed notifications
    notes = [
        (1,"overdue","Loan L004 for Mary Achieng is 45 days overdue. Penalty of KES 4,500 applied.",0),
        (2,"approved","Loan L001 for Grace Wanjiku approved — KES 100,000 disbursed.",1),
        (2,"reminder","Repayment due in 3 days for James Otieno (L002) — KES 12,200.",0),
        (1,"disbursed","Loan L002 disbursed to James Otieno — KES 250,000.",1),
        (1,"new_application","New loan application from Peter Kamau — KES 30,000.",0),
    ]
    c.executemany(
        "INSERT INTO notifications (user_id,type,message,read) VALUES (?,?,?,?)", notes
    )

    # Seed audit logs
    audits = [
        (1,"Admin User","Approved loan L001","Loans","Loan approved and disbursed"),
        (2,"Alice Njeri","Registered member M005","Members","New member registration"),
        (4,"Carol Mwangi","Recorded repayment R003","Repayments","KES 9,500 received"),
        (1,"Admin User","Updated system settings","Settings","Interest rate updated"),
        (3,"Bob Kipchoge","Exported loans report","Reports","CSV export"),
    ]
    c.executemany(
        "INSERT INTO audit_logs (user_id,user_name,action,module,details) VALUES (?,?,?,?,?)", audits
    )

    conn.commit()
    print("Seed data inserted")


def _ensure_bootstrap_admin(conn):
    if not _env_bool("BOOTSTRAP_ADMIN", True):
        return

    c = conn.cursor()
    has_users = c.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    if has_users:
        return

    username = (
        os.environ.get("BOOTSTRAP_ADMIN_USERNAME")
        or os.environ.get("ADMIN_USERNAME")
        or ""
    ).strip().lower()
    password = (
        os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
        or os.environ.get("ADMIN_PASSWORD")
        or ""
    )
    email = (
        os.environ.get("BOOTSTRAP_ADMIN_EMAIL")
        or os.environ.get("ADMIN_EMAIL")
        or ""
    ).strip().lower()
    name = (
        os.environ.get("BOOTSTRAP_ADMIN_NAME")
        or os.environ.get("ADMIN_NAME")
        or "Administrator"
    ).strip() or "Administrator"
    role = (os.environ.get("BOOTSTRAP_ADMIN_ROLE") or "admin").strip().lower() or "admin"

    if not username or not password:
        print("Bootstrap admin skipped: set BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD.")
        return

    if not email:
        email = f"{username}@local.sacco"

    c.execute(
        "INSERT INTO users (name,username,email,password,role,permissions,active) VALUES (?,?,?,?,?,?,1)",
        (name, username, email, hash_password(password), role, "[]"),
    )

    conn.commit()
    print(f"Bootstrap admin created: {username}")


def _ensure_default_expense_accounts(conn):
    c = conn.cursor()
    has_accounts = c.execute("SELECT 1 FROM expense_accounts LIMIT 1").fetchone()
    if has_accounts:
        return

    defaults = [
        ("EXP-001", "Office Rent", "Monthly office rent"),
        ("EXP-002", "Utilities", "Water, electricity, internet"),
        ("EXP-003", "Transport", "Field visits and transport"),
        ("EXP-004", "Office Supplies", "Stationery and office consumables"),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO expense_accounts (code,name,description,active) VALUES (?,?,?,1)",
        defaults,
    )
    conn.commit()


def _migrate_schema(c):
    user_cols = {row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()}
    if "username" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN username TEXT")
        c.execute("UPDATE users SET username=lower(substr(email,1,instr(email,'@')-1)) WHERE username IS NULL")
    if "permissions" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN permissions TEXT NOT NULL DEFAULT '[]'")
        c.execute("UPDATE users SET permissions='[]' WHERE permissions IS NULL OR TRIM(permissions)=''")
    else:
        c.execute("UPDATE users SET permissions='[]' WHERE permissions IS NULL OR TRIM(permissions)=''")

    member_cols = {row[1] for row in c.execute("PRAGMA table_info(members)").fetchall()}
    if "member_type" not in member_cols:
        c.execute("ALTER TABLE members ADD COLUMN member_type TEXT NOT NULL DEFAULT 'member'")

    loan_cols = {row[1] for row in c.execute("PRAGMA table_info(loans)").fetchall()}
    if loan_cols and "penalties" not in loan_cols:
        c.execute("ALTER TABLE loans ADD COLUMN penalties REAL NOT NULL DEFAULT 0")
    loan_writeoff_columns = {
        "written_off_amount": "ALTER TABLE loans ADD COLUMN written_off_amount REAL NOT NULL DEFAULT 0",
        "written_off_date": "ALTER TABLE loans ADD COLUMN written_off_date TEXT",
        "written_off_reason": "ALTER TABLE loans ADD COLUMN written_off_reason TEXT",
        "written_off_by": "ALTER TABLE loans ADD COLUMN written_off_by INTEGER",
    }
    for column, ddl in loan_writeoff_columns.items():
        if loan_cols and column not in loan_cols:
            c.execute(ddl)

    schedule_cols = {row[1] for row in c.execute("PRAGMA table_info(loan_schedule)").fetchall()}
    if schedule_cols and "penalty" not in schedule_cols:
        c.execute("ALTER TABLE loan_schedule ADD COLUMN penalty REAL NOT NULL DEFAULT 0")

    product_cols = {row[1] for row in c.execute("PRAGMA table_info(loan_products)").fetchall()}
    if product_cols and "penalty_rate" not in product_cols:
        c.execute("ALTER TABLE loan_products ADD COLUMN penalty_rate REAL NOT NULL DEFAULT 5")

    try:
        guarantor_cols = {row[1] for row in c.execute("PRAGMA table_info(guarantors)").fetchall()}
        if guarantor_cols:
            if "loan_id" not in guarantor_cols:
                c.execute("ALTER TABLE guarantors ADD COLUMN loan_id TEXT")
            if "amount" not in guarantor_cols:
                c.execute("ALTER TABLE guarantors ADD COLUMN amount REAL NOT NULL DEFAULT 0")
            if "status" not in guarantor_cols:
                c.execute("ALTER TABLE guarantors ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
            if "notes" not in guarantor_cols:
                c.execute("ALTER TABLE guarantors ADD COLUMN notes TEXT")
            if "created_at" not in guarantor_cols:
                c.execute("ALTER TABLE guarantors ADD COLUMN created_at TEXT")
    except sqlite3.OperationalError:
        pass

    c.execute("""
    CREATE TABLE IF NOT EXISTS dividend_runs (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        year         INTEGER NOT NULL,
        surplus      REAL NOT NULL,
        basis        TEXT NOT NULL DEFAULT 'savings_balance',
        total_basis  REAL NOT NULL DEFAULT 0,
        status       TEXT NOT NULL DEFAULT 'draft',
        created_by   INTEGER,
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (created_by) REFERENCES users(id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS dividend_allocations (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          INTEGER NOT NULL,
        member_id       TEXT NOT NULL,
        basis_amount    REAL NOT NULL DEFAULT 0,
        dividend_amount REAL NOT NULL DEFAULT 0,
        paid            INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (run_id)    REFERENCES dividend_runs(id),
        FOREIGN KEY (member_id) REFERENCES members(id)
    )""")

    defaults = [
        ("sacco_name", "SACCOFinance Chama"),
        ("logo_text", "SF"),
        ("logo_url", ""),
        ("address", "Nairobi, Kenya"),
        ("phone", "0712345678"),
        ("account_opening_balance", "0"),
        ("default_penalty_rate", "5"),
        ("penalty_grace_days", "0"),
    ]
    c.executemany("INSERT OR IGNORE INTO app_settings (key,value) VALUES (?,?)", defaults)
