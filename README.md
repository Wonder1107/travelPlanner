# Dynamic Smart Itinerary Engine MVP

RAG + Prompt + Agent travel planning demo for AI PM internship portfolio.

## Project Structure

```
backend/
  app/
    agents/
    services/
    tools/
    prompts/
    main.py
    schemas.py
    db.py
  tests/
frontend/
  app/
  components/
  lib/
data/
  poi_shanghai.json
docs/
```

## Core Capabilities
- **RAG**: Local POI knowledge retrieval with lexical + optional Chroma vector search
- **Prompt Engineering**: Prompt library for onboarding/planner/replanner/critic roles
- **Agent Workflow**: Planner + Monitor + Replanner orchestration (LangGraph-compatible fallback)
- **Dynamic Replan**: Event-driven itinerary updates for weather/crowd/user status

## Backend Setup (FastAPI)

```bash
cd backend
python3.10 -m venv .venv
source .venv/bin/activate
python -V  # should be Python 3.10.x
# 1) install pinned runtime dependencies first (avoid resolver loop)
python -m pip install --upgrade pip
python -m pip install -r requirements-core.txt
# 2) then install dev dependencies
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Alternative (editable install):

```bash
cd backend
source .venv/bin/activate
python -m pip install -e .
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If your old virtualenv was created with Python 3.9, recreate it first:

```bash
cd backend
rm -rf .venv
python3.10 -m venv .venv
source .venv/bin/activate
python -V  # should be Python 3.10.x
python -m pip install --upgrade pip
python -m pip install -r requirements-core.txt
python -m pip install -r requirements-dev.txt
```

Optional environment variables:

```bash
export OPENAI_API_KEY=your_key_here
export LLM_MODEL_REPLANNER=gpt-4o-mini
export LLM_TIMEOUT_SECONDS=8
export LLM_PROMPT_VARIANT=A
export DATABASE_URL=sqlite:////absolute/path/to/travel_agent.db
```

LLM behavior in replanner:
- If `OPENAI_API_KEY` is available, event replanning tries structured LLM decision first.
- If API timeout / invalid JSON / missing key occurs, system automatically falls back to deterministic rule strategy.
- `/api/trips/{trip_id}/events` now returns optional `decision` and `meta` fields (`decision_source`, `fallback_used`, `latency_ms`).

## Frontend Setup (Next.js)

```bash
cd frontend
npm install
export NEXT_PUBLIC_API_BASE=http://localhost:8000
npm run dev
```

## API Endpoints
- `POST /api/trips`
- `GET /api/trips/{trip_id}`
- `POST /api/trips/{trip_id}/events`
- `GET /api/trips/{trip_id}/logs`
- `POST /api/trips/{trip_id}/decisions/{decision_id}/feedback`
- `GET /api/trips/{trip_id}/versions`
- `POST /api/trips/{trip_id}/versions/{version_id}/rollback`
- `GET /api/config/replan`

## Test

```bash
cd backend
pytest
```

Run replanner eval cases (30 scenarios):

```bash
cd backend
python scripts/eval_replanner.py
```

Generated report:
- `backend/evals/eval_report.md`

## Suggested Demo Flow
1. On `/`, input preferences and create a trip.
2. On `/trip/{id}`, trigger rain/crowd/tired events.
3. On `/console`, inspect tool calls and replanning rationale.
