"""
tests/test_sectors_allocations.py

Tests for GET /sectors and GET /allocations.
"""


# ── /sectors ────────────────────────────────────────────────────────────────

def test_sectors_returns_200(client):
    res = client.get("/sectors")
    assert res.status_code == 200


def test_sectors_has_sectors_key(client):
    body = client.get("/sectors").json()
    assert "sectors" in body
    assert isinstance(body["sectors"], list)
    assert len(body["sectors"]) > 0


def test_sectors_item_shape(client):
    sectors = client.get("/sectors").json()["sectors"]
    for s in sectors:
        assert "id" in s
        assert "name" in s
        assert "mean_increment_pct" in s
        assert "source" in s


def test_sectors_increment_pct_positive(client):
    sectors = client.get("/sectors").json()["sectors"]
    for s in sectors:
        assert s["mean_increment_pct"] > 0, (
            f"Sector {s['id']} has non-positive increment: {s['mean_increment_pct']}"
        )


def test_sectors_contains_it_software(client):
    """it_software is used as the default in tests — must exist."""
    ids = [s["id"] for s in client.get("/sectors").json()["sectors"]]
    assert "it_software" in ids


# ── /allocations ─────────────────────────────────────────────────────────────

def test_allocations_returns_200(client):
    res = client.get("/allocations")
    assert res.status_code == 200


def test_allocations_has_allocations_key(client):
    body = client.get("/allocations").json()
    assert "allocations" in body
    assert isinstance(body["allocations"], list)
    assert len(body["allocations"]) > 0


def test_allocations_item_shape(client):
    allocs = client.get("/allocations").json()["allocations"]
    for a in allocs:
        assert "id" in a
        assert "equity" in a
        assert "gold" in a
        assert "fd" in a


def test_allocations_weights_sum_to_one(client):
    allocs = client.get("/allocations").json()["allocations"]
    for a in allocs:
        total = round(a["equity"] + a["gold"] + a["fd"], 6)
        assert abs(total - 1.0) < 1e-4, (
            f"Allocation '{a['id']}' weights sum to {total}, expected 1.0"
        )


def test_allocations_weights_in_range(client):
    allocs = client.get("/allocations").json()["allocations"]
    for a in allocs:
        for key in ("equity", "gold", "fd"):
            assert 0.0 <= a[key] <= 1.0, (
                f"Allocation '{a['id']}' has {key}={a[key]} outside [0,1]"
            )


def test_allocations_contains_balanced(client):
    """balanced is used as default preset — must exist."""
    ids = [a["id"] for a in client.get("/allocations").json()["allocations"]]
    assert "balanced" in ids


def test_allocations_has_categories(client):
    body = client.get("/allocations").json()
    assert "categories" in body
    assert isinstance(body["categories"], list)
    assert len(body["categories"]) > 0
