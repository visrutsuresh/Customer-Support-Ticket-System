# 06. Decision Log (Architecture Decision Records)

**Version 1, 2026-07-28.** One record per decision that would be expensive to reverse. Each states the situation, the options weighed, the choice, and what it costs.

---

## ADR-001. Wire the agents with an explicit state graph

**Context.** Several AI steps must run in order, with branches, and the result must be inspectable afterwards.
**Options.** A chain of function calls; a single large prompt doing everything; LangGraph nodes and edges.
**Decision.** LangGraph, with each step a named node and each branch an explicit conditional edge.
**Consequences.** The flow can be drawn, replayed and audited, and each node is testable alone. The cost is a framework dependency and its state-merging rules to learn.

---

## ADR-002. Keep two pipelines, not one

**Context.** The brief asks for autonomous agents, but autonomous runs take 60 to 140 seconds per ticket and can wander, which is dangerous in a live demo.
**Options.** Ship only the autonomous pipeline; ship only the fixed one; keep both behind a switch.
**Decision.** Both, selected by `AGENT_MODE`. The fixed pipeline is the demo safety net and the control arm for measurement.
**Consequences.** Every change touching pipeline internals must be made twice, in the same sitting. In exchange there is a real A/B baseline: escalation dropped from 17 percent (fixed) to about 8 percent (autonomous, after tool work), measured on the same twelve tickets.

---

## ADR-003. Decide sensitivity before any model call, and never fall back to cloud

**Context.** Tickets can carry personal, financial, medical or legal detail. A third-party API must never see those.
**Options.** Send everything to the cloud and redact; decide after the first call; decide locally first.
**Decision.** A pattern scan plus a category check plus a local model judgement run first, and the routing decision is made from their result. The private lane has no code path to a cloud provider.
**Consequences.** A private-lane outage cannot be papered over: the ticket errors rather than leaking. That is the correct failure, though today it stops at an error status instead of escalating to a person, which is a known gap.

---

## ADR-004. Route models on a two-by-two grid rather than by a model deciding

**Context.** Four model choices exist: small and large open models on the private lane, cheap and strong cloud models.
**Options.** Let an agent choose its own model; always use the strongest; a fixed table.
**Decision.** Plain code maps (sensitivity, difficulty) to a model, capped by a `MODEL_TIER` switch so day-to-day work runs on the cheapest lane.
**Consequences.** Cost and privacy are predictable and provable. The grid is hardcoded rather than configuration, so tuning means a code edit.

---

## ADR-005. Run the private lane on serverless GPU

**Context.** Sensitive tickets need an open-weight model, and neither laptop has a usable GPU. Corporate policy blocks the vendor's command-line tool on the work machine.
**Options.** A cloud provider with a privacy tier; a local model on the laptop; serverless GPU behind a web endpoint.
**Decision.** Serverless GPU, deployed from the personal machine, reached by both machines as a plain HTTPS endpoint protected by a shared secret, with a hard spend cap.
**Consequences.** The work machine never needs the blocked tool. The costs are cold starts of roughly a minute and real money per wake, which is why measurement runs are batched.

---

## ADR-006. Store the whole pipeline state as one JSON column

**Context.** The state shape was still moving while the schema had to be stable.
**Options.** Normalise every field into columns; store the state as JSON; both.
**Decision.** Both, in effect: the fields the queue filters on are real columns, and the entire state, including the audit chain and the thread, is one JSON column.
**Consequences.** Schema changes stopped being migrations. The cost is that deep queries go through JSON operators, which is why the metrics query reads a few fields that way.

---

## ADR-007. Prove the audit trail with a hash chain, not a database of logs

**Context.** The record must show tampering, without new infrastructure.
**Options.** Append-only table with permissions; a blockchain; a hash chain in the state.
**Decision.** Each entry stores a hash of the previous entry, so editing any past entry breaks every hash after it, and a verifier returns the first broken index.
**Consequences.** Tamper evidence for about twenty-five lines of code and no new services. It proves tampering, it does not prevent it.

---

## ADR-008. Learn by indexing resolutions, not by fine-tuning

**Context.** The system should get better at answering repeat questions.
**Options.** Fine-tune a model periodically; index resolved tickets as retrievable precedent.
**Decision.** Index-back on resolve, quality-gated, tagged as a ticket source.
**Consequences.** Improvement is immediate and reversible, with no training pipeline. Quality now depends on the retrieval floor rather than on model weights.

---

## ADR-009. Write back to the knowledge base on resolve, not on auto-send

**Context.** An auto-sent reply is a guess until the customer accepts it.
**Decision.** Only the resolve action files a resolution back, and only when an agent reply actually exists.
**Consequences.** The knowledge base stays clean of unconfirmed answers. The cost is fewer entries.

---

## ADR-010. Hard-gate sign-in on a verified email address

**Context.** Open signup let anyone claim any address, and a ticket's owner is identified by their address.
**Options.** Verify but let unverified users look around; gate reading and filing; gate sign-in itself.
**Decision.** Gate sign-in. An account cannot hold a session until the inbox is proved. A failed verification email never blocks signup, and a resend endpoint answers the same way whether or not the address exists, so it cannot be used to discover accounts.
**Consequences.** Seeded accounts must be marked verified by the seeder, which was found the hard way: the first version of the gate locked out every seeded staff account.

---

## ADR-011. Three repositories sharing a core package, extraction deferred

**Context.** The legal and governance systems were copy-forked from this one, so several modules exist three times.
**Decision.** Keep three repositories and share through one installable `core` package. The extraction is scheduled after the current deadline.
**Consequences.** Documented in full, with the measured duplication, in `Core-Sharing-Decision.md` in the planning repository.
