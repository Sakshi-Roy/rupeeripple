# RupeeRipple
### *Every habit has a price. Most people never see it.*

---

## The Name

**RupeeRipple** captures the central idea: a small, daily financial decision — ₹150 on chai, ₹400 on Swiggy, ₹799 on Netflix — creates a ripple through time. Compounded over 20 years through real market returns, that ripple becomes a wave. The app makes that wave visible.

---

## The Problem

Most personal finance tools in India ask you to track spending. RupeeRipple asks a different question:

> **What is this habit actually costing you — not today, but over your lifetime?**

A ₹150 daily coffee feels trivial. It is ₹4,500 a month, ₹54,000 a year. Invested in a balanced portfolio for 20 years at historical Indian market returns, it compounds to roughly **₹28–40 lakhs** — enough to fund four years of a private engineering college or anchor a retirement corpus.

Nobody cuts coffee because "₹150 is nothing." They cut it — or consciously keep it — when they see **₹38 lakhs** attached to it.

That is the shift RupeeRipple creates: from abstract guilt to concrete, probabilistic, honest numbers.

---

## Who This Is For

| Profile | What they get from RupeeRipple |
|---|---|
| **Young professional (22–35)** | Understands the compound cost of lifestyle inflation early, when the leverage of time is highest |
| **Mid-career earner (35–50)** | Quantifies which habits to cut versus keep, ranked by actual financial impact |
| **Personal finance advisor** | A client-facing tool to show "here is what your Swiggy habit costs, in this market, over your career" — not a spreadsheet, a simulation |
| **Financial literacy educator** | A live demo of compound interest, tax drag, and inflation — all in one screen |

---

## The Use Case, In Plain English

1. You open RupeeRipple.
2. Describe your habits — either fill in the form, or type naturally: *"I spend ₹200 on chai every morning and order Zomato twice a week at about ₹500 each time."*
3. Add your income and tell it how long you want to simulate — 10, 20, 30 years.
4. Choose how you'd invest: balanced (60% equity, 30% gold, 10% FD), aggressive, conservative, or set your own weights.
5. Click **Run Simulation**.
6. See three things:
   - What your habits have cost you in cash, over that time.
   - What that same money *could have grown to* if you had invested it instead — shown as a probability range, not a single number.
   - Which single variable — time horizon, savings rate, habit size, inflation — matters most to your outcome.
7. Read a two-sentence AI-generated insight that anchors the numbers to something real: a car, a flat downpayment, college fees.

Total time: under 3 minutes.

---

## Why This Is Honest (and Most Apps Are Not)

Most "opportunity cost" calculators give you a single projected number: "your daily coffee will cost you ₹42,37,000 over 20 years." That number is a fiction. Markets do not move in straight lines. Inflation is not constant. Nobody knows the return for the next 20 years.

RupeeRipple is built around **honest uncertainty**:

- It runs **500 independent simulation paths** (configurable up to thousands), each using a different sequence of historical market returns.
- It reports **P10 / P50 / P90** — the worst 10% of outcomes, the median, and the best 10%. The range is real.
- Every result screen includes the model's **known limitations** — sample size, tax approximations, what is not modelled.
- All numbers are shown in both **nominal** (future rupees) and **real** (today's purchasing power, CPI-deflated) terms.

The wide band between P10 and P90 is not a bug. It is the most honest thing the app does.

---

## The Mechanics

### 1. Market Return Model — Block Bootstrap

**What we do:** Sample historical market returns in contiguous blocks of 6 months, not individually, to reconstruct portfolio return paths.

**Why block bootstrap instead of:**
- *Parametric (log-normal) model* — assumes returns are independently drawn from a normal distribution. Real markets have crash clustering: bad months follow bad months. A parametric model will always underestimate how bad a bad year actually feels. Block bootstrap preserves this.
- *Simple historical replay* — replays the same 25-year sequence every time. Gives you one path, not a distribution. No uncertainty, no percentiles.
- *Monte Carlo with assumed correlation matrices* — requires estimating a covariance matrix from limited data. Estimation error in the covariance matrix is large and compounds badly over 20 years.

**Block size of 6 months** was chosen deliberately: long enough to capture crash episodes (the 2008 crisis, COVID March 2020), short enough to still randomise across regimes.

**Data:** 25 years of Nifty 50 monthly returns, gold (MCX), and FD rates. The sampler validates that the loaded data has annualised mean in [8%, 18%] and annualised std in [15%, 30%] — if the numbers look wrong, it refuses to run.

**Three asset classes modelled:**
- **Equity (Nifty 50):** Long-run annualised mean ~12–13%, std ~20–22%. High reward, high variance.
- **Gold:** Annualised mean ~8–9%, lower variance, negative correlation to equity in crises. Acts as a hedge.
- **Fixed Deposits:** Deterministic ~6–7% per annum. No variance. Provides stability and liquidity.

Cross-asset correlations are preserved *within each sampled block*, which matters: in a crash month, equity and gold move together in ways that a diagonal covariance matrix misses.

---

### 2. Income Model — India Sector Salary Data

Income is not held constant. It grows over the simulation horizon using **real sector-specific salary increment data** from industry surveys (EY, WTW, Aon) covering IT/Software, BFSI, Healthcare, Manufacturing, and others.

Each sector has a **mean increment percentage** (e.g., IT sector: ~10–11% per annum historically) and a **performance modifier**:

| Performance tier | Multiplier |
|---|---|
| Below average | 0.6× sector mean |
| Average | 1.0× sector mean |
| Above average | 1.3× sector mean |
| Top performer | 1.6× sector mean |

The **three scenarios** (Conservative / Base / Optimistic) apply a further sector-wide adjustment:
- **Conservative:** Assumes lower market returns and lower income growth — models a slow career or adverse market decade.
- **Base:** Uses historical averages as-is.
- **Optimistic:** Upper-end return paths, stronger income growth — models a strong career and bull market.

These are run **simultaneously** and shown as three tabs, letting you see the range of realistic futures rather than picking one.

---

### 3. Tax Model — India New Regime, July 2024 Budget

Tax is applied **within each simulation path**, not post-hoc. This matters because taxes are paid on gains, not contributions, and the order of compounding and taxation affects the real answer.

**What is modelled:**
- **LTCG (Long-Term Capital Gains):** 12.5% on equity and gold returns (post July 2024 budget)
- **FD interest:** Taxed at the user's income slab rate (derived from annual income)
- **4% health and education cess** on all tax
- **STT (Securities Transaction Tax):** Factored into effective return

**What is not modelled** (documented honestly in the assumptions panel):
- Short-term capital gains (STCG) — assumes a buy-and-hold approach
- Tax-loss harvesting
- ELSS / 80C deductions (would require modelling full tax return, not just gains)
- ULIP / NPS-specific tax treatment

The model applies a **blended effective rate approximation** — simpler than lot-by-lot tracking, directionally correct, and the error is disclosed.

---

### 4. Habit Cost Model — Category Creep

Habits do not cost the same every year. Prices rise. More importantly, lifestyle habits have a documented tendency to **inflate with income** — as you earn more, you eat at slightly better restaurants, upgrade your subscription tier, commute slightly more comfortably.

RupeeRipple models this as **category-specific creep rates** layered on top of the CPI rate you set:

| Category | Annual creep rate (above CPI) |
|---|---|
| Food delivery (Swiggy/Zomato) | +2% |
| Restaurants | +1.5% |
| Coffee / chai | +1% |
| Transport apps | +2% |
| Entertainment / OTT | +3% |
| Travel | +4% |
| General | +1% |

So if CPI is 6% and you set "food delivery" as a habit, its cost grows at ~8% per year in the simulation. This makes 20-year projections more honest than a flat-cost assumption.

---

### 5. Sensitivity Analysis — One-at-a-Time Perturbation

After the main simulation runs, the engine runs four additional mini-simulations, each with one variable perturbed by a small fixed amount:

| Variable | Perturbation |
|---|---|
| Savings rate | +10% relative |
| Habit cost | +10% relative |
| Inflation (CPI) | +1 percentage point |
| Time horizon | +5 years |

For each perturbation, it computes how much the **P50 combined portfolio** changes. The variable that produces the biggest % change is ranked #1.

**Why this matters:** Users often focus on the habit — "should I cut the coffee?" — when the answer is almost always "stay invested five more years." The sensitivity ranking makes this concrete and personal, not generic.

---

## The AI Features

### Feature 1: Plain-English Habit Parser (✨ button)

**What it does:** You type: *"I spend ₹300 on coffee every day, take an Uber to office costing about ₹200 each way three times a week, and pay ₹649 a month for Spotify."* The AI extracts structured habit objects — name, cost, frequency, category — that are pre-filled into the simulation form.

**How it works:**
- A carefully engineered prompt is sent to **Llama 3.1 (8B)** via the **Groq API** (free tier, ~14,400 requests/day).
- The prompt includes all 15 valid category keys with plain-English descriptions, a rule that cost_inr should be per-occurrence not monthly total, and instructions for handling annual spend (divide by 12).
- The response is validated: categoryKey must be in the valid set, frequency must be daily/weekly/monthly, cost must be > 0. Anything that passes validation is shown as a selectable checklist — you choose what to add.
- Handles markdown-wrapped JSON responses from the model gracefully.

**Why Groq + Llama over alternatives:**
- Gemini free tier had regional quota limitations (limit: 0 in practice).
- OpenAI GPT has no meaningful free tier.
- Groq's free tier is genuinely generous and Llama 3.1 8B is more than capable of a structured JSON extraction task. It is not a reasoning task — it is entity extraction with constraints.

**Why not a local rule-based parser:**
- A rule-based parser cannot handle: *"I go out for chai roughly four times a week, maybe ₹40-50 each time"* (vague amount), or *"We split Hotstar with two friends, my share is about ₹133"* (division in natural language). The LLM handles these gracefully; a regex would miss them.

---

### Feature 2: AI Result Narrator (🤖 Insight)

**What it does:** After each simulation run, a 2–3 sentence personalised insight appears above the results, written in plain English, anchored to Indian benchmarks. Example:

> *"Your weekend dining habit (₹6,500/month) is your single biggest cost driver — redirected to a balanced portfolio, it grows to ₹31.2 L by age 48, roughly the down payment on a 2BHK in Pune. The single biggest lever for your outcome isn't the habit size though — staying invested five more years moves your final portfolio 4× more than cutting dining entirely."*

**How it works:**
- After `/simulate` returns, the frontend calls `/narrate` **asynchronously** — results appear immediately, the insight appears ~1–2 seconds later.
- The narrator receives: age, horizon, income, top 3 habits by monthly cost, opportunity cost P50, combined portfolio P50, and the top sensitivity variable.
- A structured prompt instructs the model to: use actual numbers in Indian notation (₹X Cr / ₹X L), name the biggest habit, anchor to a real Indian benchmark (college fees, car, flat), and mention the #1 lever. Max 60 words. No bullet points.
- Temperature: 0.4 (slightly higher than the parser's 0.1 — we want variety in phrasing, not just determinism).
- The endpoint **never throws an error to the user** — if the AI call fails for any reason (quota, network, model error), the insight card simply does not appear. The simulation results are unaffected.

**Why this matters:** The numbers alone — ₹28.4 L, P50, 20yr — are abstract. *"Down payment on a 2BHK in Pune"* is not. The narrator converts financial output into a decision frame.

---

## Technical Stack

### Backend
| Component | Choice | Why |
|---|---|---|
| **Language** | Python 3.12 | Scientific computing ecosystem (NumPy, Pandas) |
| **API framework** | FastAPI | Async, Pydantic v2 validation, automatic OpenAPI docs |
| **Simulation engine** | Pure NumPy | Vectorised across simulation paths — 500 paths × 240 months runs in <1 second |
| **AI API** | Groq (Llama 3.1 8B) | Generous free tier, low latency, sufficient for structured extraction |
| **Server** | Uvicorn | ASGI, production-grade, hot reload in dev |

### Frontend
| Component | Choice | Why |
|---|---|---|
| **Framework** | React 18 + TypeScript | Component model maps cleanly to the panel layout |
| **Build tool** | Vite | Fast HMR, native ESM, proxy for API |
| **Styling** | Tailwind v4 | Utility-first, no separate CSS files |
| **Charts** | Recharts | Declarative, composable, handles the stacked-area band chart well |
| **State** | useState + prop drilling | No global state needed — one simulation result, three scenarios |

### Infrastructure
| Component | Choice |
|---|---|
| **Containerisation** | Docker (multi-stage for frontend, slim Python for backend) |
| **Orchestration** | docker-compose with health checks |
| **Reverse proxy** | nginx (routes `/api/*` to backend, serves React SPA) |

---

## What Is Not Modelled (and Why We Say So)

RupeeRipple includes an **Assumptions Panel** visible in the technical view. It states explicitly:

- Returns are bootstrapped from 25 years of data — thin sample for estimating P10/P90 tail behaviour.
- Tax is a blended-rate approximation, not lot-by-lot FIFO accounting.
- Life events (marriage, home loan, job loss, illness) are not modelled.
- Habit costs are assumed permanent — stopping a habit is not modelled.
- Correlation between inflation and equity returns is assumed stationary over the horizon.

This is a deliberate product decision. An app that overpromises accuracy loses the user's trust the moment reality diverges from the projection. An app that is honest about uncertainty earns trust — and the user who understands P10/P50/P90 is a more financially literate user.

---

## Roadmap

- **GitHub deployment** — containerised deploy via Docker Compose on a cloud VM
- **Test suite expansion** — integration tests for the full API layer, end-to-end scenario validation
- **Goal reverse calculator** — user inputs a target corpus (e.g. ₹1 Cr by age 50), AI figures out which habits to cut and by how much
- **PDF export** — generate a one-page scenario report for sharing with a financial advisor
- **Multi-currency / NRI mode** — USD/AED income with INR habit costs and India portfolio exposure

---

*Built with Python, FastAPI, React, Recharts, and Groq/Llama. Simulation engine validated against 59 unit tests covering income projection, tax calculation, return sampling, and Monte Carlo convergence.*
