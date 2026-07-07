from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def setup_function():
    client.post("/reset")


def test_export_requires_auth(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "cognito")
    assert client.get("/account/export").status_code == 401
    monkeypatch.delenv("AUTH_MODE")


def test_delete_requires_auth(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "cognito")
    assert client.delete("/account").status_code == 401
    monkeypatch.delenv("AUTH_MODE")


def test_export_returns_full_ledger():
    client.post("/subscriptions/1/action", json={"mode": "haggle"})
    r = client.get("/account/export")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["id"] == "dev-user"
    assert len(body["subscriptions"]) == 10
    netflix = next(s for s in body["subscriptions"] if s["name"] == "Netflix")
    assert netflix["status"] == "negotiated"
    assert "exportedAt" in body


def test_delete_account_wipes_data():
    r = client.delete("/account")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "deleted"
    assert body["rowsDeleted"] == 10
    assert body["identityDeleted"] is False  # dev mode: no Cognito call
    # A fresh GET re-seeds demo data for the dev user, proving the wipe happened
    r2 = client.delete("/account")
    assert r2.json()["rowsDeleted"] == 0
