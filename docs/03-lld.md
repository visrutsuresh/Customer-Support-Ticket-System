# 03. Low-Level Design

**Version 1, 2026-07-28.** What is inside each box of [02-hld.md](02-hld.md).

## 1. Module map

| Module | Lines | Responsibility |
|---|---|---|
| `api.py` | ~690 | Endpoints, auth wiring, background processing, channel dispatch |
| `app/graph.py` | ~470 | Deterministic pipeline: ten nodes, two conditional edges |
| `app/orchestrator.py` | ~190 | Autonomous pipeline: same nodes as thin wrappers plus a dynamic router |
| `app/agents.py` | ~295 | Five ReAct agents (classify, retrieve, generate, review, learn) |
| `app/tools.py` | ~130 | Tool registry the autonomous agents call |
| `app/router.py` | ~95 | Model choice by lane and difficulty, capped by `MODEL_TIER` |
| `app/store.py` | ~710 | All Postgres access and the metrics query |
| `app/kb.py`, `app/embed.py` | ~46 | Vector search, index-back, local embeddings |
| `app/state.py` | ~65 | `Ticket` model, `State` shape, confidence policy |
| `app/intake.py` | ~26 | Raw payload to canonical ticket |
| `app/pii.py` | ~36 | Pattern scan for personal data, including a card checksum |
| `app/roster.py` | ~27 | Assignee selection on escalation |
| `app/audit.py` | ~26 | Hash-chain reducer and verifier |
| `app/users.py` | ~101 | Accounts, roles, cookie sessions, verification |
| `app/email_channel.py`, `app/jira_channel.py`, `app/adapters.py` | ~140 | Inbound polling, outbound replies, integration seam |

## 2. The state object

One dictionary flows through the pipeline. Each node returns only its own section, and the framework merges them, so the finished object is a record of how the answer was reached.

| Key | Written by | Holds |
|---|---|---|
| `raw_input` | caller | The untouched inbound payload |
| `ticket` | `intake` | The canonical ticket (id, source, subject, body, customer, timestamp) |
| `error` | `intake` | Why the payload was rejected, if it was |
| `classification` | `classify` | category, priority, business impact, sentiment |
| `sensitivity` | `detect_sensitivity` | is_sensitive, pii_types, reason |
| `difficulty` | `score_difficulty` | simple or complex, plus a reason |
| `routing` | `route` | lane, tier, intended model |
| `retrieval` | `retrieve` | Ranked knowledge hits with scores |
| `draft` | `generate` | reply, kind (answer/question/escalate), confidence |
| `compliance` | `review` | verdict and issues |
| `review_count` | `review` | Caps the regeneration retry |
| `decision` | `decide` | auto_send or escalate, reason, assignee |
| `messages` | API layer | The conversation, roles customer / agent / internal |
| `audit` | every node | The hash chain, append-only |

`audit` uses an append-only reducer, so a node cannot overwrite history even by accident.

## 3. Deterministic pipeline, node by node

```
START -> intake -+-> classify -> detect_sensitivity -> score_difficulty -> route
                 |        -> retrieve -> generate -> review -+-> (fail, first time) generate
                 |                                           +-> decide -> learn -> END
                 +-> (malformed) decide
```

| Node | Model call | What it does | Failure behaviour |
|---|---|---|---|
| `intake` | no | Normalises the payload; rejects an unknown source | Sets `error`, jumps straight to `decide` |
| `classify` | yes | Four labels from a definition-led prompt, lower-cased | A parse failure raises and the run is retried by the caller |
| `detect_sensitivity` | yes | Pattern scan, plus a sensitive-category check, plus a model judgement; any one of them makes it sensitive | If the model output will not parse, the pattern scan and category check still stand |
| `score_difficulty` | yes | simple or complex | as classify |
| `route` | no | Lane from sensitivity, tier from difficulty, model from the 2x2 grid | Pure code, cannot fail |
| `retrieve` | no | Vector search, hits below the relevance floor of 60 are dropped | An empty list is a valid result |
| `generate` | yes | Drafts the reply; the first line is a control line carrying kind and confidence | No control line means the whole output is treated as an answer |
| `review` | yes | Placeholder check, sign-off check, outbound personal-data scan, then a policy judgement | Skipped when there is no draft |
| `decide` | no | The escalate-or-send rule below | Pure code |
| `learn` | no | Deliberately does nothing; knowledge write-back happens on resolve | n/a |

## 4. The decision rule

In order, first match wins:

1. Malformed intake, compliance failure, critical priority, or the agent declaring it needs a human, all escalate.
2. A real answer that passed review, whose **grounded confidence** clears the bar, auto-sends.
3. The same answer below the bar escalates with the numbers in the reason.
4. A question back to the customer auto-sends.
5. Anything else escalates.

Grounded confidence is the average of the model's self-reported confidence and the top retrieval score, so both must be high. The bar is 85 for money categories or high priority, 60 otherwise. On escalation an assignee is chosen from the roster by category and priority.

These are heuristics, not calibrated probabilities. Calibrating them needs the labelled set named in [01-requirements.md](01-requirements.md).

## 5. Autonomous pipeline

The same stations exist, but each is a ReAct agent: it thinks, optionally calls a tool, reads the result, and repeats up to eight steps before it must answer. An orchestrator node decides which station runs next rather than following fixed edges.

The twelve tools are read-mostly lookups (customer record, order, orders by email, billing history, subscription, account status, past tickets, service status, refund eligibility, knowledge search) plus two write actions (request a refund, cancel a subscription) which require a confirmation code derived from the ticket id.

Casing trap worth knowing: the deterministic path lower-cases every classification field, the autonomous path returns the model's raw JSON, so any code reading a classification must lower-case it first.

## 6. Cross-cutting behaviour in the API layer

- **Background processing with a cap.** The pipeline runs in a thread with a 180 second limit and two attempts. A daemon thread means a hung model call is abandoned rather than blocking shutdown. Both attempts failing sets the ticket to `error`.
- **Cancellation.** Resolving a ticket adds it to a cancelled set, so an in-flight run stops writing rather than resurrecting an archived ticket.
- **Auto-tagging.** After every run, tags are derived from the classification, at the shared layer, so both pipelines get it.
- **Human request override.** A message asking for a person parks the ticket for review with no model call at all.
- **Channel dispatch.** A reply leaves through the channel the ticket arrived on: email over SMTP, Jira as a comment, otherwise in-app only.
- **Verification gate.** Every endpoint depends on an active, verified account; customers additionally may only touch tickets born from their own address.

## 7. Error handling summary

| Failure | Behaviour |
|---|---|
| Malformed payload | Rejected at intake, escalated as "malformed intake" |
| Model call times out | Second attempt, then ticket marked `error` |
| Knowledge base unreachable | Retrieval raises, the run fails and retries; a reviewer signing off is never blocked by it |
| Email or Jira send fails | Recorded in the response as a delivery string; the reply still stands in the thread |
| Verification email fails | Logged, signup still succeeds, the user can request a fresh link |
