"""
tests/test_simulate.py

Tests for POST /simulate — the core simulation endpoint.

Coverage:
  - Happy path: response shape and field types
  - Yearly data: length, monotonicity, internal consistency
  - Sensitivity analysis: count, ranking, valid directions
  - All three scenarios run correctly
  - Custom allocation (weights instead of preset)
  - Input validation: bad preset, bad cpi_rate, empty habits, bad age, bad income
  - Edge cases: single habit, maximum horizon
"""

import copy
import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

PERCENTILE_KEYS = {"p10", "p25", "p50", "p75", "p90"}


def assert_percentile_band(band: dict, label: str):
    """Check band has all keys and values are monotonically non-decreasing."""
    assert PERCENTILE_KEYS == set(band.keys()), f"{label}: missing percentile keys"
    assert band["p10"] <= band["p25"] <= band["p50"] <= band["p75"] <= band["p90"], (
        f"{label}: percentile values not monotonically ordered: {band}"
    )


def simulate(client, payload) -> dict:
    res = client.post("/simulate", json=payload)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    return res.json()


# ── Happy path — response shape ───────────────────────────────────────────────

def test_simulate_returns_200(client, minimal_payload):
    res = client.post("/simulate", json=minimal_payload)
    assert res.status_code == 200


def test_simulate_top_level_keys(client, minimal_payload):
    body = simulate(client, minimal_payload)
    required = {
        "scenario", "horizon_years", "final_monthly_income",
        "total_habit_cost_nominal", "total_habit_cost_real",
        "opportunity_cost", "income_portfolio", "combined_portfolio",
        "combined_portfolio_real", "sensitivity", "warnings", "yearly",
    }
    assert required.issubset(body.keys()), (
        f"Missing keys: {required - set(body.keys())}"
    )


def test_simulate_scenario_echoed(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert body["scenario"] == minimal_payload["scenario"]


def test_simulate_horizon_echoed(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert body["horizon_years"] == minimal_payload["income_inputs"]["horizon_years"]


def test_simulate_final_monthly_income_positive(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert body["final_monthly_income"] > 0


def test_simulate_total_habit_cost_positive(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert body["total_habit_cost_nominal"] > 0
    assert body["total_habit_cost_real"] > 0


def test_simulate_opportunity_cost_shape(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert_percentile_band(body["opportunity_cost"], "opportunity_cost")


def test_simulate_income_portfolio_shape(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert_percentile_band(body["income_portfolio"], "income_portfolio")


def test_simulate_combined_portfolio_shape(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert_percentile_band(body["combined_portfolio"], "combined_portfolio")


def test_simulate_combined_real_shape(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert_percentile_band(body["combined_portfolio_real"], "combined_portfolio_real")


def test_simulate_combined_real_less_than_nominal(client, minimal_payload):
    """Inflation-adjusted (real) should be less than nominal for horizon > 0."""
    body = simulate(client, minimal_payload)
    assert body["combined_portfolio_real"]["p50"] < body["combined_portfolio"]["p50"]


def test_simulate_warnings_is_list(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert isinstance(body["warnings"], list)


# ── Yearly data ───────────────────────────────────────────────────────────────

def test_simulate_yearly_length(client, minimal_payload):
    body = simulate(client, minimal_payload)
    horizon = minimal_payload["income_inputs"]["horizon_years"]
    assert len(body["yearly"]) == horizon


def test_simulate_yearly_item_shape(client, minimal_payload):
    body = simulate(client, minimal_payload)
    yr = body["yearly"][0]
    required = {
        "year", "income_monthly", "habit_cost_nominal",
        "opportunity_cost", "income_portfolio", "combined_portfolio",
    }
    assert required.issubset(yr.keys())


def test_simulate_yearly_years_sequential(client, minimal_payload):
    body = simulate(client, minimal_payload)
    years = [yr["year"] for yr in body["yearly"]]
    assert years == list(range(1, minimal_payload["income_inputs"]["horizon_years"] + 1))


def test_simulate_yearly_opportunity_cost_grows(client, minimal_payload):
    """P50 opportunity cost should be higher in later years (compounding)."""
    body = simulate(client, minimal_payload)
    yearly = body["yearly"]
    first_p50 = yearly[0]["opportunity_cost"]["p50"]
    last_p50 = yearly[-1]["opportunity_cost"]["p50"]
    assert last_p50 > first_p50


def test_simulate_yearly_income_grows(client, minimal_payload):
    """Monthly income in final year should exceed starting income."""
    body = simulate(client, minimal_payload)
    yearly = body["yearly"]
    assert yearly[-1]["income_monthly"] > minimal_payload["income_inputs"]["monthly_income"]


def test_simulate_yearly_percentile_bands_valid(client, minimal_payload):
    body = simulate(client, minimal_payload)
    for i, yr in enumerate(body["yearly"]):
        assert_percentile_band(yr["opportunity_cost"],  f"yearly[{i}].opportunity_cost")
        assert_percentile_band(yr["income_portfolio"],  f"yearly[{i}].income_portfolio")
        assert_percentile_band(yr["combined_portfolio"], f"yearly[{i}].combined_portfolio")


# ── Sensitivity analysis ──────────────────────────────────────────────────────

def test_simulate_sensitivity_is_list(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert isinstance(body["sensitivity"], list)


def test_simulate_sensitivity_has_four_items(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert len(body["sensitivity"]) == 4


def test_simulate_sensitivity_item_shape(client, minimal_payload):
    body = simulate(client, minimal_payload)
    for s in body["sensitivity"]:
        assert "variable" in s
        assert "impact_pct" in s
        assert "direction" in s


def test_simulate_sensitivity_direction_valid(client, minimal_payload):
    body = simulate(client, minimal_payload)
    for s in body["sensitivity"]:
        assert s["direction"] in ("positive", "negative"), (
            f"Invalid direction: {s['direction']}"
        )


def test_simulate_sensitivity_sorted_by_impact(client, minimal_payload):
    """Sensitivity list should be sorted descending by |impact_pct|."""
    body = simulate(client, minimal_payload)
    impacts = [abs(s["impact_pct"]) for s in body["sensitivity"]]
    assert impacts == sorted(impacts, reverse=True), (
        f"Sensitivity not sorted: {impacts}"
    )


def test_simulate_horizon_has_positive_impact(client, minimal_payload):
    """Extending the horizon should always increase the portfolio (positive)."""
    body = simulate(client, minimal_payload)
    horizon_items = [s for s in body["sensitivity"] if "horizon" in s["variable"]]
    assert len(horizon_items) == 1
    assert horizon_items[0]["direction"] == "positive"


def test_simulate_inflation_has_negative_impact(client, minimal_payload):
    """Higher inflation should reduce real portfolio value (negative direction)."""
    body = simulate(client, minimal_payload)
    inflation_items = [s for s in body["sensitivity"] if "inflation" in s["variable"]]
    assert len(inflation_items) == 1
    assert inflation_items[0]["direction"] == "negative"


# ── Assumptions panel ─────────────────────────────────────────────────────────

def test_simulate_assumptions_present(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert "assumptions" in body


def test_simulate_assumptions_shape(client, minimal_payload):
    body = simulate(client, minimal_payload)
    a = body["assumptions"]
    required = {
        "simulation_paths", "return_method", "tax_regime",
        "income_model", "habit_model", "return_stats", "known_limitations",
    }
    assert required.issubset(a.keys())


def test_simulate_simulation_paths_matches_input(client, minimal_payload):
    body = simulate(client, minimal_payload)
    assert body["assumptions"]["simulation_paths"] == minimal_payload["n_simulations"]


# ── Three scenarios ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("scenario", ["conservative", "base", "optimistic"])
def test_simulate_all_scenarios_return_200(client, minimal_payload, scenario):
    payload = copy.deepcopy(minimal_payload)
    payload["scenario"] = scenario
    res = client.post("/simulate", json=payload)
    assert res.status_code == 200, f"Scenario '{scenario}' failed: {res.text}"


@pytest.mark.parametrize("scenario", ["conservative", "base", "optimistic"])
def test_simulate_scenario_echoed_correctly(client, minimal_payload, scenario):
    payload = copy.deepcopy(minimal_payload)
    payload["scenario"] = scenario
    body = simulate(client, payload)
    assert body["scenario"] == scenario


def test_simulate_optimistic_greater_than_conservative(client, minimal_payload):
    """Optimistic P50 combined portfolio should exceed conservative P50."""
    cons = copy.deepcopy(minimal_payload)
    cons["scenario"] = "conservative"
    opti = copy.deepcopy(minimal_payload)
    opti["scenario"] = "optimistic"

    cons_body = simulate(client, cons)
    opti_body = simulate(client, opti)

    assert opti_body["combined_portfolio"]["p50"] > cons_body["combined_portfolio"]["p50"], (
        "Optimistic P50 should exceed conservative P50"
    )


# ── Custom allocation ─────────────────────────────────────────────────────────

def test_simulate_custom_allocation_valid(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["allocation"] = {"equity": 0.7, "gold": 0.2, "fd": 0.1}
    res = client.post("/simulate", json=payload)
    assert res.status_code == 200


def test_simulate_custom_allocation_aggressive_vs_conservative(client, minimal_payload):
    """All-equity should have a higher P50 than all-FD over 5 years."""
    aggressive = copy.deepcopy(minimal_payload)
    aggressive["allocation"] = {"equity": 1.0, "gold": 0.0, "fd": 0.0}
    conservative = copy.deepcopy(minimal_payload)
    conservative["allocation"] = {"equity": 0.0, "gold": 0.0, "fd": 1.0}

    agg_body = simulate(client, aggressive)
    con_body = simulate(client, conservative)

    assert agg_body["combined_portfolio"]["p50"] > con_body["combined_portfolio"]["p50"]


# ── Multiple habits ───────────────────────────────────────────────────────────

def test_simulate_multi_habit_higher_cost(client, minimal_payload, multi_habit_payload):
    """More habits → higher total nominal cost."""
    single = simulate(client, minimal_payload)
    multi  = simulate(client, multi_habit_payload)
    assert multi["total_habit_cost_nominal"] > single["total_habit_cost_nominal"]


def test_simulate_multi_habit_higher_opportunity_cost(client, minimal_payload, multi_habit_payload):
    single = simulate(client, minimal_payload)
    multi  = simulate(client, multi_habit_payload)
    assert multi["opportunity_cost"]["p50"] > single["opportunity_cost"]["p50"]


# ── Input validation — expect 400 or 422 ─────────────────────────────────────

def test_simulate_unknown_preset_returns_400(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["allocation"] = {"preset": "does_not_exist"}
    res = client.post("/simulate", json=payload)
    assert res.status_code == 400
    assert "does_not_exist" in res.json()["detail"]


def test_simulate_custom_weights_not_summing_to_one_returns_400(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["allocation"] = {"equity": 0.5, "gold": 0.5, "fd": 0.5}   # sums to 1.5
    res = client.post("/simulate", json=payload)
    assert res.status_code == 400


def test_simulate_empty_habits_returns_422(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["habits"] = []
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


def test_simulate_negative_income_returns_422(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["income_inputs"]["monthly_income"] = -1000
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


def test_simulate_zero_income_returns_422(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["income_inputs"]["monthly_income"] = 0
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


def test_simulate_age_too_low_returns_422(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["income_inputs"]["current_age"] = 15
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


def test_simulate_age_too_high_returns_422(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["income_inputs"]["current_age"] = 75
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


def test_simulate_cpi_too_low_returns_422(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["cpi_rate"] = 0.001     # below 2% minimum
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


def test_simulate_cpi_too_high_returns_422(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["cpi_rate"] = 0.20      # above 12% maximum
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


def test_simulate_n_simulations_too_low_returns_422(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["n_simulations"] = 50   # below 100 minimum
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


def test_simulate_invalid_scenario_returns_422(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["scenario"] = "moonshot"
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


def test_simulate_invalid_frequency_returns_422(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["habits"][0]["frequency"] = "hourly"
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


def test_simulate_negative_habit_cost_returns_422(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["habits"][0]["cost_inr"] = -100
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


def test_simulate_no_allocation_returns_422(client, minimal_payload):
    """Must provide either preset or custom weights."""
    payload = copy.deepcopy(minimal_payload)
    payload["allocation"] = {}
    res = client.post("/simulate", json=payload)
    assert res.status_code == 422


# ── Longer horizon ────────────────────────────────────────────────────────────

def test_simulate_20_year_horizon(client, minimal_payload):
    payload = copy.deepcopy(minimal_payload)
    payload["income_inputs"]["horizon_years"] = 20
    body = simulate(client, payload)
    assert len(body["yearly"]) == 20
    assert body["horizon_years"] == 20


def test_simulate_longer_horizon_higher_portfolio(client, minimal_payload):
    """20-year portfolio P50 should exceed 5-year portfolio P50."""
    short = copy.deepcopy(minimal_payload)
    short["income_inputs"]["horizon_years"] = 5

    long_ = copy.deepcopy(minimal_payload)
    long_["income_inputs"]["horizon_years"] = 20

    short_body = simulate(client, short)
    long_body  = simulate(client, long_)

    assert long_body["combined_portfolio"]["p50"] > short_body["combined_portfolio"]["p50"]


# ── All sector IDs work ───────────────────────────────────────────────────────

def test_simulate_all_available_sectors(client, minimal_payload):
    """Every sector returned by /sectors should be accepted by /simulate."""
    sectors = client.get("/sectors").json()["sectors"]
    for sector in sectors:
        payload = copy.deepcopy(minimal_payload)
        payload["income_inputs"]["sector_id"] = sector["id"]
        res = client.post("/simulate", json=payload)
        assert res.status_code == 200, (
            f"Sector '{sector['id']}' failed with {res.status_code}: {res.text}"
        )


# ── All preset allocations work ───────────────────────────────────────────────

def test_simulate_all_preset_allocations(client, minimal_payload):
    """Every allocation preset from /allocations should be accepted by /simulate."""
    allocs = client.get("/allocations").json()["allocations"]
    for alloc in allocs:
        payload = copy.deepcopy(minimal_payload)
        payload["allocation"] = {"preset": alloc["id"]}
        res = client.post("/simulate", json=payload)
        assert res.status_code == 200, (
            f"Preset '{alloc['id']}' failed with {res.status_code}: {res.text}"
        )
