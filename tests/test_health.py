"""
tests/test_health.py

Tests for GET /health — liveness check.
"""


def test_health_returns_200(client):
    res = client.get("/health")
    assert res.status_code == 200


def test_health_response_shape(client):
    res = client.get("/health")
    body = res.json()
    assert body["status"] == "ok"
    assert "engine" in body


def test_health_content_type(client):
    res = client.get("/health")
    assert "application/json" in res.headers["content-type"]
