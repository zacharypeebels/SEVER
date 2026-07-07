from store import SubscriptionStore

SEED = [
    {"id": 1, "name": "Netflix", "category": "Streaming", "price": 15.49, "cadence": "mo", "lastUsed": 2},
    {"id": 2, "name": "Calm", "category": "Wellness", "price": 69.99, "cadence": "yr", "lastUsed": 122},
]


def _store(tmp_path):
    return SubscriptionStore(path=str(tmp_path / "test.db"))


def test_seed_only_once(tmp_path):
    s = _store(tmp_path)
    assert s.seed_user("u1", SEED) is True
    assert s.seed_user("u1", SEED) is False
    assert len(s.list("u1")) == 2


def test_data_survives_reopen(tmp_path):
    path = str(tmp_path / "test.db")
    s1 = SubscriptionStore(path=path)
    s1.seed_user("u1", SEED)
    sub = s1.get("u1", 1)
    sub["status"] = "canceled"
    s1.save("u1", sub)

    s2 = SubscriptionStore(path=path)  # simulates a service restart
    assert s2.get("u1", 1)["status"] == "canceled"


def test_users_are_isolated(tmp_path):
    s = _store(tmp_path)
    s.seed_user("u1", SEED)
    s.seed_user("u2", SEED)
    sub = s.get("u1", 1)
    sub["status"] = "paused"
    s.save("u1", sub)
    assert s.get("u2", 1)["status"] == "active"
    s.upsert_by_name("u2", {"merchant": "New Gym", "category": "Health", "price": 25.0, "cadence": "mo", "lastUsed": 0})
    assert len(s.list("u2")) == 3
    assert len(s.list("u1")) == 2


def test_upsert_updates_by_merchant_name(tmp_path):
    s = _store(tmp_path)
    s.seed_user("u1", SEED)
    assert s.upsert_by_name("u1", {"merchant": "Netflix", "category": "Streaming", "price": 17.99, "cadence": "mo", "lastUsed": 1}) == "updated"
    assert s.get("u1", 1)["price"] == 17.99
    assert s.upsert_by_name("u1", {"merchant": "Peloton", "category": "Health", "price": 39.0, "cadence": "mo", "lastUsed": 4}) == "created"
    assert len(s.list("u1")) == 3
