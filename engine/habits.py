"""
engine/habits.py

Habit cost projection engine.

Key modelling decisions:

1. CATEGORY-SPECIFIC INFLATION CREEP
   Not all habits inflate at the same rate. Restaurant food inflates faster
   than general CPI. Tobacco has additional GST/sin tax escalation.
   Streaming services use their own pricing logic.
   We use category-specific creep rates grounded in RBI/MOSPI sector CPI data.

2. NO CESSATION MODELLING IN MVP
   We do not model habit quitting probability. This is a deliberate choice:
   - Cessation rates vary enormously by person and habit type
   - Modelling it requires behavioural parameters we cannot estimate per-user
   - Including it would give optimistic bias (people tend to overestimate quitting)
   - We note this as a limitation: actual cost may be lower if habits are quit
   This makes the model conservative (slightly pessimistic) — which is the
   correct direction for a financial planning tool.

3. HEDONIC ADAPTATION
   People tend to upgrade their habits over time — a ₹50 chai becomes a
   ₹150 specialty coffee. This is captured by the creep rate being higher
   than pure CPI for discretionary categories.

Category creep rates source:
   - Food/restaurants: MOSPI CPI Food & Beverages avg 2015-2024 ~7%
   - Tobacco: sin tax escalation + CPI ~8% historically
   - Transport: fuel + app pricing ~6%
   - Entertainment/OTT: platform pricing history (Netflix, Spotify) ~10%
   - General: India CPI headline ~6%
"""

from dataclasses import dataclass, field
from typing import Literal

# Category-specific annual cost inflation rates
# Source: MOSPI CPI sub-indices 2015-2024, platform pricing history
CATEGORY_CREEP_RATES: dict[str, float] = {
    "food_restaurant":  0.072,   # Eating out — MOSPI food CPI + quality upgrade
    "food_delivery":    0.080,   # Delivery apps — platform commission + food inflation
    "tobacco":          0.085,   # Sin tax escalation + CPI
    "alcohol":          0.075,   # State excise + general inflation
    "coffee_chai":      0.070,   # Beverages CPI + quality upgrade
    "fuel":             0.060,   # Fuel price avg change
    "transport_app":    0.065,   # Ola/Uber pricing trend
    "entertainment":    0.100,   # OTT subscriptions + cinema — platform pricing data
    "gym_wellness":     0.080,   # Fitness industry pricing
    "shopping":         0.060,   # General consumer goods CPI
    "general":          0.060,   # Default: headline CPI
}

VALID_CATEGORIES = list(CATEGORY_CREEP_RATES.keys())
VALID_FREQUENCIES = ("daily", "weekly", "monthly")


@dataclass
class Habit:
    """A single recurring habit."""
    name: str
    cost_inr: float               # Cost per occurrence in INR
    frequency: Literal["daily", "weekly", "monthly"]
    category: str = "general"     # Maps to CATEGORY_CREEP_RATES

    def __post_init__(self):
        if self.cost_inr < 0:
            raise ValueError(f"Habit cost cannot be negative: {self.cost_inr}")
        if self.frequency not in VALID_FREQUENCIES:
            raise ValueError(f"Frequency must be one of {VALID_FREQUENCIES}")
        if self.category not in CATEGORY_CREEP_RATES:
            raise ValueError(
                f"Category '{self.category}' not recognised. "
                f"Valid: {VALID_CATEGORIES}"
            )

    @property
    def monthly_cost(self) -> float:
        """Convert per-occurrence cost to monthly cost."""
        if self.frequency == "daily":
            return self.cost_inr * 30.44   # Average days per month
        elif self.frequency == "weekly":
            return self.cost_inr * 4.333   # Average weeks per month
        else:
            return self.cost_inr

    @property
    def creep_rate(self) -> float:
        return CATEGORY_CREEP_RATES[self.category]


@dataclass
class HabitYearPoint:
    year: int
    monthly_cost: float       # Monthly cost in that year (nominal)
    annual_cost: float        # Annual cost in that year (nominal)
    cumulative_spent: float   # Total spent from year 0 to this year (nominal)
    real_monthly_cost: float  # Monthly cost in today's rupees (inflation-adjusted)


@dataclass
class HabitProjection:
    """Full cost projection for a list of habits."""
    habits: list[Habit]
    horizon_years: int
    inflation_rate: float
    years: list[HabitYearPoint]
    total_nominal_spent: float
    total_real_spent: float           # In today's rupees
    assumptions: dict = field(default_factory=dict)


def project_habits(
    habits: list[Habit],
    horizon_years: int,
    cpi_rate: float = 0.06,
) -> HabitProjection:
    """
    Project total habit spending over the horizon, accounting for
    category-specific cost inflation.

    Each habit's monthly cost compounds at its category-specific creep rate.
    Total monthly cost is the sum across all habits.

    Returns HabitProjection with year-by-year breakdown.
    """
    if not habits:
        raise ValueError("At least one habit required.")
    if horizon_years < 1:
        raise ValueError("Horizon must be at least 1 year.")
    if not 0 < cpi_rate < 0.25:
        raise ValueError(f"CPI rate {cpi_rate} outside reasonable range (0-25%)")

    # Starting monthly costs per habit
    base_monthly = {h.name: h.monthly_cost for h in habits}
    # Current monthly totals (will compound each year)
    current_monthly = {h.name: h.monthly_cost for h in habits}

    year_points: list[HabitYearPoint] = []
    cumulative = 0.0

    # Year 0: current state
    total_mo_0 = sum(current_monthly.values())
    year_points.append(HabitYearPoint(
        year=0,
        monthly_cost=round(total_mo_0, 2),
        annual_cost=round(total_mo_0 * 12, 2),
        cumulative_spent=0.0,
        real_monthly_cost=round(total_mo_0, 2),   # today's rupees
    ))

    for yr in range(1, horizon_years + 1):
        # Compound each habit's cost by its category creep rate
        year_monthly = 0.0
        for h in habits:
            current_monthly[h.name] *= (1 + h.creep_rate)
            year_monthly += current_monthly[h.name]

        annual = year_monthly * 12
        cumulative += annual

        # Real value: deflate by CPI to express in today's purchasing power
        real_monthly = year_monthly / ((1 + cpi_rate) ** yr)

        year_points.append(HabitYearPoint(
            year=yr,
            monthly_cost=round(year_monthly, 2),
            annual_cost=round(annual, 2),
            cumulative_spent=round(cumulative, 2),
            real_monthly_cost=round(real_monthly, 2),
        ))

    total_nominal = year_points[-1].cumulative_spent
    # Real total: sum of each year's cost deflated to today's rupees
    total_real = sum(
        yp.annual_cost / ((1 + cpi_rate) ** yp.year)
        for yp in year_points if yp.year > 0
    )

    assumptions = {
        "habit_count": len(habits),
        "habits": [
            {
                "name": h.name,
                "monthly_cost_today": round(h.monthly_cost, 2),
                "category": h.category,
                "annual_creep_rate_pct": round(h.creep_rate * 100, 1),
            }
            for h in habits
        ],
        "cpi_rate_pct": round(cpi_rate * 100, 1),
        "limitations": [
            "Cessation probability not modelled — actual cost may be lower if habits are quit.",
            "Creep rates are category averages; individual brand/product pricing may differ.",
            "No hedonic upgrade modelled beyond category-level creep.",
        ],
        "sources": {
            "food_restaurant": "MOSPI CPI Food & Beverages 2015-2024",
            "tobacco": "Sin tax escalation history + CPI",
            "entertainment": "OTT platform pricing trend (Netflix/Spotify/Prime India)",
            "general": "RBI CPI headline average 2014-2024",
        }
    }

    return HabitProjection(
        habits=habits,
        horizon_years=horizon_years,
        inflation_rate=cpi_rate,
        years=year_points,
        total_nominal_spent=round(total_nominal, 2),
        total_real_spent=round(total_real, 2),
        assumptions=assumptions,
    )
