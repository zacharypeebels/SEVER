"""Store contract tests against real Postgres.

Skipped unless TEST_DATABASE_URL is set — CI provides a Postgres service
container; locally these are skipped.
"""

import os
import uuid

import pytest

TEST_DSN = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="TEST_DATABASE_URL not set")

SEED = [
    {"id": 1, "name": "Netflix", "category": "Streaming", "price": 15.49, "cadence": "mo", "lastUsed": 2},
    {"id": 2, "name": "Calm", "category": "Wellness", "price": 69.99, "cadence": "yr", "lastUsed": 122},
]


@pytest.fixture
def store():
    from pg_store import PostgresSubscriptionStore

    return PostgresSubscriptionStore(dsn=TEST_DSN)


@pytest.fixture
def user():
    return f"test-{uuid.uuid4()}"


def test_seed_only_once(store, user):
    assert store.seed_user(user, SEED) is True
    assert store.seed_user(user, SEED) is False
    assert len(store.list(user)) == 2


def test_roundtrip_preserves_types(store, user):
    store.seed_user(user, SEED)
    sub = store.get(user, 1)
    assert sub["price"] == 15.49
    assert isinstance(sub["price"], float)
    assert sub["newPrice"] is None


def test_save_and_get(store, user):
    store.seed_user(user, SEED)
    sub = store.get(user, 1)
    sub["status"] = "negotiated"
    sub["newPrice"] = 9.6
    store.save(user, sub)
    again = store.get(user, 1)
    assert again["status"] == "negotiated"
    assert again["newPrice"] == 9.6


def test_users_are_isolated(store, user):
    other = f"other-{uuid.uuid4()}"
    store.seed_user(user, SEED)
    store.seed_user(other, SEED)
    sub = store.get(user, 1)
    sub["status"] = "canceled"
    store.save(user, sub)
    assert store.get(other, 1)["status"] == "active"


def test_upsert_by_name(store, user):
    store.seed_user(user, SEED)
    assert store.upsert_by_name(user, {"merchant": "Netflix", "category": "Streaming", "price": 17.99, "cadence": "mo", "lastUsed": 1}) == "updated"
    assert store.get(user, 1)["price"] == 17.99
    assert store.upsert_by_name(user, {"merchant": "Peloton", "category": "Health", "price": 39.0, "cadence": "mo", "lastUsed": 4}) == "created"
    assert len(store.list(user)) == 3


def test_reset_restores_seed(store, user):
    store.seed_user(user, SEED)
    store.upsert_by_name(user, {"merchant": "Extra", "category": "X", "price": 1.0, "cadence": "mo", "lastUsed": 0})
    store.reset(user, SEED)
    assert {s["name"] for s in store.list(user)} == {"Netflix", "Calm"}
