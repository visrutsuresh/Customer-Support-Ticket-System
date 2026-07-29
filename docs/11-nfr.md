# 11. Non-Functional Requirements

**Version 1, 2026-07-28.** Targets with numbers, and what is actually measured against them.

## 1. Performance

| Property | Target | Measured | Source |
|---|---|---|---|
| Ticket handling, fixed pipeline | seconds, not minutes | mean 18s, range 16 to 23 | benchmark, warm lane |
| Ticket handling, autonomous pipeline | allowed to be slower | mean 90s, range 41 to 132 | benchmark, warm lane |
| First call after the GPU lane goes idle | under two minutes | roughly 60 to 90 seconds | live probes |
| Hard ceiling per run | 180 seconds, two attempts, then a visible error | enforced in code | `PIPELINE_TIMEOUT_S` |
| Interface responsiveness | the submit screen never waits on a model | met by design: the ticket is saved and the pipeline runs in the background | `POST /tickets` |

Latency is recorded per ticket and shown on the dashboard split into warm and cold runs, so the GPU cold-start cost stays visible rather than averaged away.

## 2. Scale

| Property | Target |
|---|---|
| Concurrent users | one, a single developer machine |
| Ticket volume | low hundreds, synthetic |
| Knowledge corpus | a few hundred entries |
| Concurrency inside the pipeline | one ticket at a time per run; parallel model calls are deliberately serialised on the single GPU container |

This is a demonstration system. High availability, horizontal scaling, and queueing under load are explicitly out of scope.

## 3. Availability

There is no availability target. Everything runs on one machine, both data stores are Docker volumes, and there is no failover. The relevant guarantee is narrower and is met: **no single failure loses a ticket or leaves it stuck**. A failed run marks the ticket in error, a cancelled run cannot resurrect an archived ticket, and archiving happens before the knowledge write-back so a retrieval failure cannot strand a resolution.

## 4. Privacy and security targets

| Requirement | Status |
|---|---|
| A sensitive ticket never reaches a third-party API | Met by construction: the lane decision precedes every model call and the private lane has no code path to a cloud provider |
| No fallback from the private lane to the cloud when it is down | Met. The failure surfaces as an error rather than a silent downgrade |
| Outbound replies carry no personal data | Enforced by a scan of the draft during review |
| Only active accounts hold a session | Met. Email verification was removed 2026-07-29 (ADR-014), so an address is asserted, not proved |
| Customers see only their own tickets, staff never see raw archives | Met |

Full detail in [12-security-review.md](12-security-review.md) and [13-privacy-and-data-handling.md](13-privacy-and-data-handling.md).

## 5. Auditability

Every pipeline step appends to a hash chain stored with the ticket, and the whole state is persisted as produced. Editing any past entry breaks every hash after it and is detectable. The chain proves tampering; it does not prevent it, and there is no external notarisation.

## 6. Maintainability and reuse

The module boundaries were designed so the skeleton could be reused, and that has been proved twice: both the legal-review and governance systems were built from this shape. The cost of that reuse by copying is measured, and the plan to replace it with a shared package is recorded in the planning repository's core-sharing decision.

## 7. Cost

The GPU lane bills per wake rather than per token, so the practical unit is a warm window, not a request. A hard spend cap is set on the platform, measurement runs are batched into one window, and the dashboard shows an estimated GPU cost per ticket. Cloud token cost is not tracked, so full-tier runs under-report total cost. That gap is known and named.

## 8. Compliance and data residency

Not applicable at this stage: all data is synthetic, nothing is regulated, and there is no production deployment. The privacy lane exists so that the design does not have to change when real data appears.
