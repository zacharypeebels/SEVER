from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_health():
    assert client.get("/health").status_code == 200


def test_parse_endpoint_mixes_known_and_unknown():
    r = client.post("/parse", json={"descriptors": ["NETFLIX.COM 866-579-7172 CA", "CORNER DELI NYC"]})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["merchant"] == "Netflix"
    assert results[0]["category"] == "Streaming"
    assert results[1]["merchant"] is None
    assert results[1]["raw"] == "CORNER DELI NYC"
