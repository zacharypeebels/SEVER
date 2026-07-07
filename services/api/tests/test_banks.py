"""Bank connection endpoints — Plaid calls are monkeypatched."""

import pytest
from fastapi.testclient import TestClient

import plaid_integration
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    client.post("/reset")


@pytest.fixture
def fake_plaid(monkeypatch):
    monkeypatch.setattr(plaid_integration, "configured", lambda: True)
    monkeypatch.setattr(plaid_integration, "create_link_token", lambda user_id: f"link-{user_id}")
    monkeypatch.setattr(
        plaid_integration, "exchange_public_token", lambda pt: (f"access-{pt}", f"item-{pt}")
    )
    monkeypatch.setattr(
        plaid_integration,
        "fetch_recurring",
        lambda token: [
            {"merchant": "Netflix", "category": "Streaming", "price": 17.99, "cadence": "mo", "lastUsed": 1},
            {"merchant": "New Gym", "category": "Health", "price": 30.0, "cadence": "mo", "lastUsed": 12},
        ],
    )
    removed = []
    monkeypatch.setattr(plaid_integration, "remove_item", removed.append)
    return removed


def test_endpoints_fail_closed_without_plaid():
    assert client.post("/banks/link-token").status_code == 503
    assert client.post("/banks/exchange", json={"publicToken": "x"}).status_code == 503
    assert client.post("/banks/sync").status_code == 503


def test_link_token(fake_plaid):
    r = client.post("/banks/link-token")
    assert r.status_code == 200
    assert r.json()["linkToken"] == "link-dev-user"


def test_multi_bank_lifecycle(fake_plaid):
    # Link two banks
    c1 = client.post("/banks/exchange", json={"publicToken": "pt1", "institution": "Chase"}).json()
    c2 = client.post("/banks/exchange", json={"publicToken": "pt2", "institution": "Amex"}).json()
    banks = client.get("/banks").json()
    assert {b["institution"] for b in banks} == {"Chase", "Amex"}
    assert all("accessToken" not in b and "accessTokenEnc" not in b for b in banks)

    # Sync merges recurring charges from all connections, deduped by merchant
    r = client.post("/banks/sync").json()
    assert r["connections"] == 2
    names = [s["name"] for s in client.get("/subscriptions").json()]
    assert "New Gym" in names
    assert names.count("Netflix") == 1  # upsert, not duplicate

    # Disconnect one bank; the other remains
    d = client.delete(f"/banks/{c1['connectionId']}")
    assert d.status_code == 200
    assert fake_plaid == ["access-pt1"]  # Plaid revocation called with the right token
    remaining = client.get("/banks").json()
    assert [b["institution"] for b in remaining] == ["Amex"]


def test_disconnect_unknown_404(fake_plaid):
    assert client.delete("/banks/nope").status_code == 404


def test_delete_account_wipes_banks(fake_plaid):
    client.post("/banks/exchange", json={"publicToken": "pt1", "institution": "Chase"})
    client.delete("/account")
    assert client.get("/banks").json() == []


def test_token_encryption_roundtrip():
    import crypto

    stored = crypto.encrypt_token("access-sandbox-secret")
    assert "access-sandbox-secret" not in stored.split(":", 1)[0]
    assert crypto.decrypt_token(stored) == "access-sandbox-secret"
