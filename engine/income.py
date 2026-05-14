"""
engine/income.py

Income trajectory engine.

Models income growth as a deterministic base trajectory
with documented stochastic extensions for job switches.

Design decisions and their rationale:

1. DETERMINISTIC BASE: We use a fixed sector increment rate (not stochastic)
   for the base trajectory. This gives the user a clear, auditable central estimate.
   Uncertainty is shown via conservative/base/optimistic scenarios, not hidden
   inside a stochastic process that most users can't interpret.

2. CAREER STAGE SLOWDOWN: Empirically, salary growth rate declines with seniority.
   Early career (0-10yr): full sector rate applies.
   Mid career (10-20yr): 75% of sector rate (seniority compression).
   Late career (20yr+): 50% of sector rate.
   Source: broad consensus in HR literature; WTW data shows senior increment
   budgets are lower than junior in all sectors.

3. JOB SWITCH EVENTS: India-specific. Michael Page 2024: job switches give
   20-40% salary jump (mean 25%, std 8%). Average switch every 3.5 years.
   In BASE scenario: one switch included at year 4.
   In OPTIMISTIC: two switches (yr 3 and yr 7).
   In CONSERVATIVE: no switches (stays in same job).

4. LIFECYCLE SAVINGS RATE: Savings rate is NOT static. It follows a
   well-documented lifecycle pattern (Modigliani, confirmed in Indian
   NSSO household data):
   - Age 22-28: 8-12% (high rent, low base, lifestyle inflation)
   - Age 28-35: 15-22% (income growing, lifestyle stabilising)
   - Age 35-45: 25-35% (peak earning, loans partly paid)
   - Age 45-55: 20-28% (kids education, ageing parents offset gains)
   We interpolate smoothly across these.

Honest limitation:
   This model does not include EMI impact, marriage costs, child costs
   as explicit events. Those are out of scope for MVP. The lifecycle
   savings rate curve implicitly captures their average effect.
"""

import json
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

DATA_DIR = Path(__file__).parent.parent / "data"
SECTOR_FILE = DATA_DIR / "sector_increments.json"


@dataclass
class IncomeInputs:
    """All inputs needed to project an income trajectory."""
    monthly_income: float           # Current gross monthly income (INR)
    current_age: int                # User's current age
    sector_id: str                  # Key from sector_increments.json
    performance: Literal[
        "below_average", "average", "above_average", "top_performer"
    ] = "average"
    horizon_years: int = 20


@dataclass
class YearlyIncomePoint:
    """Income and savings data for a single year."""
    year: int
    age: int
    monthly_gross: float
    annual_gross: float
    savings_rate: float             # Fraction of income available to invest
    monthly_investable: float       # monthly_gross * savings_rate
    annual_investable: float
    yoy_growth_rate: float          # Growth vs prior year (0.095 = 9.5%)
    event: str = ""                 # e.g. "job switch" for transparency


@dataclass
class IncomeTrajectory:
    """Full income projection with scenario metadata."""
    scenario: Literal["conservative", "base", "optimistic"]
    inputs: IncomeInputs
    years: list[YearlyIncomePoint]
    effective_increment_rate: float   # Actual rate used (after performance multiplier)
    assumptions: dict = field(default_factory=dict)

    @property
    def final_monthly_income(self) -> float:
        return self.years[-1].monthly_gross

    @property
    def total_investable(self) -> float:
        return sum(y.annual_investable for y in self.years)


def _load_sector_data() -> dict:
    with open(SECTOR_FILE) as f:
        return json.load(f)


def _career_stage_multiplier(years_of_experience: int) -> float:
    """
    Returns growth rate multiplier based on career stage.
    Captures salary compression at senior levels.
    """
    if years_of_experience <= 10:
        return 1.0
    elif years_of_experience <= 20:
        # Linear decline from 1.0 to 0.75 over years 10-20
        return 1.0 - 0.025 * (years_of_experience - 10)
    else:
        # Linear decline from 0.75 to 0.50 over years 20-30
        return max(0.50, 0.75 - 0.025 * (years_of_experience - 20))


def _lifecycle_savings_rate(age: int) -> float:
    """
    Returns savings rate as a fraction of gross income based on age.
    Derived from Modigliani lifecycle hypothesis calibrated to
    India NSSO household savings data.

    Note: This is average behaviour. Individual variation is high.
    """
    if age < 25:
        return 0.08
    elif age < 28:
        # 8% -> 12%: early career ramp
        t = (age - 25) / 3
        return 0.08 + t * 0.04
    elif age < 35:
        # 12% -> 22%: income accelerating
        t = (age - 28) / 7
        return 0.12 + t * 0.10
    elif age < 45:
        # 22% -> 32%: peak earning
        t = (age - 35) / 10
        return 0.22 + t * 0.10
    elif age < 55:
        # 32% -> 24%: kids education, parents, mild decline
        t = (age - 45) / 10
        return 0.32 - t * 0.08
    else:
        return 0.24


def _job_switch_years(scenario: str, horizon: int) -> list[int]:
    """
    Returns list of years (1-indexed) in which a job switch occurs.
    Conservative: none. Base: one at year 4. Optimistic: years 3 and 7.
    """
    if scenario == "conservative":
        return []
    elif scenario == "base":
        switches = [4]
        return [y for y in switches if y <= horizon]
    else:  # optimistic
        switches = [3, 7]
        return [y for y in switches if y <= horizon]


def _job_switch_jump(scenario: str) -> float:
    """
    Salary jump from a job switch.
    Mean 25%, std 8% (Michael Page India 2024).
    Conservative: no switches. Base: mean jump. Optimistic: mean + 0.5 std.
    """
    if scenario == "base":
        return 0.25   # mean
    elif scenario == "optimistic":
        return 0.29   # mean + 0.5*std
    return 0.0


def _scenario_increment_rate(
    base_rate: float,
    perf_multiplier: float,
    scenario: str,
    sector_std: float,
) -> float:
    """
    Adjust base sector rate for scenario.
    Conservative: -1 std of historical sector variance.
    Base: base rate * performance multiplier.
    Optimistic: +0.5 std.

    We cap performance multiplier effect in conservative scenario
    (top performer in a bad market still constrained by budget).
    """
    if scenario == "conservative":
        raw = (base_rate - sector_std) * min(perf_multiplier, 1.2) / 100
    elif scenario == "base":
        raw = base_rate * perf_multiplier / 100
    else:  # optimistic
        raw = (base_rate + 0.5 * sector_std) * perf_multiplier / 100

    return max(0.02, min(raw, 0.40))   # bound: 2% floor, 40% ceiling


def project_income(
    inputs: IncomeInputs,
    scenario: Literal["conservative", "base", "optimistic"] = "base",
) -> IncomeTrajectory:
    """
    Project income and investable savings year by year.

    Returns an IncomeTrajectory with one YearlyIncomePoint per year,
    starting from year 0 (current state).
    """
    sector_data = _load_sector_data()

    if inputs.sector_id not in sector_data["sectors"]:
        raise ValueError(
            f"Unknown sector '{inputs.sector_id}'. "
            f"Valid: {list(sector_data['sectors'].keys())}"
        )

    sector = sector_data["sectors"][inputs.sector_id]
    perf_multipliers = sector_data["performance_multipliers"]
    perf_multiplier = perf_multipliers[inputs.performance]

    effective_rate = _scenario_increment_rate(
        base_rate=sector["mean_increment_pct"],
        perf_multiplier=perf_multiplier,
        scenario=scenario,
        sector_std=sector["std_dev_pct"],
    )

    switch_years = _job_switch_years(scenario, inputs.horizon_years)
    switch_jump = _job_switch_jump(scenario)

    points: list[YearlyIncomePoint] = []
    monthly = inputs.monthly_income
    years_exp = max(0, inputs.current_age - 22)  # proxy: joined work at 22

    # Year 0: current state
    savings_rate_0 = _lifecycle_savings_rate(inputs.current_age)
    points.append(YearlyIncomePoint(
        year=0,
        age=inputs.current_age,
        monthly_gross=round(monthly),
        annual_gross=round(monthly * 12),
        savings_rate=round(savings_rate_0, 3),
        monthly_investable=round(monthly * savings_rate_0),
        annual_investable=round(monthly * savings_rate_0 * 12),
        yoy_growth_rate=0.0,
        event="current",
    ))

    for yr in range(1, inputs.horizon_years + 1):
        age = inputs.current_age + yr
        exp = years_exp + yr
        stage_mult = _career_stage_multiplier(exp)
        year_rate = effective_rate * stage_mult
        prev_monthly = monthly

        monthly = monthly * (1 + year_rate)

        event = ""
        if yr in switch_years:
            monthly = monthly * (1 + switch_jump)
            event = f"job switch (+{switch_jump:.0%})"

        savings_rate = _lifecycle_savings_rate(age)
        monthly_investable = monthly * savings_rate
        yoy_growth = (monthly - prev_monthly) / prev_monthly

        points.append(YearlyIncomePoint(
            year=yr,
            age=age,
            monthly_gross=round(monthly),
            annual_gross=round(monthly * 12),
            savings_rate=round(savings_rate, 3),
            monthly_investable=round(monthly_investable),
            annual_investable=round(monthly_investable * 12),
            yoy_growth_rate=round(yoy_growth, 4),
            event=event,
        ))

    assumptions = {
        "sector": sector["name"],
        "sector_base_rate_pct": sector["mean_increment_pct"],
        "sector_std_dev_pct": sector["std_dev_pct"],
        "performance_tier": inputs.performance,
        "performance_multiplier": perf_multiplier,
        "effective_rate_pct": round(effective_rate * 100, 2),
        "job_switches": switch_years,
        "job_switch_jump_pct": round(switch_jump * 100, 1),
        "savings_rate_model": "Modigliani lifecycle, calibrated to India NSSO",
        "career_stage_slowdown": "10% reduction per decade after 10yr experience",
        "source": sector["source"],
        "limitations": [
            "Does not model EMI, marriage, or child cost events explicitly.",
            "Lifecycle savings rate is population average — individual varies widely.",
            "Job switch timing is fixed, not probabilistic, for interpretability.",
        ]
    }

    return IncomeTrajectory(
        scenario=scenario,
        inputs=inputs,
        years=points,
        effective_increment_rate=effective_rate,
        assumptions=assumptions,
    )


def project_all_scenarios(inputs: IncomeInputs) -> dict[str, IncomeTrajectory]:
    """Convenience: returns all three scenarios for comparison."""
    return {
        s: project_income(inputs, scenario=s)
        for s in ("conservative", "base", "optimistic")
    }
