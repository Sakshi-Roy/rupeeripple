"""
tests/test_parse_habits.py

Tests for POST /parse-habits — AI habit parser endpoint.

Strategy:
  - Validation tests (no API key needed): empty text, text too long, missing field
  - No-key tests: verify the endpoint returns 503 when GROQ_API_KEY is absent
  - Mocked AI tests: patch _call_gemini to return a canned response, verify
    the cleaning/validation logic works correctly without hitting Groq
"""

import os
import copy
import pytest
from unittest.mock import patch


VALID_CATEGORY_KEYS = [
    "food_restaurant", "food_delivery", "coffee_chai", "tobacco", "alcohol",
    "fuel", "transport_app", "commute", "travel", "entertainment", "cloud_saas",
    "gym_wellness", "shopping", "wifi_internet", "general",
]

VALID_FREQUENCIES = {"daily", "weekly", "monthly"}


# ── Input validation (no API call needed) ─────────────────────────────────────

def test_parse_habits_empty_text_returns_422(client):
    res = client.post("/parse-habits", json={"text": ""})
    assert res.status_code == 422


def test_parse_habits_whitespace_only_returns_422(client):
    res = client.post("/parse-habits", json={"text": "   "})
    assert res.status_code == 422


def test_parse_habits_text_too_long_returns_422(client):
    res = client.post("/parse-habits", json={"text": "x" * 2001})
    assert res.status_code == 422


def test_parse_habits_missing_text_field_returns_422(client):
    res = client.post("/parse-habits", json={})
    assert res.status_code == 422


def test_parse_habits_exactly_2000_chars_is_valid_length(client):
    """2000 characters should not fail the length check (boundary condition)."""
    with patch("api.main._call_gemini", return_value={"habits": [], "unparsed": ""}):
        res = client.post("/parse-habits", json={"text": "x" * 2000})
        # Should not be 422 (length error) — may be 200 or something else
        assert res.status_code != 422


# ── No API key → 503 ─────────────────────────────────────────────────────────

def test_parse_habits_no_api_key_returns_503(client):
    """Without GROQ_API_KEY, the endpoint should return 503."""
    original = os.environ.pop("GROQ_API_KEY", None)
    try:
        res = client.post("/parse-habits", json={"text": "I drink coffee daily for 50 rupees"})
        assert res.status_code == 503
        assert "GROQ_API_KEY" in res.json()["detail"]
    finally:
        if original:
            os.environ["GROQ_API_KEY"] = original


# ── Mocked AI — response cleaning and validation logic ───────────────────────

MOCK_GOOD_RESPONSE = {
    "habits": [
        {"name": "Morning coffee", "cost_inr": 50,  "frequency": "daily",   "categoryKey": "coffee_chai"},
        {"name": "Swiggy dinner",  "cost_inr": 400, "frequency": "weekly",  "categoryKey": "food_delivery"},
        {"name": "Netflix",        "cost_inr": 799, "frequency": "monthly", "categoryKey": "entertainment"},
    ],
    "unparsed": "",
}


@pytest.fixture
def mocked_ai(monkeypatch):
    """Patch _call_gemini to return a canned good response."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-testing")
    with patch("api.main._call_gemini", return_value=copy.deepcopy(MOCK_GOOD_RESPONSE)):
        yield


def test_parse_habits_returns_200_with_mock(client, mocked_ai):
    res = client.post("/parse-habits", json={"text": "I drink coffee every day"})
    assert res.status_code == 200


def test_parse_habits_response_has_habits_key(client, mocked_ai):
    res = client.post("/parse-habits", json={"text": "I drink coffee every day"})
    body = res.json()
    assert "habits" in body
    assert isinstance(body["habits"], list)


def test_parse_habits_response_has_unparsed_key(client, mocked_ai):
    res = client.post("/parse-habits", json={"text": "I drink coffee every day"})
    body = res.json()
    assert "unparsed" in body


def test_parse_habits_correct_habit_count(client, mocked_ai):
    res = client.post("/parse-habits", json={"text": "coffee, swiggy, netflix"})
    body = res.json()
    assert len(body["habits"]) == 3


def test_parse_habits_habit_item_shape(client, mocked_ai):
    res = client.post("/parse-habits", json={"text": "coffee, swiggy, netflix"})
    habits = res.json()["habits"]
    for h in habits:
        assert "name" in h
        assert "cost_inr" in h
        assert "frequency" in h
        assert "categoryKey" in h


def test_parse_habits_frequency_valid(client, mocked_ai):
    res = client.post("/parse-habits", json={"text": "coffee, swiggy, netflix"})
    habits = res.json()["habits"]
    for h in habits:
        assert h["frequency"] in VALID_FREQUENCIES, (
            f"Invalid frequency: {h['frequency']}"
        )


def test_parse_habits_category_key_valid(client, mocked_ai):
    res = client.post("/parse-habits", json={"text": "coffee, swiggy, netflix"})
    habits = res.json()["habits"]
    for h in habits:
        assert h["categoryKey"] in VALID_CATEGORY_KEYS, (
            f"Invalid categoryKey: {h['categoryKey']}"
        )


def test_parse_habits_cost_positive(client, mocked_ai):
    res = client.post("/parse-habits", json={"text": "coffee, swiggy, netflix"})
    habits = res.json()["habits"]
    for h in habits:
        assert h["cost_inr"] > 0


# ── Mocked AI — bad AI output is cleaned gracefully ──────────────────────────

def test_parse_habits_filters_zero_cost(client, monkeypatch):
    """Habits with cost_inr = 0 should be dropped."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    bad_response = {
        "habits": [
            {"name": "Free thing", "cost_inr": 0,   "frequency": "daily",   "categoryKey": "general"},
            {"name": "Real habit", "cost_inr": 100, "frequency": "monthly", "categoryKey": "general"},
        ],
        "unparsed": "",
    }
    with patch("api.main._call_gemini", return_value=bad_response):
        res = client.post("/parse-habits", json={"text": "stuff"})
        habits = res.json()["habits"]
        assert len(habits) == 1
        assert habits[0]["name"] == "Real habit"


def test_parse_habits_unknown_category_key_falls_back_to_general(client, monkeypatch):
    """Unknown categoryKey should be replaced with 'general'."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    bad_response = {
        "habits": [
            {"name": "Mystery", "cost_inr": 200, "frequency": "monthly", "categoryKey": "does_not_exist"},
        ],
        "unparsed": "",
    }
    with patch("api.main._call_gemini", return_value=bad_response):
        res = client.post("/parse-habits", json={"text": "stuff"})
        habits = res.json()["habits"]
        assert len(habits) == 1
        assert habits[0]["categoryKey"] == "general"


def test_parse_habits_invalid_frequency_falls_back_to_monthly(client, monkeypatch):
    """Invalid frequency should be replaced with 'monthly'."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    bad_response = {
        "habits": [
            {"name": "Odd habit", "cost_inr": 50, "frequency": "hourly", "categoryKey": "general"},
        ],
        "unparsed": "",
    }
    with patch("api.main._call_gemini", return_value=bad_response):
        res = client.post("/parse-habits", json={"text": "stuff"})
        habits = res.json()["habits"]
        assert habits[0]["frequency"] == "monthly"


def test_parse_habits_unparsed_text_returned(client, monkeypatch):
    """unparsed field should be passed through from the AI response."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    response_with_unparsed = {
        "habits": [
            {"name": "Coffee", "cost_inr": 50, "frequency": "daily", "categoryKey": "coffee_chai"},
        ],
        "unparsed": "I also mentioned something vague I couldn't parse.",
    }
    with patch("api.main._call_gemini", return_value=response_with_unparsed):
        res = client.post("/parse-habits", json={"text": "stuff"})
        assert "vague" in res.json()["unparsed"]


def test_parse_habits_empty_habits_list_is_ok(client, monkeypatch):
    """AI returning no parseable habits should still be a 200."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    with patch("api.main._call_gemini", return_value={"habits": [], "unparsed": "nothing found"}):
        res = client.post("/parse-habits", json={"text": "I have no habits"})
        assert res.status_code == 200
        assert res.json()["habits"] == []
