import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
TOKEN_HEADER = {"X-Internal-Token": "test-token"}


@pytest.fixture(autouse=True)
def _internal_token(monkeypatch):
    monkeypatch.setenv("SEVER_INTERNAL_TOKEN", "test-token")
    client.post("/reset")


def test_ingest_creates_new_subscription():
    r = client.post("/internal/ingest", json=[
        {"merchant": "New Gym", "category": "Health", "price": 25.0, "cadence": "mo", "lastUsed": 10}
    ], headers=TOKEN_HEADER)
    assert r.status_code == 200
    assert r.json() == {"created": 1, "updated": 0}
    names = [s["name"] for s in client.get("/subscriptions").json()]
    assert "New Gym" in names


def test_ingest_upserts_existing_by_name():
    r = client.post("/internal/ingest", json=[
        {"merchant": "Netflix", "category": "Streaming", "price": 17.99, "cadence": "mo", "lastUsed": 3}
    ], headers=TOKEN_HEADER)
    assert r.json() == {"created": 0, "updated": 1}
    netflix = next(s for s in client.get("/subscriptions").json() if s["name"] == "Netflix")
    assert netflix["price"] == 17.99
    assert netflix["lastUsed"] == 3


def test_ingest_rejects_missing_or_wrong_token():
    payload = [{"merchant": "X", "price": 1.0, "cadence": "mo"}]
    assert client.post("/internal/ingest", json=payload).status_code == 403
    assert client.post("/internal/ingest", json=payload, headers={"X-Internal-Token": "wrong"}).status_code == 403


def test_ingest_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SEVER_INTERNAL_TOKEN", raising=False)
    payload = [{"merchant": "X", "price": 1.0, "cadence": "mo"}]
    assert client.post("/internal/ingest", json=payload, headers=TOKEN_HEADER).status_code == 503
