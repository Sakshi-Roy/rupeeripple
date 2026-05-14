"""
api/models.py — Pydantic v2 request/response models.

These mirror the engine's dataclasses but are decoupled so the API
layer can evolve independently without touching the engine.
"""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, field_validator, model_validator


class HabitRequest(BaseModel):
    name: str
    cost_inr: float
    frequency: Literal["daily", "weekly", "monthly"]
    category: str = "general"

    @field_validator("cost_inr")
    @classmethod
    def cost_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("cost_inr must be >= 0")
        return v


class IncomeInputsRequest(BaseModel):
    monthly_income: float
    current_age: int
    sector_id: str
    performance: Literal[
        "below_average", "average", "above_average", "top_performer"
    ] = "average"
    horizon_years: int = 20

    @field_validator("monthly_income")
    @classmethod
    def income_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("monthly_income must be > 0")
        return v

    @field_validator("current_age")
    @classmethod
    def age_range(cls, v: int) -> int:
        if not 18 <= v <= 70:
            raise ValueError("current_age must be between 18 and 70")
        return v

    @field_validator("horizon_years")
    @classmethod
    def horizon_range(cls, v: int) -> int:
        if not 1 <= v <= 40:
            raise ValueError("horizon_years must be between 1 and 40")
        return v


class AllocationRequest(BaseModel):
    """Either use a named preset (e.g. 'balanced') or supply custom weights."""
    preset: Optional[str] = None
    equity: Optional[float] = None
    gold: Optional[float] = None
    fd: Optional[float] = None

    @model_validator(mode="after")
    def check_one_path(self) -> "AllocationRequest":
        has_preset = self.preset is not None
        has_custom = any(x is not None for x in [self.equity, self.gold, self.fd])
        if not has_preset and not has_custom:
            raise ValueError("Provide either 'preset' or custom equity/gold/fd weights.")
        return self


class ParseHabitsRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty")
        if len(v) > 2000:
            raise ValueError("text must be under 2000 characters")
        return v.strip()


class HabitSummaryItem(BaseModel):
    name: str
    monthly_cost_inr: float


class NarrateRequest(BaseModel):
    current_age: int
    horizon_years: int
    monthly_income: float
    top_habits: list[HabitSummaryItem]
    opportunity_cost_p50_inr: float
    combined_portfolio_p50_inr: float
    top_sensitivity_variable: str
    top_sensitivity_impact_pct: float


class SimulateRequest(BaseModel):
    income_inputs: IncomeInputsRequest
    habits: list[HabitRequest]
    allocation: AllocationRequest
    cpi_rate: float = 0.06
    n_simulations: int = 500
    scenario: Literal["conservative", "base", "optimistic"] = "base"

    @field_validator("cpi_rate")
    @classmethod
    def cpi_range(cls, v: float) -> float:
        if not 0.02 <= v <= 0.12:
            raise ValueError("cpi_rate must be between 0.02 and 0.12")
        return v

    @field_validator("n_simulations")
    @classmethod
    def sims_min(cls, v: int) -> int:
        if v < 100:
            raise ValueError("n_simulations must be >= 100")
        return v

    @field_validator("habits")
    @classmethod
    def at_least_one_habit(cls, v: list) -> list:
        if not v:
            raise ValueError("At least one habit is required.")
        return v
