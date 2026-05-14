"""
api/main.py — FastAPI application for the True Cost Engine.

Endpoints:
  POST /simulate    — run Monte Carlo simulation, return full result
  GET  /sectors     — list available sectors from sector_increments.json
  GET  /allocations — list predefined asset allocation presets
  GET  /health      — liveness check

Design notes:
- CORS is open for local dev (tighten in production).
- Engine errors that are ValueError (bad inputs) → 400.
- Unexpected engine errors → 500 with the message surfaced.
- n_simulations defaults to 500 at the API layer (fast enough for web UX).
  Users can raise it; engine enforces a minimum of 100.
"""

import json
import sys
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is on sys.path so `engine` package is importable
# regardless of where uvicorn is launched from.
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from engine.simulation import SimulationInputs, run_simulation
from engine.income import IncomeInputs
from engine.habits import Habit, VALID_CATEGORIES
from engine.returns import AssetAllocation, ALLOCATIONS

from api.models import SimulateRequest, ParseHabitsRequest, NarrateRequest

app = FastAPI(
    title="True Cost Engine",
    description=(
        "Monte Carlo simulation of the opportunity cost of habits, "
        "using India-specific income, tax, and market-return models."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_DATA_DIR = _root / "data"

# ---------------------------------------------------------------------------
# Gemini habit parser
# ---------------------------------------------------------------------------

_VALID_CATEGORY_KEYS = [
    "food_restaurant", "food_delivery", "coffee_chai", "tobacco", "alcohol",
    "fuel", "transport_app", "commute", "travel", "entertainment", "cloud_saas",
    "gym_wellness", "shopping", "wifi_internet", "general",
]

_PARSE_PROMPT = """You are a financial habit parser for an Indian personal finance app.

Extract every spending habit from the user's text and return them as JSON.

Valid categoryKey values (pick the closest match):
- food_restaurant  : dining out, restaurants
- food_delivery    : Swiggy, Zomato, food delivery
- coffee_chai      : coffee, chai, tea, cold drinks
- tobacco          : cigarettes, gutka, tobacco
- alcohol          : beer, wine, whisky, liquor
- fuel             : petrol, diesel for own vehicle
- transport_app    : Ola, Uber, Rapido, cab rides
- commute          : metro, bus, auto, daily travel to office
- travel           : flights, hotels, trips (convert annual spend to monthly: total/12)
- entertainment    : Netflix, Prime, Hotstar, cinema, OTT, gaming
- cloud_saas       : Google One, iCloud, Notion, software subscriptions
- gym_wellness     : gym, yoga, fitness classes, supplements
- shopping         : clothes, gadgets, shoes, accessories
- wifi_internet    : internet bill, mobile recharge, broadband
- general          : anything else

Rules:
1. cost_inr = cost per single occurrence, NOT monthly total.
   Example: "800 twice a week on food" → cost_inr=800, frequency="weekly"
   Example: "3000 a month on groceries" → cost_inr=3000, frequency="monthly"
2. frequency must be exactly one of: "daily", "weekly", "monthly"
3. For irregular spend (trips, annual subscriptions): divide by 12, set frequency="monthly"
4. name: short, 2–4 words, descriptive
5. If amount is vague ("some", "a bit"), make a reasonable urban-India estimate
6. Return ONLY raw JSON — no markdown fences, no explanation

JSON format:
{
  "habits": [
    {"name": "string", "cost_inr": number, "frequency": "daily|weekly|monthly", "categoryKey": "string"}
  ],
  "unparsed": "anything you could not turn into a habit, or empty string"
}

User text: "{text}"
"""


import re as _re

def _extract_json(text: str) -> dict:
    """Extract JSON from Gemini response, handling markdown wrapping."""
    text = text.strip()
    # Strip markdown code fences if present
    fence = _re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    # Find the outermost JSON object
    obj = _re.search(r"\{[\s\S]*\}", text)
    if obj:
        return json.loads(obj.group(0))
    raise ValueError("No JSON object found in Gemini response")


def _call_gemini(user_text: str) -> dict:
    from groq import Groq

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not set on the server. Add it as an environment variable and restart.",
        )

    client = Groq(api_key=api_key)
    prompt = _PARSE_PROMPT.replace("{text}", user_text)
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return _extract_json(completion.choices[0].message.content)


# ---------------------------------------------------------------------------
# Narrator
# ---------------------------------------------------------------------------

_NARRATE_PROMPT = """You are a personal finance coach for urban India. Given simulation data, write EXACTLY 2-3 sentences of personalised insight.

Rules:
- Be specific — use the actual numbers provided, formatted in Indian style (₹X Cr, ₹X L, ₹X K)
- Name the biggest habit by name
- Anchor the opportunity cost to a real Indian benchmark (e.g. college fees, car, metro flat downpayment, retirement corpus)
- Mention the #1 lever from sensitivity in plain language
- No bullet points. No headers. Plain prose only. Max 60 words total.

Data:
- Age: {current_age}, investing for {horizon_years} years (until age {final_age})
- Monthly income: ₹{monthly_income}
- Top habits by monthly spend: {habits_str}
- Opportunity cost of habits (P50, if invested instead): ₹{opp_p50}
- Total portfolio with income savings (P50): ₹{combined_p50}
- Biggest lever: {top_var} (changes final portfolio by {top_impact}%)

Write the 2-3 sentence insight now:"""


def _call_narrator(req: NarrateRequest) -> str:
    from groq import Groq

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return ""

    habits_str = ", ".join(
        f"{h.name} (₹{round(h.monthly_cost_inr):,}/mo)" for h in req.top_habits[:3]
    )

    def fmt_inr(n: float) -> str:
        if n >= 1_00_00_000: return f"{n/1_00_00_000:.1f} Cr"
        if n >= 1_00_000:    return f"{n/1_00_000:.1f} L"
        return f"{round(n):,}"

    prompt = _NARRATE_PROMPT.format(
        current_age=req.current_age,
        horizon_years=req.horizon_years,
        final_age=req.current_age + req.horizon_years,
        monthly_income=f"{round(req.monthly_income):,}",
        habits_str=habits_str,
        opp_p50=fmt_inr(req.opportunity_cost_p50_inr),
        combined_p50=fmt_inr(req.combined_portfolio_p50_inr),
        top_var=req.top_sensitivity_variable.replace("(+10%)", "").replace("(+5yr)", "").strip(),
        top_impact=round(abs(req.top_sensitivity_impact_pct), 1),
    )

    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=120,
    )
    return completion.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Helper: serialise a YearlySimResult for the API response
# ---------------------------------------------------------------------------

def _serialise_yearly(result) -> list[dict]:
    return [
        {
            "year": yr.year,
            "income_monthly": round(yr.income_monthly),
            "habit_cost_nominal": round(yr.habit_cost_nominal),
            "opportunity_cost": yr.opportunity_cost.to_dict(),
            "income_portfolio": yr.income_portfolio.to_dict(),
            "combined_portfolio": yr.combined_portfolio.to_dict(),
        }
        for yr in result.yearly
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "engine": "true_cost_engine v1.0"}


@app.get("/sectors")
def get_sectors():
    """Return all sectors from sector_increments.json."""
    with open(_DATA_DIR / "sector_increments.json") as f:
        data = json.load(f)
    return {
        "sectors": [
            {
                "id": sid,
                "name": info["name"],
                "mean_increment_pct": info["mean_increment_pct"],
                "source": info["source"],
            }
            for sid, info in data["sectors"].items()
        ]
    }


@app.get("/allocations")
def get_allocations():
    """Return predefined asset allocation presets."""
    return {
        "allocations": [
            {
                "id": name,
                "equity": alloc.equity,
                "gold": alloc.gold,
                "fd": alloc.fd,
            }
            for name, alloc in ALLOCATIONS.items()
        ],
        "categories": VALID_CATEGORIES,
    }


@app.post("/simulate")
def simulate(request: SimulateRequest):
    """
    Run a Monte Carlo simulation for a single scenario.

    Returns:
      - summary fields (P10/P50/P90 at final year, sensitivity ranking)
      - yearly[] — year-by-year percentile data for chart rendering
      - assumptions — full model assumptions for transparency panel
    """
    try:
        # --- Build engine inputs from request ---
        income_inputs = IncomeInputs(
            monthly_income=request.income_inputs.monthly_income,
            current_age=request.income_inputs.current_age,
            sector_id=request.income_inputs.sector_id,
            performance=request.income_inputs.performance,
            horizon_years=request.income_inputs.horizon_years,
        )

        habits = [
            Habit(
                name=h.name,
                cost_inr=h.cost_inr,
                frequency=h.frequency,
                category=h.category,
            )
            for h in request.habits
        ]

        # Resolve allocation — preset takes priority over custom weights
        if request.allocation.preset:
            if request.allocation.preset not in ALLOCATIONS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unknown allocation preset '{request.allocation.preset}'. "
                        f"Valid: {list(ALLOCATIONS.keys())}"
                    ),
                )
            allocation = ALLOCATIONS[request.allocation.preset]
        else:
            eq  = request.allocation.equity or 0.0
            gld = request.allocation.gold   or 0.0
            fd  = request.allocation.fd     or 0.0
            try:
                allocation = AssetAllocation(equity=eq, gold=gld, fd=fd)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        sim_inputs = SimulationInputs(
            income_inputs=income_inputs,
            habits=habits,
            allocation=allocation,
            cpi_rate=request.cpi_rate,
            n_simulations=request.n_simulations,
            scenario=request.scenario,
        )

        result = run_simulation(sim_inputs)

        return {
            **result.summary(),
            "yearly": _serialise_yearly(result),
            "assumptions": result.assumptions,
        }

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/parse-habits")
def parse_habits(request: ParseHabitsRequest):
    """
    Use Gemini 1.5 Flash to parse a plain-English habit description into
    structured habit objects that can be pre-filled into the simulation form.

    Requires GEMINI_API_KEY environment variable to be set.
    """
    try:
        raw = _call_gemini(request.text)

        habits_raw = raw.get("habits", [])
        if not isinstance(habits_raw, list):
            raise ValueError("Gemini returned unexpected format — no habits list.")

        # Validate and clean each habit
        cleaned = []
        for h in habits_raw:
            name = str(h.get("name", "")).strip() or "Unnamed habit"
            try:
                cost = float(h.get("cost_inr", 0))
            except (TypeError, ValueError):
                cost = 0.0
            freq = str(h.get("frequency", "monthly")).lower()
            if freq not in ("daily", "weekly", "monthly"):
                freq = "monthly"
            cat_key = str(h.get("categoryKey", "general"))
            if cat_key not in _VALID_CATEGORY_KEYS:
                cat_key = "general"

            if cost > 0:
                cleaned.append({
                    "name": name,
                    "cost_inr": cost,
                    "frequency": freq,
                    "categoryKey": cat_key,
                })

        return {
            "habits": cleaned,
            "unparsed": str(raw.get("unparsed", "")),
        }

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI returned malformed JSON. Try rephrasing your input.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/narrate")
def narrate(request: NarrateRequest):
    """
    Generate a 2-3 sentence personalised insight from simulation results.
    Returns empty string if GROQ_API_KEY is not set (graceful degradation).
    """
    try:
        text = _call_narrator(request)
        return {"insight": text}
    except Exception as exc:
        return {"insight": ""}  # never fail the UI over a narration error
