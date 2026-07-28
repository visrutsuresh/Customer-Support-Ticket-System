# 19. Handover

**Version 1, 2026-07-28.** What the next owner needs, in the order they will need it.

## 1. Get it running

Follow the repository `README.md` for first-time installation, then [08-runbook.md](08-runbook.md) for daily operation. You need Docker, the Python runner `uv`, Node, and an environment file built from `.env.example`. The two model endpoints and their shared token are the only values you cannot invent locally; without them the API refuses to start.

Expect this order: start the containers, run the four seed scripts, start the API, start the web app, sign in with a seeded staff account.

## 2. Read these three first

1. [02-hld.md](02-hld.md) for the shape of the system.
2. [03-lld.md](03-lld.md) section 3 and 4, the pipeline and the decision rule, which is where all the judgement lives.
3. [06-adr-log.md](06-adr-log.md) for why things are the way they are, especially the two-pipeline decision and the privacy lane.

## 3. The five things that will surprise you

1. **There are two pipelines**, chosen by an environment variable, and any change to pipeline internals has to be made in both in the same sitting. Forgetting this is how a feature has previously shipped in one mode only.
2. **The two pipelines disagree about capitalisation.** The fixed one lower-cases every classification field; the autonomous one returns the model's raw wording. Any code reading a classification must lower-case first, or it will work in exactly one mode.
3. **The model lane sleeps.** The first call after an idle period takes about a minute, and it costs real money to wake. Batch anything paid into one warm window.
4. **The whole pipeline state is stored as one JSON column.** Adding a field to the state needs no migration; the queue's filter columns are the only normalised ones.
5. **Corporate security tooling on a Windows machine interferes twice:** a local proxy hijacks the vector database's gRPC port unless localhost is excluded, and a content filter rewrites credential-shaped strings, so configuration files should be checked after any bulk edit.

## 4. Where the important logic lives

| Question | File |
|---|---|
| Which model handles this ticket | `app/router.py` |
| Send automatically or ask a human | `decide()` in `app/graph.py`, with the bar in `app/state.py` |
| What counts as sensitive | `detect_sensitivity()` in `app/graph.py` and `app/pii.py` |
| What the compliance gate enforces | `review()` in `app/graph.py` and `policy.md` |
| What happens after a run finishes | `_process()` and `_auto_dispatch()` in `api.py` |
| Everything touching the database | `app/store.py` |

## 5. Open work, in the order worth doing

1. **Priority classification**, correct on two thirds of the labelled set, with two critical tickets scored merely high. Tightening the priority definitions in the classify prompt and re-running `eval.py --classify` is the cheapest measurable win available. (The labelled set itself now exists: `data/eval_set.jsonl` plus `eval.py`.)
2. **The two missing safety tests:** one proving the audit chain detects tampering, one asserting a sensitive ticket never reaches the cloud lane.
3. **Escalate rather than error when the private lane is down.** Today a lane outage ends in an error status, which meets the privacy rule but not the intent.
4. **An endpoint that accepts a transcript**, so the third intake format is reachable.
5. **Track cloud token cost**, so full-tier runs report their true cost.
6. **Extract the shared core**, per the decision recorded in the planning repository. Deliberately scheduled after the current deadline.

## 6. Operational cautions

- Never run `docker compose down -v` unless you intend to lose the data and re-seed.
- Changing the authentication secret signs everyone out and invalidates outstanding verification links.
- The database password in the environment file and the one in the compose file must agree; Postgres only applies credentials when it first initialises an empty volume.
- Seeded development credentials are in the `README.md` and must be rotated before the system is reachable by anyone else.

## 7. Related repositories

Two sibling systems were built from this skeleton: a legal contract review system and an enterprise AI governance system. They share several modules by copy, which is measured and planned for in the core-sharing decision in the planning repository. A fix made in a shared-looking module here is worth checking in both of them.
