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
>
> **No lane yet? Deploy your own in ~10 minutes** (one-time, from any machine where `pip install modal` works):
> 1. `modal setup` (free account, $30/month free credit). Set a spend cap in the Modal dashboard before anything else.
> 2. Pick a random token and store it as a Modal secret the service reads: `modal secret create llm-lane-token LANE_TOKEN=<your-token>`
> 3. `modal deploy modal_lane/llm_service.py`. The deploy prints the endpoint URLs for both lanes.
> 4. Put the URLs and your token into `.env` as `PRIVATE_LANE_URL`, `REVIEW_LANE_URL` and `PRIVATE_LANE_TOKEN`. The services scale to zero when idle, so a demo costs cents.
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

# 3b. Import the larger article + past-ticket corpus (reads data/kb_seed.jsonl, works offline)
uv run python kb_import.py

# 4. Frontend deps
cd frontend
npm install
cd ..
```

---

## Sign in (seeded dev accounts)

Create the accounts once (idempotent, needs the DB up):

```bash
uv run python seed_users.py
```

| Email | Password | Role |
|---|---|---|
| `admin@nimbus.dev` | `admin-dev-password` | admin |
| `dana@nimbus.dev` | `staff-dev-password` | staff |
| `marco@nimbus.dev` | `staff-dev-password` | staff |
| `customer@nimbus.dev` | `customer-dev-password` | customer |

Rotate these before the API is reachable by anyone else.

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

### Behind a TLS-intercepting proxy (mitmproxy / corporate CA / etc.)

If your machine sets an `HTTPS_PROXY`, it will hijack the local Weaviate gRPC calls (port 50051) and
time them out, so ticket processing and the seed scripts fail. Keep the proxy for external calls but
exclude localhost. Set these before the backend **and** before `seed_kb.py` / `kb_import.py`:

PowerShell:
```powershell
$env:NO_PROXY="127.0.0.1,localhost"; $env:no_grpc_proxy="127.0.0.1,localhost"
uv run uvicorn api:app --reload
```

bash:
```bash
export NO_PROXY=127.0.0.1,localhost no_grpc_proxy=127.0.0.1,localhost
uv run uvicorn api:app --reload
```

### Command-line demo (no UI, no DB writes needed for the pipeline itself)
```bash
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
  on port 5432, or (most common) the password in `DATABASE_URL` does not match `POSTGRES_PASSWORD` in
  `docker-compose.yml`. Postgres only applies those credentials on a first-time init against an empty data
  volume, so if they drift, wiping alone will not help until the two agree. Fix: make `DATABASE_URL` match
  the compose credentials; then, only if the volume was initialized with the old password, remove just the
  Postgres volume by name and re-init (so the Weaviate KB volume survives):
  `docker compose down && docker volume rm <project>_pgdata && docker compose up -d`. If another Postgres
  is on 5432 (macOS Homebrew), stop it first: `brew services stop postgresql@16`.
- **"malformed intake" / ticket not saved.** `source` must be one of `chat`, `form`, `email`, `voice_transcript`.
  Any other value is rejected by design.
- **Submitting a ticket feels slow / frozen.** Creating a ticket runs the full LLM pipeline (several seconds).
  That is expected; don't double-submit.
- **App won't start, `KeyError` on a lane URL.** A required `*_LANE_URL` / `*_LANE_TOKEN` is missing from `.env`.
- **Empty retrieval / no KB matches.** Run `uv run python seed_kb.py` then `uv run python kb_import.py`
  (the collection is empty after a volume wipe).
- **Weaviate gRPC times out / seeding or processing hangs then fails.** An `HTTPS_PROXY` on your machine is
  routing localhost gRPC through the proxy. Exclude localhost with `NO_PROXY` / `no_grpc_proxy` as shown in
  "Behind a TLS-intercepting proxy" above.

---

## Repo layout

```
api.py              FastAPI backend (create/list/approve/reject/edit)
seed_kb.py          seed the Weaviate knowledge base
seed_templates.py   seed the canned replies behind the macro chips
docker-compose.yml  Postgres + Weaviate
policy.md           compliance rules the review agent enforces
app/
  graph.py          the LangGraph pipeline (all agent nodes + wiring)
  state.py          the shared State + Ticket types
  intake.py         normalize a raw payload into a canonical Ticket
  router.py         model-lane routing (3B / 14B / Claude) + MODEL_TIER
  kb.py, embed.py   Weaviate knowledge base + embeddings
  store.py          Postgres system of record
  customer_data.py  the seed-owned fixture tables: customers, orders, charges
  pii.py            PII scanner (sensitivity + outbound-leak check)
  roster.py         synthetic support roster (assignee routing)
  audit.py          hash-chain tamper-evident audit trail
  adapters.py       ticketing-system adapter seam, documented shape only (FR-1)
modal_lane/
  llm_service.py    the open-weight model service deployed to Modal
frontend/           Next.js reviewer UI (App Router, Tailwind, TypeScript)
```
