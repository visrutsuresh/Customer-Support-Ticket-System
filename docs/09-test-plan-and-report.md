# 09. Test Plan and Report

**Version 1, 2026-07-28.**

## 1. Strategy

Three layers, in increasing cost:

| Layer | Cost | What it proves |
|---|---|---|
| Automated tests (`tests/`) | free, no model calls, no database | The gates: who may do what, what a resolved ticket refuses, what approve actually sends |
| Live probes against a running instance | free | The auth and verification chain end to end, through real HTTP |
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
| `test_unverified_customer_cannot_file` | An unverified customer cannot create a ticket |
| `test_verified_customer_can_file` | A verified one can |
| `test_archive_scope_is_admin_only` | Archive browsing is 403 for staff |
| `test_staff_reopen_clears_the_doomed_mark` | Reopening cancels the resolve-time cancellation, so the ticket can process again |
| `test_reopen_refuses_non_archived` | Reopening a live ticket is 409 |
| `test_customer_cannot_reopen_someone_elses_ticket` | Ownership is enforced on reopen |
| `test_customer_history_needs_a_real_ticket` | The history panel refuses an unknown ticket |

**Last run: 2026-07-28, 10 passed, 0 failed, 2.2 seconds.**

## 4. Live verification probe, 2026-07-28

Run against the running API with mail sending swapped for a recorder, so no email left the machine and no model was called. Seventeen checks, all passing:

- Signup returns 201, the account starts unverified, and open signup cannot mint a staff role.
- Signing in unverified is refused with its own distinct reason, and no session cookie is issued.
- A wrong password returns the generic bad-credentials reason, so the two cases stay distinguishable in the interface.
- The resend endpoint answers 202 both for a real address and for one that does not exist, so it cannot be used to discover accounts.
- The verification email builds a correct link; the endpoint accepts the token once; replaying it and tampering with it are both refused.
- After verifying, sign-in succeeds, a session cookie is issued, the account reports as verified, the customer can read their own requests, and is still refused the staff queue.
- Seeded staff sign in and reach the queue.

That probe caught a real defect: the verification gate initially locked out every seeded staff and administrator account, because the seeder only marked the flag on accounts it created. Fixed and re-verified the same day.

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
