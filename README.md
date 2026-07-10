# Customer Support Ticket System

A multi-agent AI system that classifies, prioritizes, drafts a reply for, and compliance-checks
customer support tickets end to end, then hands each one to a human reviewer to approve, reject, or edit.

Use case #1 of the Ascendion internship build (the skeleton the legal and governance use cases reuse).

---

## What's in the box

| Piece | Tech | What it does |
|---|---|---|
| Agent pipeline | LangGraph | Intake -> classify -> sensitivity -> difficulty -> route -> retrieve -> draft -> review -> decide |
| Backend API | FastAPI (`api.py`) | Wraps the pipeline: create a ticket, list the queue, approve/reject/edit a draft |
| System of record | Postgres (`app/store.py`) | The reviewer queue + human actions (structured, durable) |
| Knowledge base | Weaviate (`app/kb.py`) | Past resolutions, retrieved by similarity for the reply agent (RAG) |
| Model lanes | Modal GPU + Claude (`app/router.py`) | 3B/14B open models on Modal for private tickets; Claude cloud for the rest |
| Reviewer UI | Next.js (`frontend/`) | Queue, ticket detail, approve/reject/edit, customer submit form |

---

## Prerequisites

Install these once:

- **Docker Desktop** (runs Postgres + Weaviate locally). Must be running before you start the backend.
- **uv** (Python package manager / runner). https://docs.astral.sh/uv/
- **Node.js 18+** and npm (for the frontend).
- **A `.env` file** in the repo root (see below). It is gitignored and never committed.

> The open-model lanes (3B/14B) run on Modal as web endpoints, deployed separately from `modal_lane/llm_service.py`.
> You only need the endpoint **URLs + token** in your `.env`; you do not install Modal to run the app.

### `.env` (copy from `.env.example` and fill in)

```
PRIVATE_LANE_URL=...        # Modal 3B endpoint URL   (REQUIRED, read at startup even in dev)
PRIVATE_LANE_TOKEN=...      # shared-secret token for the Modal endpoints (REQUIRED)
REVIEW_LANE_URL=...         # Modal 14B endpoint URL   (REQUIRED, read at startup even in dev)
MODEL_TIER=dev             # dev | local | full  (see table below; default dev)
ANTHROPIC_API_KEY=          # only needed when MODEL_TIER=full
DATABASE_URL=postgresql://support:support@127.0.0.1:5432/tickets
```

> All three lane variables are read the moment the app imports `app/router.py`, so the API and demo
> will not even start if any is missing, regardless of `MODEL_TIER`. Use `127.0.0.1` (not `localhost`)
> in `DATABASE_URL` to force IPv4.

---

## First-time setup

```bash
# 1. Backend deps (creates the venv from pyproject.toml / uv.lock)
uv sync

# 2. Start the databases (Postgres + Weaviate) in the background
docker compose up -d

# 3. Seed the knowledge base (creates + fills the Weaviate "Knowledge" collection)
uv run python seed_kb.py

# 4. Frontend deps
cd frontend
npm install
cd ..
```

---

## Run it (everyday, two terminals)

**Terminal 1: backend API**
```bash
docker compose up -d                     # if the DBs aren't already running
uv run uvicorn api:app --reload          # API on http://localhost:8000
```

**Terminal 2: frontend**
```bash
cd frontend
npm run dev                              # UI on http://localhost:3000
```

Then open **http://localhost:3000**. Submit a ticket at `/new`, watch it appear in the queue,
click it to review, and approve / reject / edit the AI's draft.

### Command-line demo (no UI, no DB writes needed for the pipeline itself)
```bash
uv run python demo.py                    # runs the pipeline over 7 sample tickets, prints each result
```

---

## Model tiers (`MODEL_TIER`)

| Tier | What runs | When to use |
|---|---|---|
| `dev` | Everything on the 3B (cheapest, fastest) | Day-to-day iteration |
| `local` | Reasoning checks + hard replies on the 14B; no cloud spend | Verifying reasoning quality |
| `full` | The true 2x2: adds the Claude cloud lane (needs `ANTHROPIC_API_KEY`) | Final/most capable runs |

---

## Ports and URLs

| Service | URL |
|---|---|
| Frontend (Next.js) | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API interactive docs (Swagger) | http://localhost:8000/docs |
| Weaviate (vector DB) | http://localhost:8080 |
| Postgres | localhost:5432 (`support` / `support`, db `tickets`) |

---

## Common gotchas

- **`role "support" does not exist` on startup.** A stale Postgres data volume, or another Postgres already
  on port 5432. Fix: stop the other Postgres (macOS: `brew services stop postgresql@16`), or wipe the volume
  and re-init: `docker compose down -v && docker compose up -d` (note: `-v` also wipes Weaviate, so re-run
  `seed_kb.py` after).
- **"malformed intake" / ticket not saved.** `source` must be one of `chat`, `form`, `email`, `voice_transcript`.
  Any other value is rejected by design.
- **Submitting a ticket feels slow / frozen.** Creating a ticket runs the full LLM pipeline (several seconds).
  That is expected; don't double-submit.
- **App won't start, `KeyError` on a lane URL.** A required `*_LANE_URL` / `*_LANE_TOKEN` is missing from `.env`.
- **Empty retrieval / no KB matches.** Run `uv run python seed_kb.py` (the collection is empty after a `down -v`).

---

## Repo layout

```
api.py              FastAPI backend (create/list/approve/reject/edit)
demo.py             CLI demo over sample tickets
seed_kb.py          seed the Weaviate knowledge base
docker-compose.yml  Postgres + Weaviate
policy.md           compliance rules the review agent enforces
app/
  graph.py          the LangGraph pipeline (all agent nodes + wiring)
  state.py          the shared State + Ticket types
  intake.py         normalize a raw payload into a canonical Ticket
  router.py         model-lane routing (3B / 14B / Claude) + MODEL_TIER
  kb.py, embed.py   Weaviate knowledge base + embeddings
  store.py          Postgres system of record
  pii.py            PII scanner (sensitivity + outbound-leak check)
  roster.py         synthetic support roster (assignee routing)
  audit.py          hash-chain tamper-evident audit trail
  adapters.py       ticketing-system adapter seam (Zendesk/Jira/ServiceNow shape)
modal_lane/
  llm_service.py    the open-weight model service deployed to Modal
frontend/           Next.js reviewer UI (App Router, Tailwind, TypeScript)
```
