# 16. Traceability Matrix

**Version 1, 2026-07-28.** Each requirement from [01-requirements.md](01-requirements.md), the code that satisfies it, and the test that proves it. Verdicts are MET only where real code does the work.

Legend: **MET** implemented; **PARTIAL** intent covered but a stated piece is missing or done differently; **NOT MET** nothing implements it.

## Functional

| Req | Verdict | Code | Test |
|---|---|---|---|
| FR-1 form intake | MET | `frontend/src/app/new/page.tsx`, `POST /tickets`, `app/intake.py` | manual, live probe |
| FR-1 email intake | MET | `POST /email/sync`, `app/email_channel.py` | none |
| FR-1 voice transcript intake | PARTIAL | Parser branch exists in `app/intake.py`, but no endpoint supplies a transcript field, so the format is unreachable | none |
| FR-1 one canonical schema | MET | `Ticket` in `app/state.py` | none |
| FR-1 adapter interface | MET | `app/adapters.py` | none |
| FR-2 labels | MET | `classify()` in `app/graph.py`, `classify_agent` in `app/agents.py` | none |
| FR-2 difficulty | MET | `score_difficulty()` in `app/graph.py` | none |
| FR-2 classification confidence | NOT MET | Neither path returns one; only the draft carries a confidence | n/a |
| FR-2 sensitivity flag with reasons | MET | `detect_sensitivity()` in `app/graph.py` | none |
| FR-3 pattern scan | MET | `app/pii.py`, including a card checksum | none |
| FR-3 model check for context | MET | Sensitivity prompt in `app/graph.py` | none |
| FR-3 decided before any third-party call | MET | `think_model()` in `app/router.py` pins unlaned reasoning to the private lane | **missing, and it is the system's strongest claim** |
| FR-4 two-by-two router | MET | `intended_model()` in `app/router.py` | none |
| FR-4 sensitive never reaches cloud | MET | `reply_model()` and `think_model()` have no private-to-cloud path | missing |
| FR-5 ranked retrieval with scores | MET | `search()` in `app/kb.py`, floor of 60 | none |
| FR-5 corpus holds articles and past resolutions | MET | `kb_import.py`, `index_resolved()` | none |
| FR-6 draft on the routed model | MET | `generate()` in `app/graph.py` | none |
| FR-6 citations | PARTIAL | The prompt asks for the article title in prose; no structured citation field | none |
| FR-6 draft confidence | MET | Control line parsed in `generate()` | none |
| FR-7 compliance gate | MET | `review()` in `app/graph.py` plus `policy.md` | none |
| FR-7 one regeneration retry | MET | `after_review()` capped by `review_count` | none |
| FR-7 second failure escalates | MET | `decide()` | none |
| FR-8 escalation rule | PARTIAL | High priority and sensitivity raise the confidence bar rather than forcing escalation | none |
| FR-8 assignee from the roster | MET | `assign()` in `app/roster.py` | none |
| FR-8 auto-send actually sends | MET | `_auto_dispatch()` and `dispatch_reply()` in `api.py` | `test_approve_draft_sends_and_hands_ball_to_customer` covers the approve path |
| FR-9 approve, reject, edit | MET | `POST /tickets/{id}/approve|reject|edit`, workspace actions | `test_approve_escalation_sends_nothing`, `test_approve_resolved_is_locked` |
| FR-10 hash chain per step | MET | `app/audit.py`, `audit` reducer in `app/state.py` | **missing tamper test** |
| FR-10 tampering detectable | MET | `verify()` in `app/audit.py` | missing |
| FR-10 chain persisted | MET | Whole state stored as JSON in `app/store.py` | none |
| FR-11 index-back on resolve | MET | `/resolve` to `learn_agent()` to `index_resolved()` | none |

## Non-functional

| Req | Verdict | Evidence | Test |
|---|---|---|---|
| NFR-1 no cloud fallback for sensitive | PARTIAL | No leak is possible; an outage ends in an error status instead of a human escalation | missing |
| NFR-2 latency captured and shown | MET | `set_processing_seconds()` in `api.py`, dashboard tiles | none |
| NFR-3 scale | MET | Seeded corpus, single-server design | n/a |
| NFR-4 graceful failure | PARTIAL | Two attempts and a 180 second cap, visible error; no backoff, no fallback model | none |
| NFR-5 accumulate, do not overwrite | MET | `State` in `app/state.py` | none |
| NFR-6 reusable boundaries | MET | Proven by the two systems forked from this one | n/a |
| NFR-7 synthetic data, secrets outside the repo | MET | Seed scripts, ignored environment file, blank example file | n/a |

## Requirement metrics

| Metric | Verdict | Evidence |
|---|---|---|
| Classification accuracy | MET | `data/eval_set.jsonl` (30 labelled tickets) scored by `eval.py`: category 86.7%, priority 73.3%, both 66.7%, all 3 critical tickets correct |
| Retrieval hit rate | MET | Same set: 100% at top five over 22 answerable tickets, 36% at rank one, mean rank 1.86. Free to re-run |
| Auto-resolved against escalated | MET | `store.metrics()`, `bench.py`, dashboard |
| Compliance pass rate | MET | `store.metrics()`, dashboard |
| Average latency per ticket | MET | `store.metrics()`, warm and cold split |
| Cost per ticket | PARTIAL | GPU cost estimated; cloud token cost not tracked |

## Test coverage summary

A test layer exists (ten tests, free, no model calls) and covers the gates: verification, ownership, roles, the resolved lock, the reopen path, and what approve sends. The six tests named in the original plan for the rule functions, the parsers, agent contracts, the tamper check and the sensitive-never-cloud assertion **do not exist yet**. That is the honest state, and the two most valuable to add are the tamper test and the sensitive-never-cloud test, because they are the two claims a reviewer is most likely to challenge.
