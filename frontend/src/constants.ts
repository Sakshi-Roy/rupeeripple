/**
 * Frontend category definitions.
 *
 * `engineCategory` must be a valid key from engine/habits.py CATEGORY_CREEP_RATES.
 * We add user-friendly aliases (commute, WiFi, cloud) that map to the closest
 * engine category. The creep rate shown is the engine's rate for that category.
 *
 * Why WiFi/travel/commute weren't in the original list:
 *   The engine was designed for discretionary habits you could redirect to savings.
 *   Utilities are usually fixed costs. But many users DO want to model them, so
 *   we include them here mapped to the closest matching engine inflation rate.
 */

export interface CategoryOption {
  key: string;           // unique key stored in form state
  engineCategory: string; // sent to the API — must match engine CATEGORY_CREEP_RATES
  label: string;         // shown to user
  creepPct: string;      // annual cost inflation rate (for tooltip)
  note?: string;         // optional context
}

export const CATEGORY_OPTIONS: CategoryOption[] = [
  // ── Food & Drink ──
  { key: 'food_restaurant',  engineCategory: 'food_restaurant', label: 'Food / Restaurant',            creepPct: '7.2', note: 'MOSPI Food CPI + quality upgrade' },
  { key: 'food_delivery',    engineCategory: 'food_delivery',   label: 'Food Delivery App',            creepPct: '8.0', note: 'Platform commission + food inflation' },
  { key: 'coffee_chai',      engineCategory: 'coffee_chai',     label: 'Coffee / Chai / Beverages',    creepPct: '7.0', note: 'Beverages CPI + quality upgrade' },
  // ── Substances ──
  { key: 'tobacco',          engineCategory: 'tobacco',         label: 'Tobacco / Cigarettes',         creepPct: '8.5', note: 'Sin tax escalation + CPI' },
  { key: 'alcohol',          engineCategory: 'alcohol',         label: 'Alcohol',                      creepPct: '7.5', note: 'State excise + inflation' },
  // ── Transport ──
  { key: 'fuel',             engineCategory: 'fuel',            label: 'Fuel (Petrol/Diesel)',         creepPct: '6.0', note: 'Average fuel price change' },
  { key: 'transport_app',    engineCategory: 'transport_app',   label: 'Ride-hailing (Ola/Uber/Rapido)', creepPct: '6.5', note: 'App pricing trend' },
  { key: 'commute',          engineCategory: 'transport_app',   label: 'Daily Commute (Metro/Bus/Auto)', creepPct: '6.5', note: 'Mapped to transport inflation' },
  { key: 'travel',           engineCategory: 'general',         label: 'Flights / Travel (Recurring)', creepPct: '6.0', note: 'Modelled at general CPI; travel is occasional so use annual cost ÷ 12' },
  // ── Entertainment & Subscriptions ──
  { key: 'entertainment',    engineCategory: 'entertainment',   label: 'Entertainment / OTT Streaming', creepPct: '10.0', note: 'Platform pricing history (Netflix/Prime/Spotify)' },
  { key: 'cloud_saas',       engineCategory: 'entertainment',   label: 'Cloud / SaaS / App Subscriptions', creepPct: '10.0', note: 'Platform pricing — same inflation as OTT' },
  // ── Health & Fitness ──
  { key: 'gym_wellness',     engineCategory: 'gym_wellness',    label: 'Gym / Fitness / Wellness',     creepPct: '8.0', note: 'Fitness industry pricing' },
  // ── Shopping ──
  { key: 'shopping',         engineCategory: 'shopping',        label: 'Shopping / Clothes / Gadgets', creepPct: '6.0', note: 'Consumer goods CPI' },
  // ── Utilities (fixed costs people still want to model) ──
  { key: 'wifi_internet',    engineCategory: 'general',         label: 'WiFi / Internet / Phone Bill', creepPct: '6.0', note: 'Utility — modelled at headline CPI' },
  // ── Catch-all ──
  { key: 'general',          engineCategory: 'general',         label: 'General / Other',              creepPct: '6.0', note: 'RBI CPI headline average' },
];

export const CATEGORY_BY_KEY: Record<string, CategoryOption> =
  Object.fromEntries(CATEGORY_OPTIONS.map(c => [c.key, c]));
