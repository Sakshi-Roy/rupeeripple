import type { SimulationResponse, Scenario } from '../types';
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';

const SCENARIO_COLORS: Record<Scenario, string> = {
  conservative: '#f97316',
  base: '#3b82f6',
  optimistic: '#22c55e',
};

function fmtCr(v: number) {
  if (v >= 10_000_000) return `₹${(v / 10_000_000).toFixed(1)}Cr`;
  if (v >= 100_000) return `₹${(v / 100_000).toFixed(0)}L`;
  return `₹${(v / 1000).toFixed(0)}K`;
}

interface Props {
  result: SimulationResponse;
  scenario: Scenario;
}

export default function TrajectoryChart({ result, scenario }: Props) {
  const color = SCENARIO_COLORS[scenario];

  // Build chart data: stacked area for P10→P90 band, line for P50
  const data = result.yearly.map(yr => ({
    year: yr.year,
    p10: yr.combined_portfolio.p10,
    // Recharts stacked area: first area goes from 0→p10 (transparent base),
    // second area goes from p10→p90 (the visible band)
    band: yr.combined_portfolio.p90 - yr.combined_portfolio.p10,
    p50: yr.combined_portfolio.p50,
    opp_p50: yr.opportunity_cost.p50,
  }));

  return (
    <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16 }}>
      <div style={{ marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#0f172a' }}>
          Wealth Trajectory — {scenario.charAt(0).toUpperCase() + scenario.slice(1)} Scenario
        </h3>
        <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748b' }}>
          Combined portfolio (habit savings + income savings) over {result.horizon_years} years.
          Shaded band = P10 to P90. Line = P50 median.
        </p>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
          <XAxis
            dataKey="year"
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            label={{ value: 'Year', position: 'insideBottomRight', offset: -5, fontSize: 11, fill: '#94a3b8' }}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            tickFormatter={fmtCr}
            width={55}
          />
          <Tooltip
            formatter={(value, name) => {
              const v = typeof value === 'number' ? value : 0;
              if (name === 'p10 (base)') return [fmtCr(v), 'P10'];
              if (name === 'band') return [fmtCr(v), 'P90 – P10'];
              if (name === 'Combined P50') return [fmtCr(v), 'P50 median'];
              if (name === 'Habit opp. cost P50') return [fmtCr(v), 'Habit-only P50'];
              return [fmtCr(v), String(name)];
            }}
            labelFormatter={(v) => `Year ${v}`}
            contentStyle={{ fontSize: 12, borderRadius: 6, border: '1px solid #e2e8f0' }}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, color: '#64748b', paddingTop: 8 }}
            iconType="circle"
          />

          {/* Transparent base to start the band from p10 */}
          <Area
            type="monotone"
            dataKey="p10"
            name="p10 (base)"
            stackId="band"
            fill="transparent"
            stroke="none"
            legendType="none"
          />
          {/* Visible P10→P90 band */}
          <Area
            type="monotone"
            dataKey="band"
            name="P10–P90 range"
            stackId="band"
            fill={color + '28'}
            stroke={color + '50'}
            strokeWidth={0.5}
          />

          {/* P50 median line */}
          <Line
            type="monotone"
            dataKey="p50"
            name="Combined P50"
            stroke={color}
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4 }}
          />

          {/* Opportunity cost of habits */}
          <Line
            type="monotone"
            dataKey="opp_p50"
            name="Habit opp. cost P50"
            stroke="#f97316"
            strokeWidth={1.5}
            strokeDasharray="5 3"
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <p style={{ fontSize: 11, color: '#94a3b8', marginTop: 8, marginBottom: 0 }}>
        Dashed orange line shows what your habit spend alone could have grown to if invested.
        All values nominal (future rupees, not inflation-adjusted). {result.assumptions.simulation_paths} simulation paths.
      </p>
    </div>
  );
}
