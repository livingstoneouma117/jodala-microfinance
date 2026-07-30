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
