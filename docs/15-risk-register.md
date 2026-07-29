# 15. Risk Register

**Version 1, 2026-07-28.** Live risks only. A risk that has been closed is recorded as closed rather than deleted, because the mitigation is often the interesting part.

Likelihood and impact are low, medium or high. Exposure is the pair read together.

## Open risks

| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R-1 | The GPU lane is cold or unavailable during a live demonstration, so tickets take minutes or fail | Medium | High | Warm the lane about ten minutes before, run the fixed pipeline rather than the autonomous one, and keep a recorded walkthrough as a fallback | Build owner |
| R-2 | GPU spend exhausts the budget mid-work | Medium | Medium | A hard cap on the platform, batched measurement runs, and a per-ticket cost estimate on the dashboard | Build owner |
| R-3 | Priority is judged correctly about three quarters of the time | Medium | Low | Measured on the labelled set, and improved from 66.7 to 73.3 percent by rewriting the priority definitions. All three critical tickets now rate critical, and the residual errors over-rate rather than under-rate. Escalation never depends on priority alone | Build owner |
| R-4 | Sensitivity detection misjudges a novel case, and a sensitive ticket is drafted on the cloud lane in full tier | Low | High | Three independent checks, any one of which is enough; the default tier keeps everything on the private lane anyway. A dedicated test asserting this is still missing | Build owner |
| R-5 | Prompt injection through ticket text steers a reply or a tool call | Medium | Medium | Write tools need a confirmation code, the compliance gate inspects every draft, and anything not auto-sent reaches a human. Not systematically tested | Build owner |
| R-6 | A model output shape changes and a parser silently degrades | Medium | Medium | Every parser is defensive and failures are visible as errors rather than silent. Mocked contract tests per agent do not yet exist | Build owner |
| R-7 | Duplicated code across the three systems means a bug fixed here is left unfixed there | Medium | Medium | The duplication is measured and the shared-package plan is written; two such bugs have already occurred and were fixed in both places | Build owner |
| R-8 | Corporate security tooling on the work machine breaks local development in new ways | Medium | Low | Known workarounds are documented: exclude localhost from the proxy, and never write credential-shaped strings through the editor | Build owner |
| R-9 | Documentation drifts from the code as the last week of changes land | Medium | Low | Every document in this set is dated and states what it was checked against; the traceability matrix is the piece to re-check first | Build owner |
| R-10 | No rate limiting on sign-in or ticket creation | Low here, High in production | Medium | Accepted for a single-machine demonstration, named as a blocker for real use in the security review | Build owner |
| R-11 | Anyone can sign up claiming an address they do not own, and read the tickets filed from it | Low here, High in production | High | **Currently unmitigated by choice.** This was closed on 2026-07-28 by gating sign-in on a verified inbox, and reopened on 2026-07-29 when that gate was removed (ADR-014). Accepted for a synthetic, non-public demonstration; ADR-010 records the design to restore before any real use | Build owner |

## Closed risks

| # | Risk | How it closed |
|---|---|---|
| C-1 | The private model lane could not be hosted anywhere available | Serverless GPU, deployed from the personal machine, reachable from both as an HTTPS endpoint |
| C-2 | Cold starts exceeded the platform timeout, so the lane could never answer | Timeout stack raised in the right order, and later a smaller model chosen that loads in about a minute |
| C-3 | Parallel agents woke a second GPU container and burned the budget | The lane is pinned to a single container and calls are serialised client-side |
| C-4 | Anyone could sign up claiming any address and read that person's tickets | Closed 2026-07-28 by hard-gating sign-in on a verified inbox. **REOPENED 2026-07-29** when that gate was removed by decision; it is now tracked as R-11 above |
| C-5 | The verification gate locked out every seeded staff account | Fixed 2026-07-28, then made moot 2026-07-29 when the gate was removed |
| C-6 | Approving an escalated ticket sent nothing to the customer | Fixed, and pinned by the first test in the suite |
| C-7 | The repository had no automated tests at all | A gate-focused suite exists and runs free in about two seconds |
| C-8 | Quality claims could not be defended, because no labelled evaluation set existed | 30 labelled tickets plus `eval.py`, 2026-07-28. Classification accuracy and retrieval hit rate are now numbers, and the retrieval half re-runs for free |
