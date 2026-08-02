# Demo script: the five beats

Audience takeaway: a customer types one message and a team of AI agents
classifies it, researches it, drafts the answer and knows when NOT to answer,
while a human stays in charge of everything that leaves the building.

## Pre-demo checklist (30 min before)

1. `docker compose up -d`, confirm `curl localhost:8000/` is not needed yet but
   `docker compose ps` shows both containers up.
2. Seeds if the machine is fresh: `uv run python seed_all.py` (one command,
   runs all six in order; idempotent).
3. WARM THE MODAL LANE (~77s cold): submit one throwaway ticket and wait for
   `[pipeline] T-xxxx done on attempt 1` in the log. Never demo on a cold lane.
4. Backend `uv run uvicorn api:app --reload` (:8000), frontend
   `cd frontend && npm run dev` (:3000). One app at a time: all three sibling
   systems claim :8000/:3000.
5. Two browser windows side by side: left = customer portal (log in as
   customer@nimbus.dev), right = staff workspace (dana@nimbus.dev). The split
   screen IS the demo: cause on the left, effect on the right.
6. `AGENT_MODE=autonomous` in `.env` for the money beat; know that
   `deterministic` is the safety net if the lane is sick.
7. The recorded backup of all five beats is loaded and ready to play (mandatory).

## Beat 1 - the customer asks for help (1 min)

Left window: file a ticket ("I was charged twice for order #4482, please
refund one"). Point at the honest processing state: "we are working on your
request". No fake instant answer.

## Beat 2 - the agents work (2-4 min, the money beat)

Right window: the ticket appears in the queue. While the autonomous run
executes, narrate the five agents: classifier tags category and priority,
researcher searches the knowledge base (a few hundred seeded articles plus
every past resolved ticket), resolver drafts, the difficulty scorer decides which model size the
ticket deserves, and the confidence gate decides whether a human must look
first. Sensitive tickets never leave the private GPU lane (the privacy pitch).

## Beat 3 - the human stays in charge (2 min)

Open the ticket: classification, SLA countdown, the drafted reply, the KB
sources it used. Edit one sentence of the draft, then Approve and send. Left
window: the reply lands in the customer's thread within a poll cycle (~5s).
One sentence: nothing reaches a customer unless the gate was confident or a
person pressed the button.

## Beat 4 - it knows when NOT to answer (2 min)

Left window: file "I want to speak to a real person about a legal complaint".
It escalates instead of answering: priority high, action escalate, no
auto-reply. The system's value is also what it refuses to do alone.

## Beat 5 - the loop closes (1 min)

Resolve the billing ticket with a rating. Show `learned: true` in the
response: the resolution was folded into the knowledge base, so the next
duplicate-charge ticket retrieves this one as precedent. Then the metrics
page: deflection, time-to-first-response, CSAT, and the honest SAMPLE badges
on anything estimated. If asked "does it scale": rate limits per account,
input caps, pagination, and a restart sweep are already in the code.

## If the lane misbehaves

Beat 2 is the only Modal-dependent beat. Switch `.env` to
`AGENT_MODE=deterministic` and restart the backend (same pipeline shape,
seconds instead of minutes, no 14B review model), or play the recording for
beat 2 and keep the rest live.
