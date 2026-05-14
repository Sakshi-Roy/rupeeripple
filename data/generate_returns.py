"""
data/generate_returns.py

Generates a statistically-grounded synthetic monthly return series when
real NSE/MCX data is not available.

Targets (validated by returns.py):
  - Nifty: annualised mean 8-18%, annualised std 15-30%
  - Gold:  annualised mean ~10%, annualised std ~15%
  - FD:    annualised mean ~7%, annualised std ~0.5%

We standardise after sampling so the sample statistics *exactly* match
the targets, making the validation in ReturnSampler deterministic.
"""

import numpy as np
import pandas as pd
from pathlib import Path


def save_reference_series(
    output_path: str,
    n_months: int = 300,
    seed: int = 2024,
) -> None:
    rng = np.random.default_rng(seed)

    # --- Target monthly statistics ---
    nifty_mean = 0.0110   # 13.2 % / yr
    nifty_std  = 0.0577   # 20.0 % / yr  (std/sqrt(12))

    gold_mean  = 0.0083   # 10.0 % / yr
    gold_std   = 0.0433   # 15.0 % / yr

    fd_mean    = 0.0058   #  7.0 % / yr
    fd_std     = 0.0014   #  0.5 % / yr

    # Correlated multivariate normal (equity-gold ~0.1, equity-FD ~-0.05)
    corr = np.array([
        [1.00,  0.10, -0.05],
        [0.10,  1.00,  0.00],
        [-0.05, 0.00,  1.00],
    ])
    stds = np.array([nifty_std, gold_std, fd_std])
    cov  = np.outer(stds, stds) * corr

    raw = rng.multivariate_normal(
        [0.0, 0.0, 0.0], cov, size=n_months
    )

    # Standardise each column then rescale to exact target mean/std
    def rescale(col: np.ndarray, mean: float, std: float) -> np.ndarray:
        z = (col - col.mean()) / col.std()
        return z * std + mean

    nifty = rescale(raw[:, 0], nifty_mean, nifty_std)
    gold  = rescale(raw[:, 1], gold_mean,  gold_std)
    fd    = rescale(raw[:, 2], fd_mean,    fd_std)

    # FD cannot be negative in practice; clip to a floor of 0.3 % / month
    fd = np.clip(fd, 0.003, 0.012)

    dates = pd.date_range("2000-01-01", periods=n_months, freq="MS")
    df = pd.DataFrame({
        "date": dates,
        "nifty_monthly_return": np.round(nifty, 6),
        "gold_monthly_return":  np.round(gold,  6),
        "fd_monthly_return":    np.round(fd,     6),
    })
    df.to_csv(output_path, index=False)
    print(f"[generate_returns] Saved {n_months} months to {output_path}")


if __name__ == "__main__":
    out = Path(__file__).parent / "market_returns.csv"
    save_reference_series(str(out))
