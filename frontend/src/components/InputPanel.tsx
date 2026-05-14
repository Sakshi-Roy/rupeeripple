import { useState } from 'react';
import type { FormState, HabitInput, Sector, Allocation, Frequency, Performance } from '../types';
import { CATEGORY_OPTIONS, CATEGORY_BY_KEY } from '../constants';
import { parseHabitsFromText } from '../api';

// ── Shared styles ─────────────────────────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  width: '100%', border: '1px solid #cbd5e1', borderRadius: 6,
  padding: '7px 10px', fontSize: 13, color: '#1e293b',
  background: '#fff', boxSizing: 'border-box',
};

const labelStyle: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, color: '#475569',
  textTransform: 'uppercase', letterSpacing: '0.05em',
  display: 'block', marginBottom: 4,
};

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #e2e8f0',
  borderRadius: 10, padding: 16, marginBottom: 12,
};

const iconBtn = (color = '#64748b'): React.CSSProperties => ({
  background: 'none', border: 'none', cursor: 'pointer',
  color, fontSize: 15, padding: '2px 5px', lineHeight: 1,
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function blankHabit(): HabitInput {
  return { id: String(Date.now()), name: '', cost_inr: 100, frequency: 'daily', categoryKey: 'coffee_chai' };
}

function monthlyFromHabit(h: HabitInput): number {
  return h.frequency === 'daily' ? h.cost_inr * 30.44
    : h.frequency === 'weekly' ? h.cost_inr * 4.333
    : h.cost_inr;
}

// ── Inline habit form (Add / Edit) ────────────────────────────────────────────

interface HabitFormProps {
  value: HabitInput;
  onChange: (h: HabitInput) => void;
  onSave: () => void;
  onCancel: () => void;
  saveLabel: string;
}

function HabitForm({ value, onChange, onSave, onCancel, saveLabel }: HabitFormProps) {
  return (
    <div style={{ padding: 12, background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
        <div style={{ gridColumn: '1/-1' }}>
          <label style={labelStyle}>Name</label>
          <input style={inputStyle} value={value.name}
            onChange={e => onChange({ ...value, name: e.target.value })}
            placeholder="e.g. Morning chai" autoFocus />
        </div>
        <div>
          <label style={labelStyle}>Cost (₹)</label>
          <input style={inputStyle} type="number" min={0} value={value.cost_inr}
            onChange={e => onChange({ ...value, cost_inr: Number(e.target.value) })} />
        </div>
        <div>
          <label style={labelStyle}>Frequency</label>
          <select style={inputStyle} value={value.frequency}
            onChange={e => onChange({ ...value, frequency: e.target.value as Frequency })}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <div style={{ gridColumn: '1/-1' }}>
          <label style={labelStyle}>Category</label>
          <select style={inputStyle} value={value.categoryKey}
            onChange={e => onChange({ ...value, categoryKey: e.target.value })}>
            {CATEGORY_OPTIONS.map(c => (
              <option key={c.key} value={c.key}>
                {c.label}  ({c.creepPct}%/yr)
              </option>
            ))}
          </select>
          {CATEGORY_BY_KEY[value.categoryKey]?.note && (
            <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 3 }}>
              {CATEGORY_BY_KEY[value.categoryKey].note}
            </div>
          )}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={onSave}
          disabled={!value.name.trim() || value.cost_inr <= 0}
          style={{
            flex: 1, background: '#3b82f6', color: '#fff', border: 'none',
            borderRadius: 6, padding: '7px 0', fontSize: 13, cursor: 'pointer', fontWeight: 500,
          }}>
          {saveLabel}
        </button>
        <button onClick={onCancel} style={{
          flex: 1, background: '#f1f5f9', color: '#475569', border: 'none',
          borderRadius: 6, padding: '7px 0', fontSize: 13, cursor: 'pointer',
        }}>
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── AI parse panel ────────────────────────────────────────────────────────────

interface ParsedHabit extends Omit<HabitInput, 'id'> {
  selected: boolean;
}

interface AIPanelProps {
  onAdd: (habits: HabitInput[]) => void;
}

function AIParsePanel({ onAdd }: AIPanelProps) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parsed, setParsed] = useState<ParsedHabit[] | null>(null);
  const [unparsed, setUnparsed] = useState('');

  async function handleParse() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setParsed(null);
    try {
      const res = await parseHabitsFromText(text);
      if (res.habits.length === 0) {
        setError("Couldn't find any spending habits in that text. Try being more specific — e.g. 'I spend ₹150 on chai every morning'.");
        return;
      }
      setParsed(res.habits.map(h => ({ ...h, selected: true })));
      setUnparsed(res.unparsed);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function handleAdd() {
    if (!parsed) return;
    const toAdd = parsed
      .filter(h => h.selected)
      .map(({ selected: _s, ...h }) => ({ ...h, id: String(Date.now() + Math.random()) }));
    onAdd(toAdd);
    setParsed(null);
    setText('');
    setUnparsed('');
  }

  const selectedCount = parsed?.filter(h => h.selected).length ?? 0;

  return (
    <div style={{
      marginBottom: 12, padding: 12,
      background: 'linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%)',
      border: '1px solid #bfdbfe', borderRadius: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <span style={{ fontSize: 16 }}>✨</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#1d4ed8' }}>Describe your habits in plain English</span>
        <span style={{ fontSize: 11, color: '#6b7280', marginLeft: 'auto',
          background: '#dbeafe', borderRadius: 4, padding: '2px 6px' }}>
          Powered by AI
        </span>
      </div>

      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder={`e.g. "I have chai every morning for about ₹30, order Swiggy twice a week spending around ₹400 each time, pay ₹799 a month for Netflix, and spend roughly ₹2000 a month on fuel"`}
        rows={3}
        style={{
          ...inputStyle,
          resize: 'vertical',
          fontFamily: 'inherit',
          lineHeight: 1.5,
        }}
      />

      <button
        onClick={handleParse}
        disabled={loading || !text.trim()}
        style={{
          marginTop: 8, width: '100%',
          background: loading || !text.trim() ? '#93c5fd' : '#2563eb',
          color: '#fff', border: 'none', borderRadius: 6,
          padding: '8px 0', fontSize: 13, fontWeight: 600,
          cursor: loading || !text.trim() ? 'not-allowed' : 'pointer',
        }}
      >
        {loading ? '✨ Parsing…' : 'Parse habits'}
      </button>

      {error && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#dc2626',
          background: '#fef2f2', borderRadius: 6, padding: '8px 10px' }}>
          {error}
        </div>
      )}

      {parsed && parsed.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
            Found {parsed.length} habit{parsed.length > 1 ? 's' : ''} — select which to add:
          </div>

          {parsed.map((h, i) => {
            const mo = h.frequency === 'daily' ? h.cost_inr * 30.44
              : h.frequency === 'weekly' ? h.cost_inr * 4.333 : h.cost_inr;
            const catLabel = CATEGORY_BY_KEY[h.categoryKey]?.label ?? h.categoryKey;
            return (
              <div key={i} onClick={() => setParsed(prev => prev!.map((p, j) => j === i ? { ...p, selected: !p.selected } : p))}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 10px', marginBottom: 4, borderRadius: 6, cursor: 'pointer',
                  background: h.selected ? '#eff6ff' : '#f8fafc',
                  border: `1px solid ${h.selected ? '#bfdbfe' : '#e2e8f0'}`,
                  transition: 'all 0.1s',
                }}>
                <input type="checkbox" checked={h.selected} readOnly
                  style={{ width: 14, height: 14, accentColor: '#2563eb', cursor: 'pointer' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: '#1e293b' }}>{h.name}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>
                    ₹{h.cost_inr}/{h.frequency} &middot; {catLabel}
                    &nbsp;&middot; <strong>₹{Math.round(mo).toLocaleString('en-IN')}/mo</strong>
                  </div>
                </div>
              </div>
            );
          })}

          {unparsed && (
            <div style={{ fontSize: 11, color: '#92400e', background: '#fff7ed',
              borderRadius: 6, padding: '6px 8px', marginTop: 6 }}>
              Could not parse: "{unparsed}"
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button onClick={handleAdd} disabled={selectedCount === 0} style={{
              flex: 1, background: selectedCount > 0 ? '#16a34a' : '#86efac',
              color: '#fff', border: 'none', borderRadius: 6,
              padding: '8px 0', fontSize: 13, fontWeight: 600,
              cursor: selectedCount > 0 ? 'pointer' : 'not-allowed',
            }}>
              Add {selectedCount} habit{selectedCount !== 1 ? 's' : ''} to list
            </button>
            <button onClick={() => { setParsed(null); setUnparsed(''); }} style={{
              flex: 1, background: '#f1f5f9', color: '#475569', border: 'none',
              borderRadius: 6, padding: '8px 0', fontSize: 13, cursor: 'pointer',
            }}>
              Discard
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Custom allocation panel ───────────────────────────────────────────────────

interface CustomAllocProps {
  equity: number; gold: number; fd: number;
  onChange: (eq: number, gld: number, fd: number) => void;
}

function CustomAllocPanel({ equity, gold, fd, onChange }: CustomAllocProps) {
  const total = equity + gold + fd;
  const valid = Math.abs(total - 100) < 0.1;

  function set(field: 'eq' | 'gld' | 'fd', val: number) {
    if (field === 'eq') onChange(val, gold, fd);
    else if (field === 'gld') onChange(equity, val, fd);
    else onChange(equity, gold, val);
  }

  return (
    <div style={{ marginTop: 10, padding: 12, background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 10 }}>
        Enter percentages. Must add up to 100%.
        <span style={{ float: 'right', fontWeight: 600, color: valid ? '#16a34a' : '#dc2626' }}>
          Total: {total}%
        </span>
      </div>
      {[
        { label: 'Equity (Nifty / Mutual Funds)', field: 'eq' as const, value: equity, hint: 'Higher return, higher risk' },
        { label: 'Gold (MCX / SGB)', field: 'gld' as const, value: gold, hint: 'Moderate, acts as hedge' },
        { label: 'FD / Debt Funds', field: 'fd' as const, value: fd, hint: 'Stable, lower return' },
      ].map(row => (
        <div key={row.field} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <label style={{ ...labelStyle, textTransform: 'none', fontSize: 12 }}>{row.label}</label>
            <span style={{ fontSize: 12, color: '#3b82f6', fontWeight: 600 }}>{row.value}%</span>
          </div>
          <input type="range" min={0} max={100} step={5} value={row.value}
            onChange={e => set(row.field, Number(e.target.value))}
            style={{ width: '100%', accentColor: '#3b82f6' }} />
          <div style={{ fontSize: 10, color: '#94a3b8' }}>{row.hint}</div>
        </div>
      ))}
      {!valid && (
        <div style={{ fontSize: 11, color: '#dc2626', marginTop: 6 }}>
          Allocations must sum to 100%. Currently: {total}%.
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  form: FormState;
  sectors: Sector[];
  allocations: Allocation[];
  onChange: (f: FormState) => void;
  onSubmit: () => void;
  loading: boolean;
}

export default function InputPanel({ form, sectors, allocations, onChange, onSubmit, loading }: Props) {
  const [adding, setAdding] = useState(false);
  const [newH, setNewH] = useState<HabitInput>(blankHabit());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<HabitInput | null>(null);
  const [showAI, setShowAI] = useState(false);

  const totalMonthly = form.habits.reduce((s, h) => s + monthlyFromHabit(h), 0);

  function updateIncome(key: keyof FormState['income'], val: string | number) {
    onChange({ ...form, income: { ...form.income, [key]: val } });
  }

  function removeHabit(id: string) {
    onChange({ ...form, habits: form.habits.filter(h => h.id !== id) });
  }

  function saveNewHabit() {
    if (!newH.name.trim() || newH.cost_inr <= 0) return;
    onChange({ ...form, habits: [...form.habits, { ...newH, id: String(Date.now()) }] });
    setNewH(blankHabit());
    setAdding(false);
  }

  function startEdit(h: HabitInput) {
    setEditingId(h.id);
    setEditDraft({ ...h });
    setAdding(false);
  }

  function saveEdit() {
    if (!editDraft) return;
    onChange({ ...form, habits: form.habits.map(h => h.id === editingId ? editDraft : h) });
    setEditingId(null);
    setEditDraft(null);
  }

  function addParsedHabits(habits: HabitInput[]) {
    onChange({ ...form, habits: [...form.habits, ...habits] });
    setShowAI(false);
  }

  const customTotal = form.custom_equity + form.custom_gold + form.custom_fd;
  const customValid = form.allocation_preset !== 'custom' || Math.abs(customTotal - 100) < 0.1;
  const canSubmit = !loading && form.habits.length > 0 && customValid;

  return (
    <div>
      {/* ── Habits card ── */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#0f172a' }}>Habits</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, color: '#64748b' }}>
              ~₹{Math.round(totalMonthly).toLocaleString('en-IN')}/mo
            </span>
            <button
              onClick={() => { setShowAI(v => !v); setAdding(false); setEditingId(null); }}
              title="Describe habits in plain English"
              style={{
                background: showAI ? '#dbeafe' : '#f0fdf4',
                border: `1px solid ${showAI ? '#93c5fd' : '#86efac'}`,
                borderRadius: 6, padding: '3px 8px', fontSize: 11,
                color: showAI ? '#1d4ed8' : '#15803d', cursor: 'pointer', fontWeight: 600,
              }}
            >
              ✨ AI
            </button>
          </div>
        </div>

        {/* AI parse panel (collapsible) */}
        {showAI && <AIParsePanel onAdd={addParsedHabits} />}

        {/* Habit list */}
        {form.habits.map(h => {
          const mo = monthlyFromHabit(h);
          const catLabel = CATEGORY_BY_KEY[h.categoryKey]?.label ?? h.categoryKey;

          if (editingId === h.id && editDraft) {
            return (
              <div key={h.id} style={{ marginBottom: 8 }}>
                <HabitForm value={editDraft} onChange={setEditDraft}
                  onSave={saveEdit} onCancel={() => { setEditingId(null); setEditDraft(null); }}
                  saveLabel="Save changes" />
              </div>
            );
          }

          return (
            <div key={h.id} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '8px 0', borderBottom: '1px solid #f1f5f9',
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: '#1e293b',
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {h.name || '(unnamed)'}
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  ₹{h.cost_inr}/{h.frequency} &middot; {catLabel}
                  &nbsp;&middot; <strong style={{ color: '#475569' }}>₹{Math.round(mo).toLocaleString('en-IN')}/mo</strong>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                <button title="Edit" onClick={() => startEdit(h)} style={iconBtn('#3b82f6')}>✏</button>
                <button title="Remove" onClick={() => removeHabit(h.id)} style={iconBtn('#ef4444')}>×</button>
              </div>
            </div>
          );
        })}

        {form.habits.length === 0 && !showAI && (
          <div style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', padding: '12px 0' }}>
            No habits added yet. Use ✨ AI or add manually below.
          </div>
        )}

        {adding ? (
          <div style={{ marginTop: 10 }}>
            <HabitForm value={newH} onChange={setNewH} onSave={saveNewHabit}
              onCancel={() => { setAdding(false); setNewH(blankHabit()); }}
              saveLabel="Add habit" />
          </div>
        ) : (
          <button onClick={() => { setAdding(true); setEditingId(null); setShowAI(false); }} style={{
            marginTop: 10, width: '100%', background: 'none',
            border: '1px dashed #cbd5e1', borderRadius: 6, padding: '7px 0',
            fontSize: 13, color: '#64748b', cursor: 'pointer',
          }}>
            + Add habit manually
          </button>
        )}
      </div>

      {/* ── Income ── */}
      <div style={cardStyle}>
        <h2 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 600, color: '#0f172a' }}>Income Profile</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div style={{ gridColumn: '1/-1' }}>
            <label style={labelStyle}>Monthly Income (₹)</label>
            <input style={inputStyle} type="number" min={1000}
              value={form.income.monthly_income}
              onChange={e => updateIncome('monthly_income', Number(e.target.value))} />
          </div>
          <div>
            <label style={labelStyle}>Current Age</label>
            <input style={inputStyle} type="number" min={18} max={70}
              value={form.income.current_age}
              onChange={e => updateIncome('current_age', Number(e.target.value))} />
          </div>
          <div>
            <label style={labelStyle}>Time Horizon (yrs)</label>
            <input style={inputStyle} type="number" min={1} max={40}
              value={form.income.horizon_years}
              onChange={e => updateIncome('horizon_years', Number(e.target.value))} />
          </div>
          <div style={{ gridColumn: '1/-1' }}>
            <label style={labelStyle}>Sector</label>
            <select style={inputStyle} value={form.income.sector_id}
              onChange={e => updateIncome('sector_id', e.target.value)}>
              {sectors.length === 0 && <option value="it_software">IT / Software</option>}
              {sectors.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div style={{ gridColumn: '1/-1' }}>
            <label style={labelStyle}>Performance Tier</label>
            <select style={inputStyle} value={form.income.performance}
              onChange={e => updateIncome('performance', e.target.value as Performance)}>
              <option value="below_average">Below Average (0.7×)</option>
              <option value="average">Average (1.0×)</option>
              <option value="above_average">Above Average (1.2×)</option>
              <option value="top_performer">Top Performer (3.0×)</option>
            </select>
          </div>
        </div>
      </div>

      {/* ── Portfolio & Settings ── */}
      <div style={cardStyle}>
        <h2 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 600, color: '#0f172a' }}>Portfolio & Settings</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div style={{ gridColumn: '1/-1' }}>
            <label style={labelStyle}>Asset Allocation</label>
            <select style={inputStyle} value={form.allocation_preset}
              onChange={e => onChange({ ...form, allocation_preset: e.target.value })}>
              {allocations.length === 0 && (
                <>
                  <option value="balanced">Balanced (60% eq / 30% gold / 10% FD)</option>
                  <option value="aggressive">Aggressive (80% eq / 10% gold / 10% FD)</option>
                  <option value="conservative">Conservative (30% eq / 20% gold / 50% FD)</option>
                </>
              )}
              {allocations.map(a => (
                <option key={a.id} value={a.id}>
                  {a.id.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  {' '}({Math.round(a.equity * 100)}% eq / {Math.round(a.gold * 100)}% gold / {Math.round(a.fd * 100)}% FD)
                </option>
              ))}
              <option value="custom">Custom — set my own percentages</option>
            </select>

            {form.allocation_preset === 'custom' && (
              <CustomAllocPanel
                equity={form.custom_equity} gold={form.custom_gold} fd={form.custom_fd}
                onChange={(eq, gld, fd) => onChange({ ...form, custom_equity: eq, custom_gold: gld, custom_fd: fd })}
              />
            )}
          </div>

          <div>
            <label style={labelStyle}>CPI / Inflation (%)</label>
            <input style={inputStyle} type="number" min={2} max={12} step={0.5}
              value={Math.round(form.cpi_rate * 100)}
              onChange={e => onChange({ ...form, cpi_rate: Number(e.target.value) / 100 })} />
            <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 3 }}>RBI avg 2014–24: 6%</div>
          </div>

          <div>
            <label style={labelStyle}>Simulations</label>
            <select style={inputStyle} value={form.n_simulations}
              onChange={e => onChange({ ...form, n_simulations: Number(e.target.value) })}>
              <option value={300}>300 (fast)</option>
              <option value={500}>500 (default)</option>
              <option value={1000}>1000 (accurate)</option>
            </select>
          </div>
        </div>
      </div>

      {/* ── Submit ── */}
      {form.allocation_preset === 'custom' && !customValid && (
        <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8, textAlign: 'center' }}>
          Custom allocation must add to 100% before running.
        </div>
      )}
      <button onClick={onSubmit} disabled={!canSubmit} style={{
        width: '100%', background: canSubmit ? '#3b82f6' : '#93c5fd',
        color: '#fff', border: 'none', borderRadius: 8,
        padding: '12px 0', fontSize: 14, fontWeight: 600,
        cursor: canSubmit ? 'pointer' : 'not-allowed', transition: 'background 0.2s',
      }}>
        {loading ? 'Running simulation…' : 'Run Simulation (3 scenarios)'}
      </button>
    </div>
  );
}
