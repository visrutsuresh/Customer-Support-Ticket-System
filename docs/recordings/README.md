# Demo recordings

Screen recordings of the live app on localhost, driven end to end: every ticket
was really filed, every pipeline run is a real model call on the private GPU
lane (Modal T4), and the email / Jira clips talk to the real mailbox and a real
Jira project. Pipeline runs and long typing are fast-forwarded 10x; the
transcripts mark those moments. Recorded with `AGENT_MODE=deterministic` (the
fixed-graph pipeline; the autonomous ReAct mode is the same product surface).

- `01-support-walkthrough.mp4` — the full walkthrough (4:25), spliced from the
  clips below in order. `01-support-walkthrough-transcript.md` has narration
  with timestamps.
- `clips/` — the individual chapters, each with its own transcript:
  - `01a-file-and-autosend` — customer files via guided chat; the pipeline
    answers and sends with no human.
  - `01b-thread-and-resolve` — customer replies on the thread, pipeline re-runs
    thread-aware; customer resolves and scores 9/10.
  - `01c-critical-refusal` — office-wide outage classified critical; drafting
    agent declines, a specialist takes over in their own words.
  - `01d-channels` — Sync email / Sync Jira: real inbox mail and a live Jira
    issue become triaged tickets.
  - `01e-desk-tools` — a compliance-failed draft is held; take-over, tags,
    internal note, attachment, macro edited and sent back out as email.
  - `01f-approve` — a correct held refund draft approved and sent in one click;
    customer receives it.
  - `01g-metrics-and-close` — the measured performance page and the resolved
    customer view.

Rebuild: `demo-media-kit/cap/` in the ascendion-internship repo (recorder
scripts `clip-01*.json`, `record2.js`, `edit.py`, `combine.py`).
