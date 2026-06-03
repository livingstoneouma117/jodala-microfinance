import importlib.util
import sys
from pathlib import Path

import pytest


def _fresh_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "sacco-test.db"))
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.setenv("BOOTSTRAP_ADMIN", "false")
    for name in list(sys.modules):
        if name == "app" or name == "database" or name == "auth" or name == "calculator" or name.startswith("services") or name.startswith("routes"):
            sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("jodala_app", Path(__file__).resolve().parents[1] / "app.py")
    app_module = importlib.util.module_from_spec(spec)
    sys.modules["jodala_app"] = app_module
    spec.loader.exec_module(app_module)
    app_module.init_db()
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    return _fresh_app(tmp_path, monkeypatch)


def _login(client, username="admin", password="admin123"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    return payload["data"]["token"]


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_login_success_and_failure(client):
    token = _login(client)
    assert token

    failed = client.post("/api/auth/login", json={"username": "admin", "password": "wrong-password"})
    assert failed.status_code == 401
    assert failed.get_json()["success"] is False


def test_report_export_requires_auth_and_returns_csv(client):
    unauthorized = client.get("/api/reports/export/members?format=csv")
    assert unauthorized.status_code == 401

    token = _login(client)
    response = client.get("/api/reports/export/members?format=csv", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert b"ID,Name" in response.data


def test_overdue_penalties_are_applied_to_outstanding(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/loans?status=all&limit=100", headers=headers)
    assert response.status_code == 200
    loans = response.get_json()["data"]["loans"]
    penalized = [loan for loan in loans if float(loan.get("penalties") or 0) > 0]
    assert penalized

    loan = penalized[0]
    assert float(loan["outstanding"]) >= float(loan["penalties"])

    detail = client.get(f"/api/loans/{loan['id']}", headers=headers)
    assert detail.status_code == 200
    payload = detail.get_json()["data"]
    assert float(payload["summary"]["penalties"]) == float(loan["penalties"])
    assert any(float(row.get("penalty") or 0) > 0 for row in payload["schedule"])


def test_admin_can_write_off_overdue_loan(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    before = client.get("/api/loans/L004", headers=headers)
    assert before.status_code == 200
    before_payload = before.get_json()["data"]
    before_outstanding = float(before_payload["summary"]["outstanding"] or 0)
    assert before_outstanding > 0

    written_off = client.post(
        "/api/loans/L004/write-off",
        json={"reason": "Unrecoverable test balance", "write_off_date": "2026-06-03"},
        headers=headers,
    )
    assert written_off.status_code == 200
    assert written_off.get_json()["data"]["written_off_amount"] == pytest.approx(before_outstanding)

    detail = client.get("/api/loans/L004", headers=headers)
    assert detail.status_code == 200
    payload = detail.get_json()["data"]
    assert payload["loan"]["status"] == "written_off"
    assert float(payload["loan"]["written_off_amount"] or 0) == pytest.approx(before_outstanding)
    assert float(payload["loan"]["penalties"] or 0) == pytest.approx(0)
    assert float(payload["summary"]["outstanding"] or 0) == pytest.approx(0)

    listing = client.get("/api/loans?q=L004&status=all", headers=headers)
    assert listing.status_code == 200
    loan = listing.get_json()["data"]["loans"][0]
    assert loan["status"] == "written_off"
    assert float(loan["outstanding"] or 0) == pytest.approx(0)


def test_admin_can_assign_roles_and_non_admin_cannot(client):
    admin_token = _login(client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    users_response = client.get("/api/users", headers=admin_headers)
    assert users_response.status_code == 200
    users = users_response.get_json()["data"]
    target = next(user for user in users if user["username"] == "cashier")

    update = client.patch(
        f"/api/users/{target['id']}/role",
        json={"role": "officer"},
        headers=admin_headers,
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["role"] == "officer"

    officer_token = _login(client, "officer", "officer123")
    denied = client.patch(
        f"/api/users/{target['id']}/role",
        json={"role": "cashier"},
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert denied.status_code == 403


def test_admin_granted_permission_allows_officer_to_do_admin_only_action(client):
    admin_token = _login(client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    users = client.get("/api/users", headers=admin_headers).get_json()["data"]
    officer = next(user for user in users if user["username"] == "officer")

    denied_token = _login(client, "cashier", "cashier123")
    denied = client.post(
        "/api/loan-products",
        json={
            "name": "Cashier Blocked Product",
            "min_amount": 1000,
            "max_amount": 5000,
            "min_term": 1,
            "max_term": 3,
            "annual_rate": 0,
            "method": "flat",
            "penalty_rate": 0,
            "active": True,
        },
        headers={"Authorization": f"Bearer {denied_token}"},
    )
    assert denied.status_code == 403

    grant = client.put(
        f"/api/users/{officer['id']}",
        json={
            "name": officer["name"],
            "username": officer["username"],
            "email": officer["email"],
            "role": officer["role"],
            "active": True,
            "permissions": ["loan-products.create"],
        },
        headers=admin_headers,
    )
    assert grant.status_code == 200

    officer_token = _login(client, "officer", "officer123")
    created = client.post(
        "/api/loan-products",
        json={
            "name": "Officer Managed Product",
            "min_amount": 1000,
            "max_amount": 5000,
            "min_term": 1,
            "max_term": 3,
            "annual_rate": 0,
            "method": "flat",
            "penalty_rate": 0,
            "active": True,
        },
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert created.status_code == 201
    assert created.get_json()["data"]["name"] == "Officer Managed Product"


def test_expense_edit_and_delete_updates_main_account_balance(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    initial = client.get("/api/dashboard", headers=headers)
    assert initial.status_code == 200
    starting_balance = float(initial.get_json()["data"]["stats"]["account_current_balance"] or 0)

    funded = client.post("/api/settings/account/add", json={"amount": 1000}, headers=headers)
    assert funded.status_code == 200

    account = client.post(
        "/api/expenses/accounts",
        json={"name": "Pytest Office Costs", "code": "TST-OFF", "description": "Test expenses"},
        headers=headers,
    )
    assert account.status_code == 201
    account_id = account.get_json()["data"]["id"]

    created = client.post(
        "/api/expenses/transactions",
        json={"account_id": account_id, "amount": 100, "expense_date": "2026-05-30", "payee": "Printer Shop"},
        headers=headers,
    )
    assert created.status_code == 201
    expense_id = created.get_json()["data"]["id"]

    after_create = client.get("/api/dashboard", headers=headers)
    assert float(after_create.get_json()["data"]["stats"]["account_current_balance"] or 0) == pytest.approx(starting_balance + 900)

    updated = client.put(
        f"/api/expenses/transactions/{expense_id}",
        json={"account_id": account_id, "amount": 250, "expense_date": "2026-05-30", "payee": "Printer Shop", "notes": "Adjusted"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert float(updated.get_json()["data"]["amount"] or 0) == pytest.approx(250)

    after_update = client.get("/api/dashboard", headers=headers)
    assert float(after_update.get_json()["data"]["stats"]["account_current_balance"] or 0) == pytest.approx(starting_balance + 750)

    deleted = client.delete(f"/api/expenses/transactions/{expense_id}", headers=headers)
    assert deleted.status_code == 200

    after_delete = client.get("/api/dashboard", headers=headers)
    assert float(after_delete.get_json()["data"]["stats"]["account_current_balance"] or 0) == pytest.approx(starting_balance + 1000)
