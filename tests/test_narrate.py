"""
tests/test_narrate.py

Tests for POST /narrate — AI result narrator endpoint.

The narrator is designed to fail silently (returns empty string on error),
so tests focus on:
  - Shape of response
  - Graceful degradation without API key
  - Input validation
  - Mocked output when key is present
"""

import os
import pytest
from unittest.mock import patch


VALID_NARRATE_PAYLOAD = {
    "current_age": 28,
    "horizon_years": 20,
    "monthly_income": 80000,
    "top_habits": [
        {"name": "Weekend dining", "monthly_cost_inr": 6500},
        {"name": "Daily coffee",   "monthly_cost_inr": 4566},
    ],
    "opportunity_cost_p50_inr": 2_800_000,
    "combined_portfolio_p50_inr": 18_000_000,
    "top_sensitivity_variable": "horizon (+5yr)",
    "top_sensitivity_impact_pct": 52.3,
}


def test_narrate_returns_200(client):
    """Narrate always returns 200 — even on failure (graceful degradation)."""
    res = client.post("/narrate", json=VALID_NARRATE_PAYLOAD)
    assert res.status_code == 200


def test_narrate_response_has_insight_key(client):
    res = client.post("/narrate", json=VALID_NARRATE_PAYLOAD)
    assert "insight" in res.json()


def test_narrate_no_key_returns_empty_string(client):
    """Without GROQ_API_KEY, insight should be empty string — not an error."""
    original = os.environ.pop("GROQ_API_KEY", None)
    try:
        res = client.post("/narrate", json=VALID_NARRATE_PAYLOAD)
        assert res.status_code == 200
        assert res.json()["insight"] == ""
    finally:
        if original:
            os.environ["GROQ_API_KEY"] = original


def test_narrate_mocked_returns_insight_string(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    fake_insight = "Your weekend dining habit could grow to ₹28L — enough for a car."
    with patch("api.main._call_narrator", return_value=fake_insight):
        res = client.post("/narrate", json=VALID_NARRATE_PAYLOAD)
        assert res.json()["insight"] == fake_insight


def test_narrate_exception_in_narrator_returns_empty(client, monkeypatch):
    """If narrator throws any exception, insight should be empty — never a 500."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    with patch("api.main._call_narrator", side_effect=RuntimeError("network error")):
        res = client.post("/narrate", json=VALID_NARRATE_PAYLOAD)
        assert res.status_code == 200
        assert res.json()["insight"] == ""


def test_narrate_missing_required_field_returns_422(client):
    import copy
    payload = copy.deepcopy(VALID_NARRATE_PAYLOAD)
    del payload["current_age"]
    res = client.post("/narrate", json=payload)
    assert res.status_code == 422


def test_narrate_empty_top_habits_accepted(client, monkeypatch):
    """Narrator should handle empty habits list without crashing."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    import copy
    payload = copy.deepcopy(VALID_NARRATE_PAYLOAD)
    payload["top_habits"] = []
    with patch("api.main._call_narrator", return_value="Some insight."):
        res = client.post("/narrate", json=payload)
        assert res.status_code == 200
