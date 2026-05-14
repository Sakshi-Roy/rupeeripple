import { useState, useEffect } from 'react';
import type { FormState, AllScenarios, Scenario, Sector, Allocation } from './types';
import { fetchSectors, fetchAllocations, runAllScenarios, narrateResults } from './api';
import InputPanel from './components/InputPanel';
import ResultsPanel from './components/ResultsPanel';
import TrajectoryChart from './components/TrajectoryChart';

const DEFAULT_FORM: FormState = {
  income: {
    monthly_income: 80000,
    current_age: 28,
    sector_id: 'it_software',
    performance: 'average',
    horizon_years: 20,
  },
  habits: [
    { id: '1', name: 'Daily coffee', cost_inr: 150, frequency: 'daily', categoryKey: 'coffee_chai' },
    { id: '2', name: 'Weekend dining', cost_inr: 1500, frequency: 'weekly', categoryKey: 'food_restaurant' },
    { id: '3', name: 'OTT subscriptions', cost_inr: 800, frequency: 'monthly', categoryKey: 'entertainment' },
  ],
  allocation_preset: 'balanced',
  custom_equity: 60,
  custom_gold: 30,
  custom_fd: 10,
  cpi_rate: 0.06,
  n_simulations: 500,
};

export default function App() {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [allocations, setAllocations] = useState<Allocation[]>([]);
  const [results, setResults] = useState<AllScenarios | null>(null);
  const [activeScenario, setActiveScenario] = useState<Scenario>('base');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [insight, setInsight] = useState<string | null>(null);

  useEffect(() => {
    fetchSectors().then(setSectors).catch(() => {});
    fetchAllocations().then(setAllocations).catch(() => {});
  }, []);

  async function handleSubmit() {
    setLoading(true);
    setError(null);
    setInsight(null);
    try {
      const res = await runAllScenarios(form);
      setResults(res);

      // Fire narration in background — doesn't block results display
      const base = res.base;
      const topSens = [...base.sensitivity].sort((a, b) => Math.abs(b.impact_pct) - Math.abs(a.impact_pct))[0];
      const toMonthly = (h: typeof form.habits[0]) =>
        h.frequency === 'daily' ? h.cost_inr * 30.44
        : h.frequency === 'weekly' ? h.cost_inr * 4.33
        : h.cost_inr;
      const topHabits = [...form.habits]
        .sort((a, b) => toMonthly(b) - toMonthly(a))
        .slice(0, 3)
        .map(h => ({ name: h.name, monthly_cost_inr: toMonthly(h) }));

      narrateResults({
        current_age: form.income.current_age,
        horizon_years: form.income.horizon_years,
        monthly_income: form.income.monthly_income,
        top_habits: topHabits,
        opportunity_cost_p50_inr: base.opportunity_cost.p50,
        combined_portfolio_p50_inr: base.combined_portfolio.p50,
        top_sensitivity_variable: topSens?.variable ?? '',
        top_sensitivity_impact_pct: topSens?.impact_pct ?? 0,
      }).then(text => { if (text) setInsight(text); });

    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const activeResult = results?.[activeScenario] ?? null;

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <header style={{ background: '#fff', borderBottom: '1px solid #e2e8f0', padding: '16px 24px' }}>
        <div style={{ maxWidth: 1400, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#0f172a' }}>True Cost Engine</h1>
            <p style={{ margin: 0, fontSize: 13, color: '#64748b', marginTop: 2 }}>
              What is your daily habit really costing you over time?
            </p>
          </div>
          <div style={{ fontSize: 12, color: '#94a3b8', textAlign: 'right', maxWidth: 280 }}>
            Monte Carlo simulation &middot; India tax regime (July 2024) &middot; P10/P50/P90 bands
          </div>
        </div>
      </header>

      <div style={{
        maxWidth: 1400, margin: '0 auto', padding: '20px 16px',
        display: 'grid', gridTemplateColumns: 'minmax(0, 380px) 1fr',
        gap: 20, alignItems: 'start',
      }}>
        <div>
          <InputPanel
            form={form} sectors={sectors} allocations={allocations}
            onChange={setForm} onSubmit={handleSubmit} loading={loading}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: 8, padding: '10px 14px', fontSize: 12, color: '#92400e' }}>
            <strong>Model assumptions:</strong> No major life events (marriage, home loan, illness) are modelled.
            Pre-tax returns on small portfolios may differ. All figures are probabilistic ranges — not predictions.
          </div>

          {error && (
            <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#dc2626' }}>
              {error}
            </div>
          )}

          {!results && !loading && (
            <div style={{ textAlign: 'center', padding: '60px 0', color: '#94a3b8' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>📊</div>
              <p style={{ fontSize: 14 }}>Fill in your details and click <strong>Run Simulation</strong></p>
            </div>
          )}

          {loading && (
            <div style={{ textAlign: 'center', padding: '60px 0', color: '#64748b' }}>
              <div style={{ fontSize: 14, marginBottom: 8 }}>Running 1,500 Monte Carlo paths across 3 scenarios…</div>
              <div style={{ width: 200, height: 4, background: '#e2e8f0', borderRadius: 2, margin: '0 auto', overflow: 'hidden' }}>
                <div style={{ height: '100%', background: '#3b82f6', borderRadius: 2, width: '60%' }} />
              </div>
            </div>
          )}

          {results && !loading && (
            <>
              {insight && (
                <div style={{
                  background: 'linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%)',
                  border: '1px solid #bfdbfe', borderRadius: 10,
                  padding: '14px 18px', display: 'flex', gap: 12, alignItems: 'flex-start',
                }}>
                  <span style={{ fontSize: 22, lineHeight: 1 }}>🤖</span>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#1d4ed8', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 4 }}>
                      AI Insight
                    </div>
                    <p style={{ margin: 0, fontSize: 13, color: '#1e293b', lineHeight: 1.65 }}>{insight}</p>
                  </div>
                </div>
              )}
              <ResultsPanel
                results={results}
                activeScenario={activeScenario}
                onScenarioChange={setActiveScenario}
              />
              {activeResult && (
                <TrajectoryChart result={activeResult} scenario={activeScenario} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
