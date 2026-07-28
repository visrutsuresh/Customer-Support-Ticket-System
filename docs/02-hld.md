# 02. High-Level Design

**Version 1, 2026-07-28.**

## 1. The shape of the system

```
   Customer                      Support staff
      |                                |
      v                                v
+-----------------------------------------------+
|  Next.js web app (frontend/, port 3000)        |
|  customer portal  |  staff workspace  | metrics|
+-----------------------------------------------+
                    | HTTP + cookie session
                    v
+-----------------------------------------------+
|  FastAPI backend (api.py, port 8000)           |
|  auth, ticket endpoints, background processing |
+-----------------------------------------------+
     |               |                |
     v               v                v
+---------+   +-------------+   +--------------+
| Agent   |   | Postgres    |   | Weaviate     |
| pipeline|   | system of   |   | knowledge    |
| (LangGraph) | record      |   | base (vector)|
+---------+   +-------------+   +--------------+
     |
     v
+-----------------------------------------------+
|  Model router (app/router.py)                  |
|  private lane: 3B / 14B on Modal GPU           |
|  cloud lane:   Claude Haiku / Sonnet           |
+-----------------------------------------------+
```

Inbound channels other than the web form: an email mailbox polled over IMAP, and a Jira project polled for new issues. Both create tickets through the same pipeline.

## 2. Components

| Component | Where | Responsibility |
|---|---|---|
| Web app | `frontend/` | Customer portal (file a request, read the thread), staff workspace (queue, review, approve/reject/edit), metrics dashboard |
| API | `api.py` | Authentication, ticket lifecycle endpoints, background pipeline runs, channel dispatch |
| Deterministic pipeline | `app/graph.py` | Fixed ten-node LangGraph flow, the demo safety net and the A/B baseline |
| Autonomous pipeline | `app/orchestrator.py`, `app/agents.py` | Five ReAct agents with a twelve-tool universe and a dynamic router node |
| Model router | `app/router.py` | Chooses the model from lane and difficulty, caps it by `MODEL_TIER` |
| System of record | `app/store.py` on Postgres | Tickets, threads, tags, links, templates, attachments, metrics |
| Knowledge base | `app/kb.py` on Weaviate | Article and past-resolution retrieval by meaning, plus index-back on resolve |
| Audit chain | `app/audit.py` | Hash chain over pipeline steps |
| Channels | `app/email_channel.py`, `app/jira_channel.py`, `app/adapters.py` | Inbound polling and outbound replies |

## 3. The two pipelines

Both are kept, selected by the `AGENT_MODE` environment variable.

- **deterministic** (`app/graph.py`): a fixed sequence of nodes. Fast, predictable, the safety net for a live demo and the control arm for measurement.
- **autonomous** (`app/orchestrator.py` + `app/agents.py`): five ReAct agents that choose tools and steps themselves, with an orchestrator node deciding what runs next. Slower and more variable, but it is the agentic behaviour the brief asks for.

Cross-cutting features are built at the shared layer (`api.py` handlers, `app/store.py`) so both modes inherit them. Anything touching pipeline internals is changed in both places in the same edit.

## 4. Request flow, one ticket

1. A customer submits a request. The API writes a pending row immediately and returns a ticket id, so the screen never blocks on a model.
2. A background task runs the pipeline under a 180 second cap, with a second attempt if the first times out (a cold GPU container is the usual cause).
3. The pipeline classifies, checks sensitivity, scores difficulty, picks the lane and model, retrieves knowledge, drafts, reviews against policy, and decides.
4. The decision is either auto-send (the reply leaves through the channel the ticket arrived on) or escalate (a staff member is named, and the customer is told a human is coming).
5. Staff approve, edit, or reject in the workspace. Resolving the ticket archives it and files the resolution back into the knowledge base as precedent.

## 5. Technology choices

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python + FastAPI | Mandated stack; async endpoints with background tasks fit the long-running pipeline |
| Agent wiring | LangGraph | Explicit nodes and conditional edges, so the flow is inspectable rather than implicit |
| Vector store | Weaviate | Mandated stack; runs locally in Docker with no cloud account |
| Relational store | Postgres | Durable system of record with JSONB for the whole pipeline state |
| Frontend | Next.js App Router, TypeScript, Tailwind | Mandated stack |
| Private model lane | Modal serverless GPU | Sensitive tickets must not reach a third-party API, and no local GPU is available |
| Cloud model lane | Claude (Haiku and Sonnet) | Strong quality for non-sensitive work at low cost |

## 6. Deployment topology

Everything runs on one developer machine. Postgres and Weaviate run in Docker (`docker-compose.yml`). The two model lanes are remote HTTPS endpoints. There is no clustering, no load balancer, and no separate environments; see [11-nfr.md](11-nfr.md).

| Service | Address |
|---|---|
| Web app | http://localhost:3000 |
| API | http://localhost:8000 (interactive docs at `/docs`) |
| Weaviate | http://localhost:8080, gRPC 50051 |
| Postgres | localhost:5432, database `tickets` |

## 7. Design principles held throughout

- **The human stays in the loop where it matters.** Auto-send is allowed only for a grounded, policy-passing, high-confidence answer; everything else is a person's decision.
- **Nothing sensitive leaves the building.** The lane decision is made before any model call, and the private lane has no path to a cloud provider.
- **Accumulate, do not overwrite.** Each node adds its own section to the state, so the finished state is the record of how the answer was reached.
- **Fail visibly.** A timed-out or crashed run marks the ticket in an error state rather than leaving it stuck in processing.
