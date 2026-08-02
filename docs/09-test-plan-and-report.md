# 09. Test Plan and Report

**Version 1, 2026-07-28.**

## 1. Strategy

Three layers, in increasing cost:

| Layer | Cost | What it proves |
|---|---|---|
| Automated tests (`tests/`) | free, no model calls, no database | The gates: who may do what, what a resolved ticket refuses, what approve actually sends |
| Live probes against a running instance | free | The auth chain end to end, through real HTTP |
| Benchmark runs (`bench.py`) | GPU money | Behaviour of the whole pipeline on a fixed ticket set, both modes. See [10-benchmark-report.md](10-benchmark-report.md) |
| Labelled evaluation (`eval.py`) | free, or one model call per ticket | Whether the decisions were **right**: classification accuracy and retrieval hit rate against 30 labelled tickets |

The automated layer runs with the application driven directly, with the authentication dependency and the store replaced, so no Postgres, no vector database and no model are needed. That is what keeps it free and fast.

## 2. Running them

```bash
uv run --with pytest --with httpx python -m pytest tests/ -q
```

`pytest` and `httpx` are not project dependencies, hence `--with`.

## 3. What is covered today

| Test | Pins |
|---|---|
| `test_approve_escalation_sends_nothing` | Approving an escalation with no draft sends nothing, the historical bug it was written for |
| `test_approve_draft_sends_and_hands_ball_to_customer` | Approving a real draft adds it to the thread, dispatches it, and moves the ticket to awaiting-customer |
| `test_approve_resolved_is_locked` | A resolved ticket refuses further action with 409 |
| `test_customer_can_file` | A customer can create a ticket, and their identity comes from the account rather than the form |
| `test_archive_scope_is_admin_only` | Archive browsing is 403 for staff |
| `test_staff_reopen_clears_the_doomed_mark` | Reopening cancels the resolve-time cancellation, so the ticket can process again |
| `test_reopen_refuses_non_archived` | Reopening a live ticket is 409 |
| `test_customer_cannot_reopen_someone_elses_ticket` | Ownership is enforced on reopen |
| `test_customer_history_needs_a_real_ticket` | The history panel refuses an unknown ticket |
| `test_window_blocks_then_recovers` | The rate limiter refuses the call over the cap with 429, then allows again once the window has passed |
| `test_keys_are_independent` | One account's spent rate budget never affects another's |
| `test_assign_and_clear` | Manual assignment sets a trimmed assignee and null clears it back to unassigned |
| `test_assign_missing_ticket_404s` | Assigning on an unknown ticket refuses with 404 |
| `test_unknown_sort_rejected` | A sort key outside the whitelist is refused with 422 and never reaches SQL |
| `test_sla_sort_reaches_store_as_the_whitelisted_key` | The `sla` sort arrives at the store as the whitelisted key, not as user text |

**Last run: 2026-08-02, 15 passed, 0 failed, 0.7 seconds.**

## 4. The auth probe, and why it no longer applies

A seventeen-check live probe ran on 2026-07-28 against the running API, with mail sending swapped for a recorder. It covered the email verification chain end to end: signup starting unverified, an unverified sign-in refused with its own distinct reason, the resend endpoint answering identically for real and unknown addresses so it could not be used to discover accounts, the link built correctly, the token accepted once and refused on replay or tampering, and a verified customer reaching their own requests but not the staff queue. It caught a real defect at the time: the gate initially locked out every seeded staff account.

**All of that was removed on 2026-07-29 (ADR-014), so the probe no longer describes this system.** It is recorded here rather than deleted because it is the evidence for what the removal gave up. What still holds from the same session: a wrong password returns the generic bad-credentials reason, open signup cannot mint a staff role, and seeded staff sign in and reach the queue.

## 5. Known gaps

These are named rather than hidden, and are the honest answer if a reviewer asks what is untested.

| Gap | Why it matters |
|---|---|
| No unit tests for the model router or the decision rule | Those two functions encode all the judgement in the system |
| No golden-file tests for intake parsing | A parser change could silently alter the canonical ticket |
| No mocked-model contract tests per agent | Agent output shape changes would only surface in a live run |
| No end-to-end test with a fake model | The full graph is only exercised by paid runs |
| No tamper test on the audit chain | The verifier exists but nothing proves it fires |
| No test asserting sensitive tickets never reach the cloud lane | This is the system's strongest privacy claim and it rests on reading the router, not on a test |
| ~~No labelled evaluation set~~ | **Closed 2026-07-28:** `data/eval_set.jsonl` holds 30 labelled tickets and `eval.py` scores them. The retrieval half is free to re-run at any time; the classification half costs one model call per ticket. Results in [10-benchmark-report.md](10-benchmark-report.md) section 4 |

The first six are a few hours of free work each. The last needs data creation and is the largest single item.

## 6. Test data

Everything is synthetic: seeded customers, orders, knowledge articles, and a twelve-ticket benchmark batch. No real customer data has ever been in the system.
