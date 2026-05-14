import type { FormState, SimulationResponse, Scenario, Sector, Allocation, HabitInput } from './types';
import { CATEGORY_BY_KEY } from './constants';

const BASE = import.meta.env.VITE_API_URL ?? '/api';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchSectors(): Promise<Sector[]> {
  const res = await fetch(`${BASE}/sectors`);
  const data = await handleResponse<{ sectors: Sector[] }>(res);
  return data.sectors;
}

export async function fetchAllocations(): Promise<Allocation[]> {
  const res = await fetch(`${BASE}/allocations`);
  const data = await handleResponse<{ allocations: Allocation[] }>(res);
  return data.allocations;
}

export interface ParsedHabitsResponse {
  habits: Omit<HabitInput, 'id'>[];
  unparsed: string;
}

export async function parseHabitsFromText(text: string): Promise<ParsedHabitsResponse> {
  const res = await fetch(`${BASE}/parse-habits`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  return handleResponse<ParsedHabitsResponse>(res);
}

function buildPayload(form: FormState, scenario: Scenario) {
  // Map frontend categoryKey → engine category string
  const habits = form.habits.map(({ name, cost_inr, frequency, categoryKey }) => ({
    name,
    cost_inr,
    frequency,
    category: CATEGORY_BY_KEY[categoryKey]?.engineCategory ?? 'general',
  }));

  // Allocation: preset or custom weights (0–100 → 0.0–1.0)
  const allocation =
    form.allocation_preset === 'custom'
      ? {
          equity: form.custom_equity / 100,
          gold: form.custom_gold / 100,
          fd: form.custom_fd / 100,
        }
      : { preset: form.allocation_preset };

  return {
    income_inputs: {
      monthly_income: form.income.monthly_income,
      current_age: form.income.current_age,
      sector_id: form.income.sector_id,
      performance: form.income.performance,
      horizon_years: form.income.horizon_years,
    },
    habits,
    allocation,
    cpi_rate: form.cpi_rate,
    n_simulations: form.n_simulations,
    scenario,
  };
}

export async function runSimulation(
  form: FormState,
  scenario: Scenario,
): Promise<SimulationResponse> {
  const res = await fetch(`${BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildPayload(form, scenario)),
  });
  return handleResponse<SimulationResponse>(res);
}

export interface NarratePayload {
  current_age: number;
  horizon_years: number;
  monthly_income: number;
  top_habits: { name: string; monthly_cost_inr: number }[];
  opportunity_cost_p50_inr: number;
  combined_portfolio_p50_inr: number;
  top_sensitivity_variable: string;
  top_sensitivity_impact_pct: number;
}

export async function narrateResults(payload: NarratePayload): Promise<string> {
  const res = await fetch(`${BASE}/narrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return '';
  const data = await res.json();
  return data.insight ?? '';
}

export async function runAllScenarios(
  form: FormState,
): Promise<Record<Scenario, SimulationResponse>> {
  const [conservative, base, optimistic] = await Promise.all([
    runSimulation(form, 'conservative'),
    runSimulation(form, 'base'),
    runSimulation(form, 'optimistic'),
  ]);
  return { conservative, base, optimistic };
}
