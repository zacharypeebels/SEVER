import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_disabled_mode_allows_requests(monkeypatch):
    monkeypatch.delenv("AUTH_MODE", raising=False)
    r = client.get("/subscriptions")
    assert r.status_code == 200


def test_cognito_mode_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "cognito")
    r = client.get("/subscriptions")
    assert r.status_code == 401
    assert r.json()["detail"] == "missing bearer token"


def test_cognito_mode_rejects_malformed_header(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "cognito")
    r = client.get("/subscriptions", headers={"Authorization": "Basic abc123"})
    assert r.status_code == 401


def test_health_never_requires_auth(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "cognito")
    r = client.get("/health")
    assert r.status_code == 200
