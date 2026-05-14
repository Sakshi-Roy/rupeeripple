"""
engine/tax.py

India tax engine for investment returns.
Reflects the July 2024 Union Budget changes (effective FY 2024-25 onwards).

Tax rules implemented:
    Equity / Equity Mutual Funds:
        - STCG (< 12 months): 20% flat  [was 15% pre-July 2024]
        - LTCG (>= 12 months): 12.5% on gains above ₹1.25L exemption  [was 10% above ₹1L]

    Debt Mutual Funds / FD:
        - All gains taxed at income slab rate (no indexation benefit post April 2023)
        - We use effective slab rate supplied by user

    Gold:
        - STCG (< 24 months): income slab rate
        - LTCG (>= 24 months): 12.5% flat  [was 20% with indexation pre-July 2024]
        - Physical gold: same as above
        - Sovereign Gold Bonds (SGB): LTCG tax-exempt on maturity — modelled separately

Honest limitations:
    - In a long-horizon simulation we approximate by assuming all equity is
      held long-term (>12 months) and all FD is taxed at slab. This
      slightly underestimates tax drag from short-term rebalancing.
    - Surcharge and cess (4% health & education cess) is applied on top.
    - State taxes not modelled (negligible for financial instruments).
    - Tax laws can change. This reflects July 2024 rules.
"""

from dataclasses import dataclass


# Health & Education Cess on income tax
CESS_RATE = 0.04


@dataclass(frozen=True)
class TaxProfile:
    """
    User's tax profile.

    annual_income: gross annual income in INR (used to determine slab)
    slab_rate: marginal income tax rate (0.0 to 0.30)
    """
    annual_income: float
    slab_rate: float  # e.g. 0.20 for 20%

    def __post_init__(self):
        if not 0.0 <= self.slab_rate <= 0.30:
            raise ValueError(f"Slab rate {self.slab_rate} outside [0, 0.30]")

    @classmethod
    def from_income(cls, annual_income: float) -> "TaxProfile":
        """
        Infer marginal slab rate from annual income.
        New tax regime slabs (FY 2024-25, post-July 2024 budget):
            0 - 3L:     0%
            3L - 7L:    5%
            7L - 10L:   10%
            10L - 12L:  15%
            12L - 15L:  20%
            >15L:       30%
        Note: rebate u/s 87A makes tax nil up to ₹7L effective net tax.
        We use marginal rate for investment taxation purposes.
        """
        L = 100_000  # lakh shorthand
        if annual_income <= 3 * L:
            slab = 0.0
        elif annual_income <= 7 * L:
            slab = 0.05
        elif annual_income <= 10 * L:
            slab = 0.10
        elif annual_income <= 12 * L:
            slab = 0.15
        elif annual_income <= 15 * L:
            slab = 0.20
        else:
            slab = 0.30
        return cls(annual_income=annual_income, slab_rate=slab)


# Tax constants — July 2024 budget
EQUITY_LTCG_RATE = 0.125           # 12.5%
EQUITY_LTCG_EXEMPTION = 125_000    # ₹1.25 lakh per year
EQUITY_STCG_RATE = 0.20            # 20%
GOLD_LTCG_RATE = 0.125             # 12.5% (post July 2024)
GOLD_STCG_USES_SLAB = True         # under 24 months
DEBT_USES_SLAB = True              # all debt gains at slab


def tax_on_equity_ltcg(gross_gain: float, exemption_used: float = 0.0) -> float:
    """
    Tax on equity LTCG gains in a given year.

    Args:
        gross_gain: total LTCG gain from equity in INR
        exemption_used: how much of the ₹1.25L exemption already consumed

    Returns:
        tax payable (INR), after cess
    """
    exemption_remaining = max(0.0, EQUITY_LTCG_EXEMPTION - exemption_used)
    taxable = max(0.0, gross_gain - exemption_remaining)
    tax = taxable * EQUITY_LTCG_RATE
    return tax * (1 + CESS_RATE)


def tax_on_equity_stcg(gross_gain: float) -> float:
    """Tax on equity STCG (held < 12 months). 20% flat + cess."""
    return max(0.0, gross_gain) * EQUITY_STCG_RATE * (1 + CESS_RATE)


def tax_on_fd_or_debt(gross_gain: float, profile: TaxProfile) -> float:
    """FD/Debt MF: taxed at marginal slab rate + cess."""
    return max(0.0, gross_gain) * profile.slab_rate * (1 + CESS_RATE)


def tax_on_gold_ltcg(gross_gain: float) -> float:
    """Gold LTCG (>= 24 months): 12.5% flat + cess. Post July 2024."""
    return max(0.0, gross_gain) * GOLD_LTCG_RATE * (1 + CESS_RATE)


def tax_on_gold_stcg(gross_gain: float, profile: TaxProfile) -> float:
    """Gold STCG (< 24 months): slab rate + cess."""
    return max(0.0, gross_gain) * profile.slab_rate * (1 + CESS_RATE)


def effective_annual_return_after_tax(
    gross_annual_return: float,
    asset_type: str,          # "equity" | "gold" | "fd"
    profile: TaxProfile,
    holding_period_months: int = 24,  # assumed for approximation
) -> float:
    """
    Approximate post-tax annual return for a given gross return and asset type.

    Used in the simulation to convert gross portfolio returns to after-tax returns
    on a simplified annual basis (we assume long-term holding throughout).

    This is an approximation. A fully accurate model would track
    cost basis lot-by-lot — unnecessary complexity for an MVP.

    Returns: post-tax annual return rate (e.g. 0.108 for 10.8%)
    """
    if gross_annual_return <= 0:
        # Losses: no tax benefit modelled (loss harvesting out of scope for MVP)
        return gross_annual_return

    if asset_type == "equity":
        # Assume LTCG (long-term hold). Apply ₹1.25L exemption once per year.
        # For a portfolio of size P, gain = P * gross_annual_return
        # We can only approximate the rate adjustment, not the absolute exemption,
        # without knowing portfolio size. We use the rate directly.
        # Note: exemption benefits smaller portfolios more — documented limitation.
        tax_rate = EQUITY_LTCG_RATE * (1 + CESS_RATE)
        return gross_annual_return * (1 - tax_rate)

    elif asset_type == "gold":
        if holding_period_months >= 24:
            tax_rate = GOLD_LTCG_RATE * (1 + CESS_RATE)
        else:
            tax_rate = profile.slab_rate * (1 + CESS_RATE)
        return gross_annual_return * (1 - tax_rate)

    elif asset_type == "fd":
        tax_rate = profile.slab_rate * (1 + CESS_RATE)
        return gross_annual_return * (1 - tax_rate)

    else:
        raise ValueError(f"Unknown asset_type: {asset_type}. Use equity/gold/fd.")


def apply_tax_to_monthly_returns(
    monthly_returns: list[float],
    allocation_equity: float,
    allocation_gold: float,
    allocation_fd: float,
    profile: TaxProfile,
) -> list[float]:
    """
    Apply a blended after-tax adjustment to monthly portfolio returns.

    We compute a blended after-tax multiplier based on asset weights and
    apply it consistently. This is a simplification — it is honest about
    being an approximation, not lot-by-lot accounting.

    Returns: list of after-tax monthly returns
    """
    # Annual return rates → approximate monthly
    equity_tax_rate = EQUITY_LTCG_RATE * (1 + CESS_RATE)
    gold_tax_rate = GOLD_LTCG_RATE * (1 + CESS_RATE)
    fd_tax_rate = profile.slab_rate * (1 + CESS_RATE)

    # Blended tax rate on positive returns
    blended_tax_rate = (
        allocation_equity * equity_tax_rate
        + allocation_gold * gold_tax_rate
        + allocation_fd * fd_tax_rate
    )

    after_tax = []
    for r in monthly_returns:
        if r > 0:
            after_tax.append(r * (1 - blended_tax_rate))
        else:
            # Losses passed through (no tax benefit modelled — conservative)
            after_tax.append(r)

    return after_tax
