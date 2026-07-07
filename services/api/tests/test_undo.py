from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def setup_function():
    client.post("/reset")


def test_undo_after_cancel_restores_and_allows_new_actions():
    client.post("/subscriptions/1/action", json={"mode": "cancel"})
    r = client.post("/subscriptions/1/undo")
    assert r.status_code == 200
    body = r.json()
    assert body["subscription"]["status"] == "active"
    assert body["reclaimedMonthly"] == -15.49

    # The original bug: actions after undo must work again
    r2 = client.post("/subscriptions/1/action", json={"mode": "pause"})
    assert r2.status_code == 200
    assert r2.json()["subscription"]["status"] == "paused"


def test_undo_after_haggle_clears_new_price():
    client.post("/subscriptions/4/action", json={"mode": "haggle"})
    r = client.post("/subscriptions/4/undo")
    assert r.status_code == 200
    body = r.json()
    assert body["subscription"]["newPrice"] is None
    assert body["reclaimedMonthly"] == -22.8


def test_undo_on_active_subscription_conflicts():
    assert client.post("/subscriptions/2/undo").status_code == 409


def test_undo_unknown_subscription_404():
    assert client.post("/subscriptions/999/undo").status_code == 404
