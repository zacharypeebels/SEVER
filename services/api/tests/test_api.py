from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def setup_function():
    client.post("/reset")


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_subscriptions():
    r = client.get("/subscriptions")
    assert r.status_code == 200
    subs = r.json()
    assert len(subs) == 10
    assert subs[0]["name"] == "Netflix"


def test_cancel_reclaims_monthly():
    r = client.post("/subscriptions/3/action", json={"mode": "cancel"})
    assert r.status_code == 200
    body = r.json()
    assert body["subscription"]["status"] == "canceled"
    assert body["reclaimedMonthly"] == 44.0


def test_haggle_sets_new_price():
    r = client.post("/subscriptions/4/action", json={"mode": "haggle"})
    assert r.status_code == 200
    body = r.json()
    assert body["subscription"]["status"] == "negotiated"
    assert body["subscription"]["newPrice"] == 37.19


def test_cancel_twice_conflicts():
    client.post("/subscriptions/1/action", json={"mode": "cancel"})
    r = client.post("/subscriptions/1/action", json={"mode": "cancel"})
    assert r.status_code == 409


def test_unknown_subscription_404():
    r = client.post("/subscriptions/999/action", json={"mode": "pause"})
    assert r.status_code == 404
