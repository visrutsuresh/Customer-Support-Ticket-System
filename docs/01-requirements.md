# 01. Requirements

**Version 1, 2026-07-28.** Authoritative sources: the client requirement PDF in this folder, and the project PRD (`Track-Use-Cases/01-Customer-Support-Triage/PRD.md` in the planning repo). This document restates those requirements in the form the code is checked against. Status is measured, not aspirational: see [16-traceability-matrix.md](16-traceability-matrix.md) for the evidence behind every row.

## 1. Problem

A support team receives tickets in mixed formats. For each one a human judges urgency, searches knowledge articles and past resolutions, drafts a reply, and confirms it follows policy before sending. That is slow, inconsistent between agents, and risky on tickets carrying private customer data.

## 2. What this product is

A multi-agent assistant **for a support agent**, not an end-customer chatbot. It ingests a ticket, classifies and prioritises it, checks sensitivity locally, retrieves relevant knowledge, drafts a compliant reply, then either sends low-risk high-confidence replies automatically or escalates the rest to the right human. Every step appends to a tamper-evident audit trail, and resolved tickets are indexed back as searchable precedent.

It is also the reusable skeleton for the legal-review and AI-governance systems, so clean module boundaries are a requirement rather than a preference.

## 3. Functional requirements

| ID | Requirement | Status |
|---|---|---|
| FR-1 | Accept tickets in multiple formats (web form, email, voice transcript as text) and normalise each into one canonical ticket schema. A documented adapter interface exists for external ticketing products; no live integration is built. | MET, except the transcript format is unreachable from the API |
| FR-2 | Label each ticket with issue type, priority, business impact, sentiment, difficulty, and a sensitivity flag with reasons. | MET, except no classification confidence score |
| FR-3 | Detect sensitivity locally BEFORE any third-party API call: pattern matching for PII plus a model check for contextual sensitivity. | MET |
| FR-4 | Route the model by a 2x2 table over sensitivity and difficulty. Sensitive tickets never reach a third-party API. | MET |
| FR-5 | Retrieve relevant knowledge-base articles and past resolutions from the vector database, ranked, with source ids and scores. | MET |
| FR-6 | Draft a reply with the routed model, citing sources, with a confidence score. | MET, citation is free text not a structured field |
| FR-7 | Check the draft against policy, tone and risky language. On failure regenerate once; a second failure escalates. | MET |
| FR-8 | Decide auto-send versus escalate by plain code, and pick an assignee from the team roster on escalation. | PARTIAL, high priority and sensitivity raise the bar rather than forcing escalation |
| FR-9 | Reviewer interface: approve, reject, or edit the draft before it goes out. | MET |
| FR-10 | Append every step to a tamper-evident hash chain; editing any past entry is detectable. | MET |
| FR-11 | Index resolved tickets back into the vector database as retrievable precedent, with no model fine-tuning. | MET |

## 4. Non-functional requirements

| ID | Requirement | Target | Status |
|---|---|---|---|
| NFR-1 | Sensitive tickets are processed only on the self-hosted lane, and never fall back to cloud when that lane is down. | Hard rule, zero exceptions | PARTIAL, no leak is possible, but an outage ends in an error status instead of a human escalation |
| NFR-2 | Near-real-time handling, with latency visible in the interface. | Cloud lane seconds, private lane allowed slower | MET |
| NFR-3 | Single concurrent user, synthetic corpus in the low hundreds. | Not high-concurrency | MET |
| NFR-4 | The pipeline never crashes: a failing model call is retried and the failure is visible. | Two attempts, 180s cap | PARTIAL, no backoff and no fallback to a healthy model |
| NFR-5 | The accumulating state object is itself the audit record. | Every node auditable | MET |
| NFR-6 | Module boundaries clean enough that the skeleton is reusable by the other two systems. | Reuse proven | MET |
| NFR-7 | Synthetic data only; secrets in environment variables, never in the repository. | Zero real customer data | MET |

## 5. Out of scope

No speech to text (transcripts arrive as text). No live external ticketing integration (adapter interface only). No model fine-tuning. Not a customer-facing self-serve chatbot. Not production grade: no high availability, no high concurrency.

## 6. Known requirement gaps

**Closed 2026-07-28:** the two measurement requirements, classification accuracy and retrieval hit rate, were previously unmeasurable because no labelled evaluation set existed. `data/eval_set.jsonl` (30 labelled tickets) and `eval.py` now report them: category 86.7 percent, priority 73.3 percent, retrieval hit rate 100 percent at five and 36 percent at rank one, with all three critical tickets rated critical after a measured prompt fix. See [10-benchmark-report.md](10-benchmark-report.md) section 4.

Remaining gaps: **cost per ticket** covers GPU time but not cloud tokens; **FR-1's transcript format** has a parser but no endpoint that reaches it; and **FR-8's escalation rule** treats high priority and sensitivity as a higher confidence bar rather than a forced escalation.
