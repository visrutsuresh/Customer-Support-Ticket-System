# Recording verification log

Every take passed a frame-level gate before shipping: one frame extracted per
narration beat (`demo-media-kit/cap/check_frames.py` in the
ascendion-internship repo), each frame read against the narration line and the
database. Nothing is seeded to fake an outcome: every pipeline run is a live
model call, and outcomes that depend on the model's judgment get
outcome-neutral narration plus in-take asserts, so a run that goes the other
way aborts the take instead of shipping a lie. The recordings carry no audio;
narration lives in the transcripts, so where a live run diverged from the
planned wording the say line was corrected against the pixels before the
transcript was cut (the video is never altered).

## Single-take walkthrough — one RETAKE, then PASS

**Take 1: FAIL, caught by the frame gate + DB cross-check.** Two defects.
(1) The held refund draft's "Approve & send" is a real first-click UI bug: the
button sets the composer text and calls send in the same React tick, so send
reads the still-empty composer and silently no-ops (no API call was logged).
The ticket stayed `pending` and the closing customer scene showed no reply
while the narration claimed one had landed. (2) That run's draft asked for an
order number rather than promising the refund, contradicting the scripted
"the draft is exactly right" line. Fixed by scripting the human flow around
the bug (Edit first loads the draft into the composer on camera, then Approve
& send fires cleanly), making the draft narration outcome-neutral, and adding
an assert that the "waiting on you" hold clears. The app bug is logged for a
code fix; the demo does not paper over it, the lawyer-style two-step is real
UI.

**Take 2 (the shipped video): PASS on all 54 beats.** DB cross-check:
first ticket resolved with CSAT 9 (moved to history), duplicate-charge ticket
`approved`, outage `approved` with Dana's reply, emailed ticket `sent`
(auto-send), exactly one Jira import. Key beats:

| Beat | Frame shows | Verdict |
|---|---|---|
| Portal | Empty "Your entries", one writing line, quick starts. | PASS |
| File + auto-send | Guided chat, six-stage pipeline progress, SUPPORT answer with payment methods; no "specialist" text (asserted). | PASS |
| Thread + resolve | Thread-aware second answer; CSAT chip row 1-10 on camera; resolve recorded (DB csat 9). SOLVED chip sat below the fold in the sampled frame; the state is DB-confirmed and the clicks are on camera. | PASS (note) |
| Duplicate charge | "Charged twice... two 19.99 charges" filed; specialist-hold ack (asserted "specialist"); rail shows the three real 19.99 renewals. | PASS |
| Outage | Critical escalate (asserted CRITICAL PRIORITY); this run the drafter produced a held draft, verdict banner "DRAFTED A REPLY AND STOPPED. NOTHING HAS BEEN SENT" — say line corrected to match (the chapter take's run had no draft; both are real behaviors). | PASS (say corrected) |
| Outage worked | OUTAGE tag added, internal note saved and pinned, outage-checklist.txt attached, Dana's hand-written reply sent (status approved). | PASS |
| Channels | Sync email imports the real invoice mail ("EMAIL +1"), Sync Jira imports the live issue; both rows appear in the queue mid-pipeline. | PASS |
| Held refund draft | "DRAFT · WAITING ON YOU · NOT SENT", Approve & send / Edit first / Dismiss, "NOTHING SENDS WITHOUT YOU" footer; Edit first loads the draft, approve clears the hold (asserted). | PASS |
| Emailed ticket | "AUTO-HANDLED", reply "SENT VIA EMAIL · AUTO-SENT", "REPLIES LEAVE AS EMAIL" — narration is channel-focused and outcome-neutral, matching either verdict. | PASS |
| Metrics | Measured tiles (117 tickets, 43% escalation, CSAT 7.8, GPU cost) each labelled measured / estimate / sample; category breakdown. | PASS |
| Close | Customer's screen: the approved reply landed on the duplicate-charge thread; first ticket "RESOLVED · THANKS FOR WRITING IN" with Reopen. | PASS |

Transcript-only say corrections on the shipped take (pixels untouched): the
outage draft line above, "three tickets" → "open tickets" on the queue pan
(the resolved one had already moved to history), and a softened description of
the charges rail.
