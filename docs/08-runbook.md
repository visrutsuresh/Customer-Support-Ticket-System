# 08. Runbook

**Version 1, 2026-07-28.** Operating the system on a developer machine. First-time installation is in the repository `README.md`; this document is for running, recovering and diagnosing.

## 1. Daily start

```bash
docker compose up -d                    # Postgres + Weaviate
uv run uvicorn api:app --reload         # API on :8000
cd frontend && npm run dev              # web app on :3000
```

Behind a proxy that intercepts TLS, set the exclusions **before** the backend and before any seed script, or the vector database calls hang and then fail:

```bash
export NO_PROXY=127.0.0.1,localhost no_grpc_proxy=127.0.0.1,localhost
```

Stop with `Ctrl-C` in each terminal, then `docker compose down` (without `-v`, which would delete the data).

## 2. Seeding

| Command | Effect |
|---|---|
| `uv run python seed_users.py` | Creates the staff, admin and demo customer accounts. Idempotent: existing accounts are repaired rather than duplicated, including their verified flag |
| `uv run python seed_kb.py` | Creates and fills the knowledge collection |
| `uv run python kb_import.py` | Imports the larger corpus of articles and past tickets, offline |
| `uv run python seed_data.py`, `seed_universe.py` | Synthetic customers, orders and tickets for the demo world |

After any `docker compose down -v`, all four must be run again.

## 3. Health checks

| Check | Command or address | Healthy answer |
|---|---|---|
| API alive | `GET http://localhost:8000/` | `{"status":"ok", ...}` with the active mode and tier |
| Interactive API docs | http://localhost:8000/docs | The endpoint list renders |
| Database | `docker compose ps` | Both containers up |
| Sign-in works | http://localhost:3000/login | A seeded staff account reaches the workspace |
| Model lane warm | Submit one ticket and watch the log | `[pipeline] T-xxxx done on attempt 1` |

## 4. Routine operations

| Task | How |
|---|---|
| Warm the GPU lane before a demo | Submit one throwaway ticket about ten minutes ahead; the first call after idle takes about a minute |
| Switch pipeline mode | Set `AGENT_MODE` and restart the API |
| Switch model tier | Set `MODEL_TIER` and restart the API |
| Pull in new mail | `POST /email/sync` as staff, or the button in the workspace |
| Pull in new Jira issues | `POST /jira/sync` as staff |
| Read the numbers | The metrics page in the workspace, or `GET /metrics` |

## 5. Incidents

### A ticket is stuck at "processing"

The pipeline runs in the background with a 180 second cap and two attempts. If both fail the ticket is set to `error`, which is visible in the queue. Check the API log for `[pipeline] ... attempt N failed`. The usual cause is a cold GPU container; retry once the lane is warm by adding a customer reply, which reprocesses the ticket.

### Everything returns 401 after a restart

`AUTH_SECRET` changed, so existing cookies no longer verify. Sign in again.

### Staff cannot sign in, and the reason is not the password

Their account is not marked verified. Re-run `seed_users.py`, which repairs the flag on accounts that already exist.

### Database authentication failed on startup

`DATABASE_URL` and the compose credentials disagree. Make them match. If the volume was initialised with the old password, remove only the Postgres volume and let it re-initialise, so the knowledge base volume survives:

```bash
docker compose down
docker volume rm <project>_pgdata
docker compose up -d
```

Then re-run the seeds.

### Retrieval returns nothing

The knowledge collection is empty, usually after a volume wipe. Run `seed_kb.py` then `kb_import.py`.

### Seeding or processing hangs on the vector database

A local TLS-intercepting proxy is routing the gRPC port. Set the exclusions in section 1 in the same shell.

### Mail or Jira sync returns 502

The upstream is unreachable or the credentials are wrong. Neither blocks the rest of the system; the endpoint reports the failure rather than half-importing.

## 6. Before a demo, in order

1. `git pull`, then `uv sync` and `npm install` if either lock file moved.
2. Start the databases, the API and the web app.
3. Run the seeds if this machine is fresh.
4. Warm the model lane with one throwaway ticket.
5. Sign in as staff and confirm the queue renders and the metrics page has numbers.
6. Keep `AGENT_MODE=deterministic` unless the autonomous behaviour is what is being shown: it is several times faster and does not wander.

## 7. What is deliberately not here

No monitoring, alerting, log aggregation, scheduled backup, or on-call procedure. This is a single-machine demonstration system, see [11-nfr.md](11-nfr.md).
