import { useState } from 'react';
import type { AllScenarios, Scenario, SimulationResponse, PercentileResult } from '../types';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList,
} from 'recharts';

// ── Constants ────────────────────────────────────────────────────────────────

const SCENARIO_LABELS: Record<Scenario, string> = {
  conservative: 'Conservative',
  base: 'Base',
  optimistic: 'Optimistic',
};

const SCENARIO_COLORS: Record<Scenario, string> = {
  conservative: '#f97316',
  base: '#3b82f6',
  optimistic: '#22c55e',
};

// ── Formatters ───────────────────────────────────────────────────────────────

function fmt(n: number, short = false): string {
  if (n >= 10_000_000) return `₹${(n / 10_000_000).toFixed(short ? 0 : 1)} Cr`;
  if (n >= 100_000)    return `₹${(n / 100_000).toFixed(short ? 0 : 1)} L`;
  return `₹${Math.round(n).toLocaleString('en-IN')}`;
}

function fmtMo(n: number): string {
  return `₹${Math.round(n).toLocaleString('en-IN')}/mo`;
}

// ── Sensitivity variable plain-English explanations ──────────────────────────

function sensitivityExplanation(variable: string, impactPct: number): string {
  const abs = Math.abs(impactPct).toFixed(1);
  if (variable.includes('horizon')) {
    return `Investing for ${abs}% more time has an outsized compounding effect. The longer you stay invested, the more markets work for you — this is the single biggest lever.`;
  }
  if (variable.includes('savings_rate')) {
    return `Saving ${abs}% more of your income each month directly adds to what gets invested. More money in → more money out.`;
  }
  if (variable.includes('habit_cost')) {
    return `Your habit spending redirected to investments makes a ${abs}% difference to the final number. It matters — but less than how long you invest or how much you save from income.`;
  }
  if (variable.includes('inflation')) {
    return `Higher inflation (${abs}% impact) erodes the real value of your portfolio. Equity returns historically outpace inflation, but it still shrinks your purchasing power.`;
  }
  return `${variable} changes your final portfolio by ${abs}%.`;
}

// ── Simple (layman) view ─────────────────────────────────────────────────────

function SimpleView({ result, scenario }: { result: SimulationResponse; scenario: Scenario }) {
  const color = SCENARIO_COLORS[scenario];
  const cp = result.combined_portfolio;
  const cpReal = result.combined_portfolio_real;
  const opp = result.opportunity_cost;
  const yr = result.horizon_years;

  // Sorted sensitivity — top item is the most impactful
  const sorted = [...result.sensitivity].sort((a, b) => Math.abs(b.impact_pct) - Math.abs(a.impact_pct));
  const top = sorted[0];
  const bottom = sorted[sorted.length - 1];
  const ratio = bottom && Math.abs(bottom.impact_pct) > 0.1
    ? Math.round(Math.abs(top.impact_pct) / Math.abs(bottom.impact_pct))
    : null;

  const blockStyle: React.CSSProperties = {
    background: '#f8fafc', borderRadius: 8, padding: '12px 14px', marginBottom: 10,
    border: '1px solid #e2e8f0',
  };
  const headStyle: React.CSSProperties = {
    fontSize: 12, fontWeight: 700, color: '#475569',
    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6,
  };
  const bigNum: React.CSSProperties = {
    fontSize: 22, fontWeight: 700, color, display: 'block',
  };
  const sub: React.CSSProperties = { fontSize: 12, color: '#64748b', marginTop: 2 };

  return (
    <div>
      {/* What your habits cost */}
      <div style={blockStyle}>
        <div style={headStyle}>What your habits cost you</div>
        <p style={{ fontSize: 13, color: '#334155', margin: 0, lineHeight: 1.6 }}>
          You currently spend{' '}
          <strong>{fmtMo(result.total_habit_cost_nominal / (yr * 12))}</strong> on habits.
          Over <strong>{yr} years</strong>, that adds up to{' '}
          <strong style={{ color: '#dc2626' }}>{fmt(result.total_habit_cost_nominal)}</strong> in future money —
          or <strong>{fmt(result.total_habit_cost_real)}</strong> in today's purchasing power
          (after accounting for {Math.round(100 * ((result.assumptions.income_model as {effective_rate_pct?: number})?.effective_rate_pct ?? 0.06))}% inflation).
        </p>
      </div>

      {/* If you invested that habit money */}
      <div style={blockStyle}>
        <div style={headStyle}>If you invested your habit money instead</div>
        <p style={{ fontSize: 13, color: '#334155', margin: '0 0 10px', lineHeight: 1.6 }}>
          Redirecting your habit spending to a diversified portfolio over {yr} years:
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, textAlign: 'center' }}>
          {[
            { label: 'Worst 10% of markets', val: opp.p10, note: 'P10 — unlucky scenario' },
            { label: 'Most likely outcome', val: opp.p50, note: 'P50 — median scenario' },
            { label: 'Best 10% of markets', val: opp.p90, note: 'P90 — lucky scenario' },
          ].map(({ label, val, note }) => (
            <div key={note} style={{ background: '#fff', borderRadius: 6, padding: 10, border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{label}</div>
              <div style={{ fontSize: 16, fontWeight: 700, color }}>{fmt(val, true)}</div>
              <div style={{ fontSize: 10, color: '#94a3b8' }}>{note}</div>
            </div>
          ))}
        </div>
        <p style={{ fontSize: 12, color: '#64748b', marginTop: 8, lineHeight: 1.5 }}>
          The wide gap between worst and best isn't uncertainty we can avoid — it reflects how markets genuinely behave over {yr} years.
          The middle number (P50) is the most realistic single estimate.
        </p>
      </div>

      {/* Combined picture */}
      <div style={blockStyle}>
        <div style={headStyle}>Your full picture (habits + income savings)</div>
        <p style={{ fontSize: 13, color: '#334155', margin: '0 0 10px', lineHeight: 1.6 }}>
          Adding your income savings rate to the habit savings, in <strong>{yr} years</strong>:
        </p>
        <div style={{ textAlign: 'center', marginBottom: 8 }}>
          <span style={bigNum}>{fmt(cp.p50)}</span>
          <span style={sub}>Most likely total portfolio (nominal / future rupees)</span>
        </div>
        <div style={{ textAlign: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 17, fontWeight: 700, color: '#64748b' }}>{fmt(cpReal.p50)}</span>
          <span style={sub}>Same amount in <em>today's</em> money (inflation-adjusted)</span>
        </div>
        <p style={{ fontSize: 12, color: '#64748b', marginTop: 6, lineHeight: 1.5 }}>
          Range: <strong>{fmt(cp.p10)}</strong> (bad markets) to <strong>{fmt(cp.p90)}</strong> (good markets).
          Your monthly income is projected to reach <strong>{fmtMo(result.final_monthly_income)}</strong> by year {yr}.
        </p>
      </div>

      {/* What matters most */}
      <div style={blockStyle}>
        <div style={headStyle}>The one thing that matters most</div>
        {top && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <div style={{ fontSize: 32 }}>
                {top.variable.includes('horizon') ? '⏳'
                  : top.variable.includes('savings') ? '💰'
                  : top.variable.includes('habit') ? '☕'
                  : '📈'}
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#0f172a' }}>
                  {top.variable.replace(/\(.*\)/, '').trim()}
                </div>
                {ratio && ratio > 2 && (
                  <div style={{ fontSize: 12, color: color, fontWeight: 600 }}>
                    {ratio}× more impactful than {bottom.variable.replace(/\(.*\)/, '').trim()}
                  </div>
                )}
              </div>
            </div>
            <p style={{ fontSize: 13, color: '#334155', margin: 0, lineHeight: 1.6 }}>
              {sensitivityExplanation(top.variable, top.impact_pct)}
            </p>
          </>
        )}
      </div>

      {/* Ranked list */}
      <div style={blockStyle}>
        <div style={headStyle}>All levers ranked by impact</div>
        {sorted.map((s, i) => {
          const abs = Math.abs(s.impact_pct);
          const maxAbs = Math.abs(sorted[0].impact_pct);
          return (
            <div key={s.variable} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                <span style={{ fontSize: 12, color: '#334155' }}>
                  {i + 1}. {s.variable.replace(/\(.*\)/, '').trim()}
                </span>
                <span style={{ fontSize: 12, fontWeight: 600, color: s.direction === 'positive' ? '#16a34a' : '#dc2626' }}>
                  {s.impact_pct > 0 ? '+' : ''}{s.impact_pct.toFixed(1)}%
                </span>
              </div>
              <div style={{ height: 6, background: '#f1f5f9', borderRadius: 3 }}>
                <div style={{
                  height: '100%', borderRadius: 3,
                  width: `${Math.min(100, (abs / maxAbs) * 100)}%`,
                  background: s.direction === 'positive' ? '#3b82f6' : '#ef4444',
                }} />
              </div>
            </div>
          );
        })}
        <p style={{ fontSize: 11, color: '#94a3b8', margin: '6px 0 0' }}>
          Each bar shows the % change in your final portfolio from a 10% change in that variable (or +5yr for time horizon, +1pp for inflation).
        </p>
      </div>

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: '10px 14px', fontSize: 12, color: '#92400e' }}>
          <strong>Heads up:</strong>
          <ul style={{ margin: '4px 0 0', paddingLeft: 16 }}>
            {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Technical (existing) view ────────────────────────────────────────────────

function MetricRow({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{ padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span style={{ fontSize: 12, color: '#64748b' }}>{label}</span>
        <span style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>{value}</span>
      </div>
      {sub && <div style={{ fontSize: 11, color: '#94a3b8', textAlign: 'right' }}>{sub}</div>}
    </div>
  );
}

function PBand({ label, data, color }: { label: string; data: PercentileResult; color: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 12, color: '#475569', marginBottom: 4, fontWeight: 500 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 11, color: '#94a3b8', minWidth: 24 }}>P10</span>
        <div style={{ flex: 1, position: 'relative', height: 24 }}>
          <div style={{ position: 'absolute', top: 4, bottom: 4, left: 0, right: 0, background: '#f1f5f9', borderRadius: 4 }} />
          <div style={{ position: 'absolute', top: 4, bottom: 4, left: '10%', right: '10%', background: color + '33', borderRadius: 4 }} />
          <div style={{ position: 'absolute', top: 6, bottom: 6, left: '49%', width: 3, background: color, borderRadius: 2 }} />
        </div>
        <span style={{ fontSize: 11, color: '#94a3b8', minWidth: 24 }}>P90</span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#64748b', marginTop: 2 }}>
        <span>{fmt(data.p10)}</span>
        <span style={{ fontWeight: 600, color: '#0f172a' }}>{fmt(data.p50)}</span>
        <span>{fmt(data.p90)}</span>
      </div>
    </div>
  );
}

function SensitivityChart({ result }: { result: SimulationResponse }) {
  const sorted = [...result.sensitivity].sort((a, b) => Math.abs(b.impact_pct) - Math.abs(a.impact_pct));
  const maxAbs = Math.max(...sorted.map(s => Math.abs(s.impact_pct)), 1);

  const top = sorted[0];
  const bottom = sorted[sorted.length - 1];
  const ratio = bottom && Math.abs(bottom.impact_pct) > 0.1
    ? Math.round(Math.abs(top.impact_pct) / Math.abs(bottom.impact_pct))
    : null;

  const chartData = sorted.map(s => ({
    name: s.variable.replace(/\(.*\)/, '').trim(),
    impact: Math.abs(s.impact_pct),
    direction: s.direction,
    raw: s.impact_pct,
  }));

  return (
    <div>
      {ratio !== null && ratio > 2 && (
        <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 6, padding: '8px 12px', fontSize: 12, color: '#1d4ed8', marginBottom: 12 }}>
          <strong>{top.variable.replace(/\(.*\)/, '').trim()}</strong> matters{' '}
          <strong>{ratio}× more</strong> than{' '}
          <strong>{bottom.variable.replace(/\(.*\)/, '').trim()}</strong> for your P50 outcome.
        </div>
      )}
      <ResponsiveContainer width="100%" height={sorted.length * 38 + 20}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 50, left: 10, bottom: 0 }}>
          <XAxis type="number" domain={[0, maxAbs * 1.15]} hide />
          <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11, fill: '#475569' }} />
          <Tooltip
            formatter={(_v, _n, props) => {
              const raw = (props.payload as { raw?: number })?.raw ?? 0;
              return [`${raw > 0 ? '+' : ''}${raw.toFixed(1)}% on P50`, 'Impact'];
            }}
            contentStyle={{ fontSize: 12 }}
          />
          <Bar dataKey="impact" radius={[0, 4, 4, 0]} barSize={18}>
            <LabelList
              dataKey="impact"
              position="right"
              formatter={(v: unknown) => typeof v === 'number' ? `${v.toFixed(1)}%` : ''}
              style={{ fontSize: 11, fill: '#475569' }}
            />
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.direction === 'positive' ? '#3b82f6' : '#ef4444'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p style={{ fontSize: 10, color: '#94a3b8', marginTop: 6 }}>
        Each variable perturbed by +10% (or +5yr for horizon, +1pp for inflation). Impact = % change in P50 combined portfolio.
      </p>
    </div>
  );
}

function AssumptionsPanel({ result }: { result: SimulationResponse }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: 12 }}>
      <button onClick={() => setOpen(o => !o)} style={{
        background: 'none', border: 'none', cursor: 'pointer',
        fontSize: 12, color: '#64748b', padding: 0,
        display: 'flex', alignItems: 'center', gap: 4,
      }}>
        {open ? '▾' : '▸'} Model assumptions & limitations
      </button>
      {open && (
        <div style={{ marginTop: 8, padding: 12, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 11, color: '#475569' }}>
          <div style={{ marginBottom: 8 }}><strong>Return model:</strong> {result.assumptions.return_method}</div>
          <div style={{ marginBottom: 8 }}><strong>Tax:</strong> {result.assumptions.tax_regime}</div>
          <div style={{ marginBottom: 4 }}><strong>Known limitations:</strong></div>
          <ul style={{ margin: 0, paddingLeft: 16 }}>
            {result.assumptions.known_limitations.map((l, i) => <li key={i} style={{ marginBottom: 3 }}>{l}</li>)}
          </ul>
          {result.warnings.length > 0 && (
            <div style={{ marginTop: 10, padding: '8px 10px', background: '#fff7ed', borderRadius: 6, color: '#92400e' }}>
              <strong>Warnings:</strong>
              <ul style={{ margin: '4px 0 0', paddingLeft: 16 }}>
                {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TechnicalView({ result, scenario }: { result: SimulationResponse; scenario: Scenario }) {
  const color = SCENARIO_COLORS[scenario];
  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <MetricRow label="Total habit spend (nominal)" value={fmt(result.total_habit_cost_nominal)} sub={`Real: ${fmt(result.total_habit_cost_real)}`} />
        <MetricRow label="Final monthly income" value={fmtMo(result.final_monthly_income)} sub={`after ${result.horizon_years} years`} />
      </div>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Portfolio at Year {result.horizon_years}
        </div>
        <PBand label="Opportunity cost of habits" data={result.opportunity_cost} color="#f97316" />
        <PBand label="Income savings portfolio" data={result.income_portfolio} color="#8b5cf6" />
        <PBand label="Combined portfolio (nominal)" data={result.combined_portfolio} color={color} />
        <PBand label="Combined portfolio (today's ₹)" data={result.combined_portfolio_real} color="#64748b" />
      </div>
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          What moves your outcome most?
        </div>
        <SensitivityChart result={result} />
      </div>
      <AssumptionsPanel result={result} />
    </div>
  );
}

// ── Root component ────────────────────────────────────────────────────────────

type ViewMode = 'simple' | 'technical';

interface Props {
  results: AllScenarios;
  activeScenario: Scenario;
  onScenarioChange: (s: Scenario) => void;
}

export default function ResultsPanel({ results, activeScenario, onScenarioChange }: Props) {
  const [view, setView] = useState<ViewMode>('simple');
  const result = results[activeScenario];

  return (
    <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden' }}>
      {/* Scenario tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0' }}>
        {(['conservative', 'base', 'optimistic'] as Scenario[]).map(s => (
          <button key={s} onClick={() => onScenarioChange(s)} style={{
            flex: 1, padding: '10px 0', border: 'none', cursor: 'pointer',
            fontSize: 13, fontWeight: s === activeScenario ? 600 : 400,
            background: s === activeScenario ? '#fff' : '#f8fafc',
            color: s === activeScenario ? SCENARIO_COLORS[s] : '#64748b',
            borderBottom: s === activeScenario ? `2px solid ${SCENARIO_COLORS[s]}` : '2px solid transparent',
            transition: 'all 0.15s',
          }}>
            {SCENARIO_LABELS[s]}
          </button>
        ))}
      </div>

      {/* Simple / Technical toggle */}
      <div style={{ display: 'flex', borderBottom: '1px solid #f1f5f9', background: '#fafafa' }}>
        {(['simple', 'technical'] as ViewMode[]).map(v => (
          <button key={v} onClick={() => setView(v)} style={{
            flex: 1, padding: '8px 0', border: 'none', cursor: 'pointer',
            fontSize: 12, fontWeight: v === view ? 600 : 400,
            background: v === view ? '#fff' : 'transparent',
            color: v === view ? '#0f172a' : '#94a3b8',
            borderBottom: v === view ? '2px solid #0f172a' : '2px solid transparent',
          }}>
            {v === 'simple' ? '💬 Plain English' : '📊 Technical Detail'}
          </button>
        ))}
      </div>

      <div style={{ padding: 16 }}>
        {view === 'simple'
          ? <SimpleView result={result} scenario={activeScenario} />
          : <TechnicalView result={result} scenario={activeScenario} />
        }
      </div>
    </div>
  );
}
