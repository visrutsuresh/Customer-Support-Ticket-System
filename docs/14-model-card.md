# 14. Model Card

**Version 1, 2026-07-28.** What models this system uses, how they are chosen, what they are good at, and where they fail.

## 1. Models in use

| Lane | Model | Host | Used for |
|---|---|---|---|
| Private, simple | Qwen2.5-3B-Instruct | Serverless GPU (T4), half precision | Everyday reasoning and replies on the cheapest tier |
| Private, complex | Qwen2.5-14B-Instruct | Serverless GPU (A10G), 4-bit quantised | Reasoning checks and harder replies, and all sensitive work that needs quality |
| Cloud, simple | Claude Haiku 4.5 | Provider API | Non-sensitive simple replies, full tier only |
| Cloud, complex | Claude Sonnet 4.6 | Provider API | Non-sensitive complex replies, full tier only |
| Embeddings | A small local sentence embedding model, 384 dimensions | The machine itself | Turning text into vectors for retrieval. No text leaves the machine to be indexed |

All generation runs at temperature zero, so repeated runs are as reproducible as the model allows.

## 2. How a model is chosen

Two questions, asked in plain code, never by a model:

1. Is the ticket sensitive? That picks the lane, and it is decided before any model call.
2. Is it simple or complex? That picks the size within the lane.

A `MODEL_TIER` switch then caps the result: `dev` forces everything onto the small model, `local` allows the larger open model, `full` unlocks the cloud lane. The interface always shows the model the grid intended, even when the tier caps what actually ran, so the trade-off is visible rather than hidden.

## 3. What the models are asked to do

| Task | Output contract |
|---|---|
| Classify | Strict JSON: category, priority, business impact, sentiment |
| Score difficulty | Strict JSON: simple or complex, plus a reason |
| Judge sensitivity | Strict JSON: a boolean, matched categories, a reason |
| Draft a reply | A control line carrying kind and confidence, then the reply text |
| Review the draft | The single word PASS, or FAIL with a reason |
| Learn from a resolution | Whether the resolution is worth filing, and its title |

Every one of these is parsed by code that expects a specific shape, and every parser tolerates the model wrapping its answer in prose or fences.

## 4. Known failure modes

| Failure | How it shows | What contains it |
|---|---|---|
| Invalid JSON from a small model | A parse error, the run retries, and a second failure marks the ticket in error | The retry, plus the pattern and category checks that stand on their own for sensitivity |
| Truncated output on long answers | The reply stops mid-sentence | Generous token limits per call; still possible on unusually long threads |
| Over-escalation | Correct answers sent to a human because confidence sat just under the bar | The bar was recalibrated from 90 to 85 after answers scoring 87 were being escalated |
| Third-person voice, or internal wording copied into a customer reply | It reads like notes rather than a letter | An explicit voice rule in the prompt and a quality clause in the review gate |
| Hallucinated detail when the knowledge base has nothing | An invented answer | The prompt requires the model to ask a question or decline instead, and the retrieval floor drops weak matches. This is prompt-level, not structural, so it depends on model obedience |
| Wandering in autonomous mode | Many steps, repeated tool calls, long latency | An eight-step ceiling per agent, a duplicate-call block, and a whole-run time cap |
| Cold container | The first call after idle takes about a minute | The lane is warmed before demos, and the caller retries once |

## 5. What is not measured

**Measured as of 2026-07-28**, against 30 labelled tickets: category 83.3 percent, priority 66.7 percent, both correct on the same ticket 60 percent, retrieval hit rate 100 percent at top five and 36 percent at rank one. Priority errors lean safe, seven over-rating against three under-rating, but two critical tickets, an outage and a legal threat, were scored high rather than critical.

Still unmeasured: whether an auto-sent reply was actually **useful** to the customer, and whether an escalation was necessary. Both need either a human rater or real customer feedback, and neither exists on synthetic data. The customer rating field is the closest available proxy and is only populated in demonstrations.

## 6. Appropriate and inappropriate use

Appropriate: drafting and triaging synthetic customer requests with a human able to review anything the system did not auto-send.

Inappropriate without further work: any decision with legal or financial consequence taken without review; use on real customer data before the retention and redaction gaps in [13-privacy-and-data-handling.md](13-privacy-and-data-handling.md) are closed; any setting where a wrong auto-sent reply cannot be corrected.

## 7. Human oversight

Auto-send is deliberately narrow: a policy-passing answer, grounded in retrieved material, above a confidence bar that is higher for money and high-priority tickets. Everything else reaches a person, who can approve, edit or reject, and an explicit request to speak to a human bypasses the model entirely.
