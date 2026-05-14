# RupeeRipple 💸

> **Every habit has a price. Most people never see it.**

RupeeRipple is a Monte Carlo simulation engine that shows the true, probabilistic, long-term opportunity cost of daily spending habits — built specifically for India's tax regime, salary structure, and market returns.

---

## What it does

You enter your habits (coffee, Swiggy, Netflix, petrol), income, and investment preference. RupeeRipple runs 500 simulation paths through 25 years of historical Nifty 50, gold, and FD return data and shows you:

- **P10 / P50 / P90** — the range of realistic outcomes, not a single number
- **Sensitivity ranking** — which lever (time, savings rate, inflation, habit size) matters most
- **AI insight** — a 2-sentence personalised summary anchored to real Indian benchmarks
- **Three scenarios** — Conservative, Base, Optimistic — simultaneously

---

## Tech stack

| Layer | Stack |
|---|---|
| Simulation engine | Python 3.12, NumPy, Pandas |
| API | FastAPI, Pydantic v2, Uvicorn |
| AI | Groq API (Llama 3.1 8B) |
| Frontend | React 18, TypeScript, Vite, Recharts |
| Infrastructure | Docker, docker-compose, nginx |

---

## Project structure

```
rupeeripple/
├── engine/              # Simulation engine (pure Python, no FastAPI dependency)
│   ├── simulation.py    # Monte Carlo orchestrator
│   ├── income.py        # Sector salary trajectory model
│   ├── returns.py       # Block bootstrap return sampler
│   ├── tax.py           # India new tax regime (July 2024)
│   └── habits.py        # Habit cost + category creep model
├── api/
│   ├── main.py          # FastAPI app — all routes
│   └── models.py        # Pydantic request/response models
├── data/
│   ├── sector_increments.json   # EY/WTW/Aon salary increment data
│   └── generate_returns.py      # Synthetic return data generator
├── frontend/            # React + TypeScript + Vite
│   └── src/
│       ├── components/  # InputPanel, ResultsPanel, TrajectoryChart
│       ├── api.ts       # API client
│       ├── types.ts     # TypeScript interfaces
│       └── constants.ts # Category mappings
├── tests/               # 98 API-layer integration tests
├── Dockerfile.api
├── Dockerfile.frontend
├── docker-compose.yml
└── pytest.ini
```

---

## Local development

### Prerequisites
- Python 3.12+
- Node.js 20+
- A free [Groq API key](https://console.groq.com) (for AI features — optional, app works without it)

### Backend

```bash
pip install -r requirements.txt

# Set your Groq key (optional — AI features only)
export GROQ_API_KEY=your_key_here          # Mac/Linux
$env:GROQ_API_KEY="your_key_here"          # Windows PowerShell

python -m uvicorn api.main:app --reload
# API running at http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# App running at http://localhost:5173
```

### Run tests

```bash
python -m pytest tests/ -v
# 98 tests, all passing
```

---

## Docker (production)

```bash
# Set your Groq key in the environment first
export GROQ_API_KEY=your_key_here

docker compose up --build
# App at http://localhost:3000
# API at http://localhost:8000
```

The frontend container serves the built React app via nginx and proxies `/api/*` requests to the backend container.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | No | Enables AI habit parser and result narrator. Without it, both features are silently disabled. |

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/sectors` | Available salary sectors |
| `GET` | `/allocations` | Asset allocation presets |
| `POST` | `/simulate` | Run Monte Carlo simulation |
| `POST` | `/parse-habits` | Parse plain-English habits via AI |
| `POST` | `/narrate` | Generate AI insight from results |

Full OpenAPI docs available at `http://localhost:8000/docs` when the backend is running.

---

## Model assumptions (documented honestly)

- Returns bootstrapped from 25 years of historical data — thin sample for P10/P90 tail estimation
- Tax applied as blended effective rate, not lot-by-lot FIFO
- Life events (marriage, home loan, illness) not modelled
- Habit costs assumed permanent — stopping a habit mid-horizon not modelled
- Equity-gold-FD correlations assumed stationary over the horizon

These are disclosed in the app's Assumptions panel on every results page.

---

## Licence

MIT
