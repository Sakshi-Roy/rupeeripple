"""
engine/returns.py

Market return engine for the True Cost Simulator.

Design philosophy:
- Bootstrap sampling from historical return series rather than parametric assumptions.
  This preserves the actual autocorrelation structure, crash clustering, and
  regime behaviour observed in real data.
- When a real NSE data file is provided, it uses that. Falls back to the
  statistically-grounded synthetic series from data/generate_returns.py.
- Asset allocation mix is handled here — weighted portfolio returns per month.

Honest limitations documented:
- 25 years of Nifty data is a thin sample for estimating tail behaviour.
- Bootstrap assumes the future return distribution resembles the past.
  Structural breaks (e.g. India becoming a developed market) are not modelled.
- Correlation between assets is assumed stationary. In crises it is not.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass
from typing import Literal

DATA_DIR = Path(__file__).parent.parent / "data"
RETURNS_FILE = DATA_DIR / "market_returns.csv"


@dataclass(frozen=True)
class AssetAllocation:
    """
    Represents a portfolio allocation across three asset classes.
    Weights must sum to 1.0.
    """
    equity: float   # Nifty 50 / equity mutual funds
    gold: float     # Gold (MCX / sovereign gold bonds)
    fd: float       # Fixed deposits / debt funds

    def __post_init__(self):
        total = self.equity + self.gold + self.fd
        if not abs(total - 1.0) < 1e-6:
            raise ValueError(f"Asset weights must sum to 1.0, got {total:.4f}")
        for name, val in [("equity", self.equity), ("gold", self.gold), ("fd", self.fd)]:
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"{name} weight {val} out of [0,1]")


# Predefined allocations — matches what users would actually choose
ALLOCATIONS: dict[str, AssetAllocation] = {
    "equity_only":  AssetAllocation(equity=1.0,  gold=0.0,  fd=0.0),
    "gold_only":    AssetAllocation(equity=0.0,  gold=1.0,  fd=0.0),
    "fd_only":      AssetAllocation(equity=0.0,  gold=0.0,  fd=1.0),
    "balanced":     AssetAllocation(equity=0.6,  gold=0.3,  fd=0.1),
    "conservative": AssetAllocation(equity=0.3,  gold=0.2,  fd=0.5),
    "aggressive":   AssetAllocation(equity=0.8,  gold=0.1,  fd=0.1),
}


class ReturnSampler:
    """
    Bootstraps monthly portfolio returns from historical data.

    Bootstrap approach:
    - Samples blocks of consecutive months (block bootstrap) rather than
      individual months. This preserves short-term autocorrelation and
      crash clustering (crashes last multiple months, not one month).
    - Block length: 6 months. Long enough to capture crash episodes,
      short enough to not over-constrain the simulation.
    """

    BLOCK_SIZE = 6  # months — captures crash clustering

    def __init__(self):
        self._returns_df = self._load_returns()
        self._n_months = len(self._returns_df)
        self._validate()

    def _load_returns(self) -> pd.DataFrame:
        if not RETURNS_FILE.exists():
            # Auto-generate if not present
            import sys
            sys.path.insert(0, str(DATA_DIR))
            from generate_returns import save_reference_series
            save_reference_series(str(RETURNS_FILE))

        df = pd.read_csv(RETURNS_FILE, parse_dates=["date"])
        required = {"nifty_monthly_return", "gold_monthly_return", "fd_monthly_return"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Returns file missing columns: {missing}")
        return df.reset_index(drop=True)

    def _validate(self):
        nifty = self._returns_df["nifty_monthly_return"].values
        ann_mean = nifty.mean() * 12
        ann_std = nifty.std() * np.sqrt(12)
        # Sanity check: Nifty should be between 8% and 18% annualised mean
        assert 0.08 <= ann_mean <= 0.18, (
            f"Nifty annualised mean {ann_mean:.2%} outside expected range. "
            "Check your return data."
        )
        assert 0.15 <= ann_std <= 0.30, (
            f"Nifty annualised std {ann_std:.2%} outside expected range."
        )

    def sample_portfolio_returns(
        self,
        allocation: AssetAllocation,
        n_months: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """
        Returns array of n_months monthly portfolio returns via block bootstrap.

        Each return is the weighted sum of asset returns for that month,
        preserving cross-asset correlations within each sampled block.
        """
        nifty_col = self._returns_df["nifty_monthly_return"].values
        gold_col = self._returns_df["gold_monthly_return"].values
        fd_col = self._returns_df["fd_monthly_return"].values

        # Max valid block start index
        max_start = self._n_months - self.BLOCK_SIZE

        portfolio_returns = np.empty(n_months)
        filled = 0

        while filled < n_months:
            # Sample a random block start
            start = rng.integers(0, max_start + 1)
            block_end = min(start + self.BLOCK_SIZE, self._n_months)
            block_len = block_end - start
            remaining = n_months - filled
            take = min(block_len, remaining)

            nifty_block = nifty_col[start:start + take]
            gold_block = gold_col[start:start + take]
            fd_block = fd_col[start:start + take]

            portfolio_returns[filled:filled + take] = (
                allocation.equity * nifty_block
                + allocation.gold * gold_block
                + allocation.fd * fd_block
            )
            filled += take

        return portfolio_returns

    def get_empirical_stats(self, allocation: AssetAllocation) -> dict:
        """
        Returns empirical statistics for a given allocation.
        Used to display honest model assumptions to users.
        """
        nifty = self._returns_df["nifty_monthly_return"].values
        gold = self._returns_df["gold_monthly_return"].values
        fd = self._returns_df["fd_monthly_return"].values

        portfolio = (
            allocation.equity * nifty
            + allocation.gold * gold
            + allocation.fd * fd
        )

        ann_mean = portfolio.mean() * 12
        ann_std = portfolio.std() * np.sqrt(12)

        return {
            "annualised_mean_return": round(ann_mean, 4),
            "annualised_std_dev": round(ann_std, 4),
            "worst_month": round(float(portfolio.min()), 4),
            "best_month": round(float(portfolio.max()), 4),
            "data_months": self._n_months,
            "note": (
                "Bootstrap from historical data. Past distribution does not "
                "guarantee future distribution. Thin sample (25yr) limits "
                "reliability of tail estimates."
            ),
        }


# Module-level singleton — loaded once, reused across simulations
_sampler: ReturnSampler | None = None


def get_sampler() -> ReturnSampler:
    global _sampler
    if _sampler is None:
        _sampler = ReturnSampler()
    return _sampler
