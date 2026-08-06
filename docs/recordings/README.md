# Demo recordings

Screen recordings of the live app on localhost, driven end to end: every ticket
was really filed, every pipeline run is a real model call on the private GPU
lane (Modal T4), and the email / Jira segments talk to the real mailbox and a
real Jira project. Pipeline runs and long typing are fast-forwarded 10x; the
transcripts mark those moments. Recorded with `AGENT_MODE=deterministic` (the
fixed-graph pipeline; the autonomous ReAct mode is the same product surface).

- `01-support-walkthrough.mp4` (4:12) — the whole desk in ONE CONTINUOUS TAKE.
  Three sign-ins only, one per role: the customer files a how-to question and
  watches the machine answer it alone, replies on the thread, resolves and
  scores it, then files a duplicate-charge ticket (drafted but HELD, money
  never sends itself) and an office-wide outage (critical, parked for a
  person). Then the staff side: the triaged queue in one slow pan, real email
  and Jira synced into tickets on camera, the outage worked end to end (tag,
  internal note, attached checklist, a hand-written reply), the held refund
  draft read and approved, the emailed ticket's auto-sent reply, and the
  measured performance page. It closes back on the customer's screen with the
  approved reply landed. `01-support-walkthrough-transcript.md` has narration
  with timestamps.
- `clips/` — the same journey as seven standalone chapters (recorded
  separately, each with its own transcript), kept for slide embeds:
  `01a-file-and-autosend`, `01b-thread-and-resolve`, `01c-critical-refusal`,
  `01d-channels`, `01e-desk-tools`, `01f-approve`, `01g-metrics-and-close`.

Every recording passed a frame-by-frame check against its narration before
shipping; the beat-by-beat log, including the retake it forced, is in
`VERIFICATION.md`.

Rebuild: `demo-media-kit/cap/` in the ascendion-internship repo (recorder
scripts `clip-01-full.json` / `clip-01*.json`, `record2.js`, `edit.py`,
`combine.py`).
