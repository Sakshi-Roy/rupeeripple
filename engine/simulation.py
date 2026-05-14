"""
engine/simulation.py

Monte Carlo simulation orchestrator.

This is the brain of the engine. It combines:
- Income trajectory (from income.py)
- Habit costs (from habits.py)
- Market returns via block bootstrap (from returns.py)
- Tax adjustment (from tax.py)

Into a coherent simulation of: "if you invested what you spend on habits
plus a portion of your growing income, what would you have?"

Design principles:
1. TRANSPARENCY: Every simulation result carries its assumptions.
   Nothing is a black box.

2. HONEST UNCERTAINTY: We run N paths (default 1000) and report
   the distribution — not a point estimate. P10/P25/P50/P75/P90.

3. SEPARATION OF CONCERNS:
   - The opportunity cost of habits: what if you'd invested JUST
     the habit spend, from day one?
   - The income-linked portfolio: what if you invested your savings
     rate * income every month?
   - Combined: both together.
   This separation is pedagogically valuable and honest.

4. REAL vs NOMINAL: All outputs are provided in both nominal (future
   rupees) and real (today's rupees, CPI-deflated) terms.

5. SENSITIVITY ANALYSIS: After simulation, we compute which input
   variable has the largest impact on the P50 outcome. This is more
   actionable than the simulation itself.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Literal

from .income import IncomeTrajectory, IncomeInputs, project_income
from .habits import HabitProjection, Habit, project_habits
from .returns import ReturnSampler, AssetAllocation, get_sampler
from .tax import TaxProfile, apply_tax_to_monthly_returns


N_SIMULATIONS_DEFAULT = 1000
PERCENTILES = [10, 25, 50, 75, 90]


@dataclass
class SimulationInputs:
    """Complete input set for one simulation run."""
    # Income
    income_inputs: IncomeInputs

    # Habits
    habits: list[Habit]

    # Portfolio
    allocation: AssetAllocation
    cpi_rate: float = 0.06

    # Simulation
    n_simulations: int = N_SIMULATIONS_DEFAULT
    scenario: Literal["conservative", "base", "optimistic"] = "base"

    def __post_init__(self):
        if self.n_simulations < 100:
            raise ValueError("n_simulations must be >= 100 for reliable percentiles.")
        if not 0.02 <= self.cpi_rate <= 0.12:
            raise ValueError(f"CPI rate {self.cpi_rate} outside [2%, 12%]")


@dataclass
class PercentileResult:
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float

    def to_dict(self) -> dict:
        return {
            "p10": round(self.p10),
            "p25": round(self.p25),
            "p50": round(self.p50),
            "p75": round(self.p75),
            "p90": round(self.p90),
        }


@dataclass
class YearlySimResult:
    """Simulation percentiles at a specific year."""
    year: int
    habit_cost_nominal: float         # Deterministic: total habit cost to date
    habit_cost_real: float            # In today's rupees
    opportunity_cost: PercentileResult   # What habit money could have been
    income_portfolio: PercentileResult   # What savings rate * income could be
    combined_portfolio: PercentileResult # Both together
    income_monthly: float             # Deterministic income in this year


@dataclass
class SensitivityResult:
    """Which input variable moves the P50 outcome the most."""
    variable: str
    base_p50: float
    perturbed_p50: float
    impact_pct: float      # % change in P50 from 10% change in variable
    direction: str         # "positive" or "negative"


@dataclass
class SimulationResult:
    """Complete simulation output."""
    inputs: SimulationInputs
    scenario: str
    income_trajectory: IncomeTrajectory
    habit_projection: HabitProjection
    yearly: list[YearlySimResult]
    final_year: YearlySimResult
    sensitivity: list[SensitivityResult]
    assumptions: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        """Clean summary for API response."""
        fy = self.final_year
        return {
            "scenario": self.scenario,
            "horizon_years": self.inputs.income_inputs.horizon_years,
            "final_monthly_income": round(self.income_trajectory.final_monthly_income),
            "total_habit_cost_nominal": round(self.habit_projection.total_nominal_spent),
            "total_habit_cost_real": round(self.habit_projection.total_real_spent),
            "opportunity_cost": fy.opportunity_cost.to_dict(),
            "income_portfolio": fy.income_portfolio.to_dict(),
            "combined_portfolio": fy.combined_portfolio.to_dict(),
            "combined_portfolio_real": {
                k: round(v / ((1 + self.inputs.cpi_rate) **
                              self.inputs.income_inputs.horizon_years))
                for k, v in fy.combined_portfolio.to_dict().items()
            },
            "sensitivity": [
                {
                    "variable": s.variable,
                    "impact_pct": round(s.impact_pct, 1),
                    "direction": s.direction,
                }
                for s in sorted(self.sensitivity, key=lambda x: abs(x.impact_pct), reverse=True)
            ],
            "warnings": self.warnings,
        }


def _compute_percentiles(values: np.ndarray) -> PercentileResult:
    vals = np.percentile(values, PERCENTILES)
    return PercentileResult(
        p10=float(vals[0]),
        p25=float(vals[1]),
        p50=float(vals[2]),
        p75=float(vals[3]),
        p90=float(vals[4]),
    )


def _run_paths(
    monthly_contributions: list[float],   # one value per month
    sampler: ReturnSampler,
    allocation: AssetAllocation,
    tax_profile: TaxProfile,
    allocation_equity: float,
    allocation_gold: float,
    allocation_fd: float,
    n_sims: int,
    rng: np.random.Generator,
    record_years: list[int],
) -> dict[int, np.ndarray]:
    """
    Core simulation loop. Vectorised across simulations for speed.

    Returns dict: year -> array of portfolio values across n_sims paths.
    """
    n_months = len(monthly_contributions)
    contribs = np.array(monthly_contributions, dtype=np.float64)

    # Pre-sample all return paths at once — much faster than looping
    all_returns = np.empty((n_sims, n_months), dtype=np.float64)
    for i in range(n_sims):
        raw = sampler.sample_portfolio_returns(allocation, n_months, rng)
        taxed = apply_tax_to_monthly_returns(
            raw.tolist(), allocation_equity, allocation_gold, allocation_fd, tax_profile
        )
        all_returns[i] = taxed

    # Vectorised compound growth
    # portfolio[sim, month] = (portfolio[sim, month-1] + contrib[month]) * (1 + return[sim, month])
    portfolio = np.zeros((n_sims,), dtype=np.float64)
    record_months = {y * 12 - 1: y for y in record_years if y > 0}
    year_snapshots: dict[int, np.ndarray] = {}

    for m in range(n_months):
        portfolio = (portfolio + contribs[m]) * (1 + all_returns[:, m])
        if m in record_months:
            year_snapshots[record_months[m]] = portfolio.copy()

    return year_snapshots


def run_simulation(inputs: SimulationInputs) -> SimulationResult:
    """
    Run the full Monte Carlo simulation.

    Steps:
    1. Project income trajectory for the scenario
    2. Project habit costs
    3. Build monthly contribution series (habits + income savings)
    4. Run N simulation paths through the return sampler
    5. Record percentile distributions at each year
    6. Compute sensitivity analysis
    7. Package results with full assumptions
    """
    warnings: list[str] = []

    # --- Step 1: Income ---
    income_traj = project_income(inputs.income_inputs, scenario=inputs.scenario)

    # --- Step 2: Habits ---
    habit_proj = project_habits(
        inputs.habits,
        inputs.income_inputs.horizon_years,
        inputs.cpi_rate,
    )

    # --- Step 3: Build monthly contribution series ---
    horizon_years = inputs.income_inputs.horizon_years
    n_months = horizon_years * 12
    tax_profile = TaxProfile.from_income(inputs.income_inputs.monthly_income * 12)

    # Monthly habit contributions (what they spend on habits → redirect to invest)
    habit_monthly_series = _build_habit_monthly_series(inputs.habits, n_months)

    # Monthly income-savings contributions (savings_rate * income per month)
    income_monthly_series = _build_income_monthly_series(income_traj, n_months)

    # Combined
    combined_series = [h + i for h, i in zip(habit_monthly_series, income_monthly_series)]

    # --- Step 4: Run simulations ---
    sampler = get_sampler()
    rng = np.random.default_rng(42)  # Fixed seed for reproducibility
    record_years = list(range(1, horizon_years + 1))

    habit_snapshots = _run_paths(
        habit_monthly_series, sampler, inputs.allocation, tax_profile,
        inputs.allocation.equity, inputs.allocation.gold, inputs.allocation.fd,
        inputs.n_simulations, rng, record_years,
    )

    rng2 = np.random.default_rng(43)
    income_snapshots = _run_paths(
        income_monthly_series, sampler, inputs.allocation, tax_profile,
        inputs.allocation.equity, inputs.allocation.gold, inputs.allocation.fd,
        inputs.n_simulations, rng2, record_years,
    )

    rng3 = np.random.default_rng(44)
    combined_snapshots = _run_paths(
        combined_series, sampler, inputs.allocation, tax_profile,
        inputs.allocation.equity, inputs.allocation.gold, inputs.allocation.fd,
        inputs.n_simulations, rng3, record_years,
    )

    # --- Step 5: Package yearly results ---
    yearly_results: list[YearlySimResult] = []
    for yr in record_years:
        habit_pt = habit_proj.years[yr]
        income_pt = income_traj.years[yr]

        yearly_results.append(YearlySimResult(
            year=yr,
            habit_cost_nominal=habit_pt.cumulative_spent,
            habit_cost_real=sum(
                habit_proj.years[y].annual_cost / ((1 + inputs.cpi_rate) ** y)
                for y in range(1, yr + 1)
            ),
            opportunity_cost=_compute_percentiles(habit_snapshots[yr]),
            income_portfolio=_compute_percentiles(income_snapshots[yr]),
            combined_portfolio=_compute_percentiles(combined_snapshots[yr]),
            income_monthly=income_pt.monthly_gross,
        ))

    # --- Step 6: Sensitivity analysis ---
    sensitivity = _compute_sensitivity(inputs, income_traj, habit_proj, sampler)

    # --- Step 7: Warnings ---
    if inputs.n_simulations < 500:
        warnings.append(
            f"Running only {inputs.n_simulations} simulations. "
            "Tail percentiles (P10/P90) may be unstable. Use 1000+ for reliable results."
        )
    final_income = income_traj.final_monthly_income
    if final_income > inputs.income_inputs.monthly_income * 10:
        warnings.append(
            "Income projection implies very high growth. "
            "Consider whether the sector rate and performance tier are realistic."
        )

    assumptions = {
        "simulation_paths": inputs.n_simulations,
        "return_method": "Block bootstrap from historical data (block size=6 months)",
        "tax_regime": "India new regime, July 2024 budget",
        "income_model": income_traj.assumptions,
        "habit_model": habit_proj.assumptions,
        "return_stats": sampler.get_empirical_stats(inputs.allocation),
        "known_limitations": [
            "Returns bootstrapped from 25yr history — thin for tail estimation.",
            "Tax applied as blended rate approximation, not lot-by-lot.",
            "Life events (marriage, home loan, illness) not explicitly modelled.",
            "Habit cessation not modelled — costs assumed permanent.",
            "Correlation between inflation and equity returns assumed stationary.",
        ]
    }

    return SimulationResult(
        inputs=inputs,
        scenario=inputs.scenario,
        income_trajectory=income_traj,
        habit_projection=habit_proj,
        yearly=yearly_results,
        final_year=yearly_results[-1],
        sensitivity=sensitivity,
        assumptions=assumptions,
        warnings=warnings,
    )


def _build_habit_monthly_series(habits: list[Habit], n_months: int) -> list[float]:
    """Monthly habit costs over the simulation horizon, with category creep."""
    from .habits import CATEGORY_CREEP_RATES
    current = {h.name: h.monthly_cost for h in habits}
    series = []
    for m in range(n_months):
        if m > 0 and m % 12 == 0:
            for h in habits:
                current[h.name] *= (1 + h.creep_rate)
        series.append(sum(current.values()))
    return series


def _build_income_monthly_series(traj: IncomeTrajectory, n_months: int) -> list[float]:
    """Monthly investable income over simulation horizon, interpolating yearly data."""
    series = []
    for m in range(n_months):
        yr = min(m // 12, len(traj.years) - 1)
        series.append(traj.years[yr].monthly_investable)
    return series


def _compute_sensitivity(
    inputs: SimulationInputs,
    income_traj: IncomeTrajectory,
    habit_proj: HabitProjection,
    sampler: ReturnSampler,
) -> list[SensitivityResult]:
    """
    Compute one-at-a-time sensitivity analysis.
    Each variable is perturbed by +10% and the change in P50 combined
    portfolio at final year is recorded.

    This tells the user: "which knob matters most for your outcome?"
    """
    results = []

    def base_p50() -> float:
        rng = np.random.default_rng(99)
        habit_series = _build_habit_monthly_series(
            inputs.habits, inputs.income_inputs.horizon_years * 12
        )
        income_series = _build_income_monthly_series(
            income_traj, inputs.income_inputs.horizon_years * 12
        )
        combined = [h + i for h, i in zip(habit_series, income_series)]
        tax_profile = TaxProfile.from_income(inputs.income_inputs.monthly_income * 12)
        record_years = [inputs.income_inputs.horizon_years]
        snaps = _run_paths(
            combined, sampler, inputs.allocation, tax_profile,
            inputs.allocation.equity, inputs.allocation.gold, inputs.allocation.fd,
            300, rng, record_years,
        )
        return float(np.median(snaps[inputs.income_inputs.horizon_years]))

    bp50 = base_p50()

    def sensitivity_for(variable: str, perturbed_inputs: SimulationInputs) -> SensitivityResult:
        from .income import project_income
        inc = project_income(perturbed_inputs.income_inputs, scenario=perturbed_inputs.scenario)
        hab = project_habits(
            perturbed_inputs.habits,
            perturbed_inputs.income_inputs.horizon_years,
            perturbed_inputs.cpi_rate,
        )
        rng = np.random.default_rng(99)
        habit_series = _build_habit_monthly_series(
            perturbed_inputs.habits, perturbed_inputs.income_inputs.horizon_years * 12
        )
        income_series = _build_income_monthly_series(
            inc, perturbed_inputs.income_inputs.horizon_years * 12
        )
        combined = [h + i for h, i in zip(habit_series, income_series)]
        tax_profile = TaxProfile.from_income(perturbed_inputs.income_inputs.monthly_income * 12)
        record_years = [perturbed_inputs.income_inputs.horizon_years]
        snaps = _run_paths(
            combined, sampler, perturbed_inputs.allocation, tax_profile,
            perturbed_inputs.allocation.equity, perturbed_inputs.allocation.gold,
            perturbed_inputs.allocation.fd, 300, rng, record_years,
        )
        pp50 = float(np.median(snaps[perturbed_inputs.income_inputs.horizon_years]))
        impact = (pp50 - bp50) / bp50 * 100 if bp50 > 0 else 0.0
        return SensitivityResult(
            variable=variable,
            base_p50=bp50,
            perturbed_p50=pp50,
            impact_pct=round(impact, 2),
            direction="positive" if impact > 0 else "negative",
        )

    # Perturb savings rate +10% (relative)
    from .income import IncomeInputs
    import copy, dataclasses

    # 1. Savings rate: proxy by increasing monthly income (more investable)
    perturbed_income = dataclasses.replace(
        inputs.income_inputs,
        monthly_income=inputs.income_inputs.monthly_income * 1.10
    )
    p_inputs_savings = dataclasses.replace(inputs, income_inputs=perturbed_income)
    results.append(sensitivity_for("savings_rate (+10%)", p_inputs_savings))

    # 2. Habit cost: +10% base cost
    perturbed_habits = [
        dataclasses.replace(h, cost_inr=h.cost_inr * 1.10)
        for h in inputs.habits
    ]
    p_inputs_habits = dataclasses.replace(inputs, habits=perturbed_habits)
    results.append(sensitivity_for("habit_cost (+10%)", p_inputs_habits))

    # 3. CPI: +1pp (e.g. 6% -> 7%)
    p_inputs_cpi = dataclasses.replace(inputs, cpi_rate=min(inputs.cpi_rate + 0.01, 0.12))
    results.append(sensitivity_for("inflation (+1pp)", p_inputs_cpi))

    # 4. Time horizon: +5 years
    p_income_horizon = dataclasses.replace(
        inputs.income_inputs,
        horizon_years=inputs.income_inputs.horizon_years + 5
    )
    p_inputs_horizon = dataclasses.replace(inputs, income_inputs=p_income_horizon)
    results.append(sensitivity_for("horizon (+5yr)", p_inputs_horizon))

    return results
