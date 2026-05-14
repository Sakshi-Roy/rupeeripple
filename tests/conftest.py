"""
tests/conftest.py

Shared fixtures for the RupeeRipple API test suite.
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture(scope="session")
def client():
    """FastAPI test client — reused across all tests in the session."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def minimal_payload():
    """Smallest valid SimulateRequest payload — used as a base for mutation tests."""
    return {
        "income_inputs": {
            "monthly_income": 80000,
            "current_age": 28,
            "sector_id": "it_software",
            "performance": "average",
            "horizon_years": 5,          # short horizon → fast test
        },
        "habits": [
            {
                "name": "Daily coffee",
                "cost_inr": 150,
                "frequency": "daily",
                "category": "general",
            }
        ],
        "allocation": {"preset": "balanced"},
        "cpi_rate": 0.06,
        "n_simulations": 100,            # minimum → fast test
        "scenario": "base",
    }


@pytest.fixture
def multi_habit_payload(minimal_payload):
    """Payload with multiple habit categories for richer tests."""
    payload = minimal_payload.copy()
    payload["habits"] = [
        {"name": "Coffee",        "cost_inr": 150,  "frequency": "daily",   "category": "general"},
        {"name": "Swiggy",        "cost_inr": 400,  "frequency": "weekly",  "category": "food_delivery"},
        {"name": "Netflix",       "cost_inr": 800,  "frequency": "monthly", "category": "entertainment"},
        {"name": "Petrol",        "cost_inr": 3000, "frequency": "monthly", "category": "fuel"},
    ]
    return payload
