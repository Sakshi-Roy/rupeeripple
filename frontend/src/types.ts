export type Scenario = 'conservative' | 'base' | 'optimistic';
export type Frequency = 'daily' | 'weekly' | 'monthly';
export type Performance = 'below_average' | 'average' | 'above_average' | 'top_performer';

export interface HabitInput {
  id: string;
  name: string;
  cost_inr: number;
  frequency: Frequency;
  /** Key from CATEGORY_OPTIONS (e.g. 'commute', 'cloud_saas'). Mapped to engine category in api.ts. */
  categoryKey: string;
}

export interface IncomeInputs {
  monthly_income: number;
  current_age: number;
  sector_id: string;
  performance: Performance;
  horizon_years: number;
}

export interface FormState {
  income: IncomeInputs;
  habits: HabitInput[];
  /** Preset name from ALLOCATIONS, or 'custom' for manual weights */
  allocation_preset: string;
  /** Used only when allocation_preset === 'custom'. Values are 0–100 (percent). */
  custom_equity: number;
  custom_gold: number;
  custom_fd: number;
  cpi_rate: number;
  n_simulations: number;
}

export interface PercentileResult {
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
}

export interface YearlyData {
  year: number;
  income_monthly: number;
  habit_cost_nominal: number;
  opportunity_cost: PercentileResult;
  income_portfolio: PercentileResult;
  combined_portfolio: PercentileResult;
}

export interface SensitivityItem {
  variable: string;
  impact_pct: number;
  direction: string;
}

export interface SimulationResponse {
  scenario: string;
  horizon_years: number;
  final_monthly_income: number;
  total_habit_cost_nominal: number;
  total_habit_cost_real: number;
  opportunity_cost: PercentileResult;
  income_portfolio: PercentileResult;
  combined_portfolio: PercentileResult;
  combined_portfolio_real: PercentileResult;
  sensitivity: SensitivityItem[];
  warnings: string[];
  yearly: YearlyData[];
  assumptions: {
    simulation_paths: number;
    return_method: string;
    tax_regime: string;
    income_model: Record<string, unknown>;
    habit_model: Record<string, unknown>;
    return_stats: Record<string, unknown>;
    known_limitations: string[];
  };
}

export type AllScenarios = Record<Scenario, SimulationResponse>;

export interface Sector {
  id: string;
  name: string;
  mean_increment_pct: number;
  source: string;
}

export interface Allocation {
  id: string;
  equity: number;
  gold: number;
  fd: number;
}
