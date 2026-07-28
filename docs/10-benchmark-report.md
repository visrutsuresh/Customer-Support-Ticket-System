# 10. Benchmark Report

**Version 1, 2026-07-28.** Numbers as measured, with their limits stated. Raw results are committed as `bench_baseline.json`, `bench_deterministic.json` and `bench_autonomous.json`.

## 1. Method

`bench.py` runs the same twelve synthetic tickets through the whole pipeline and records, per ticket: the classification, the decision and its reason, the compliance verdict, the model's self-reported confidence, the top retrieval score, the blended grounded confidence, wall-clock latency, and for the autonomous mode the tools used and the number of steps.

All three runs used the larger open-weight model on the private lane (`MODEL_TIER=local`), so the cloud lane is not represented in these figures.

## 2. Results

| Run | Mode | Escalated | Auto-sent | Compliance passed | Mean confidence | Mean latency |
|---|---|---|---|---|---|---|
| `bench_deterministic.json` | fixed pipeline | 16.7% (2 of 12) | 83.3% | 12 of 12 | 88 | 18s (16 to 23) |
| `bench_baseline.json` | autonomous, before tool work | 33.3% (4 of 12) | 58.3% | 11 of 12 | 89 | 91s (45 to 113) |
| `bench_autonomous.json` | autonomous, after tool work | 0% | 100% | 12 of 12 | 89 | 90s (41 to 132) |

Every escalation in both of the first two runs was for the same reason: grounded confidence just under the bar (87, 84, 89, 85 against a threshold of 90). None were compliance failures.

## 3. What these numbers mean

- **The autonomous pipeline started worse than the fixed one and ended better.** Giving the agents a real tool universe took escalations from a third of the batch to none, against a fixed-pipeline control of one in six. That comparison is the point of keeping both pipelines.
- **Escalation was driven by the confidence bar, not by bad answers.** Answers scoring 87 out of 100 were being sent to a human. The bar for sensitive and money categories has since been lowered from 90 to 85 for exactly this reason, so a rerun should show fewer escalations in both modes.
- **Autonomy costs about five times the wall clock.** Roughly 90 seconds against 18. That is the trade the mode switch exists to let you make, and it is why the fixed pipeline is the demo default.

## 4. Labelled evaluation, 2026-07-28

The benchmark above measures what the system **decided**. It cannot say whether the decision was **right**, because those twelve tickets have no correct answer attached. A separate labelled set now closes that gap.

`data/eval_set.jsonl` holds 30 tickets with the correct category, priority, difficulty and sensitivity written down, and, for the 22 that a knowledge-base article genuinely answers, the titles of the acceptable articles. The remaining 8 are deliberately not covered by the knowledge base: two complaints, two feature requests, an outage, a legal threat, an erasure request, and one too vague to answer.

`eval.py` scores it in two halves, separable by cost:

```bash
uv run python eval.py             # retrieval only, free, no model calls
uv run python eval.py --classify  # adds one model call per ticket
```

**Results, 30 tickets, 0 errors, 249 seconds:**

| Measure | Result |
|---|---|
| Retrieval hit rate, top 5 | **100%** (22 of 22 answerable tickets) |
| Retrieval hit at rank 1 | 36% (8 of 22), mean rank of a hit 1.86 |
| Classification accuracy, category | **83.3%** |
| Classification accuracy, priority | **66.7%** |
| Both correct on the same ticket | 60.0% |

**Reading these honestly:**

- **Hit rate at five is a soft measure.** With five slots and a relevance floor, the right article is almost always somewhere in the list. Rank one at 36 percent is the number that discriminates, and it is the one to improve.
- **Retrieval cannot tell "no good article" from "good article".** All eight no-coverage tickets still returned hits, scoring 77 to 89, inside the same band as genuine matches. The score floor cannot separate them. What actually protects those tickets is the control line in the drafting prompt, which lets the agent say it must ask or escalate. That is prompt-level, not structural.
- **Category confusion is sensible, not random.** Five errors, each a single ticket: technical against account in both directions, a delivery question read as shipping rather than general, a complaint read as a refund, and a feature request read as billing.
- **Priority is the weak dimension, and it errs safe.** Ten misses: seven over-rate (medium to high, low to medium), three under-rate. The two that matter are the two critical tickets scored high, an outage and a legal threat, because under-rating is the direction that hurts.

## 5. Limits, stated plainly

- **Twelve tickets, and thirty labelled ones, are batches rather than samples.** No confidence intervals are claimed and none should be.
- **The labels were written by the same person who built the system**, which is the strongest bias in the evaluation numbers.
- **Latency depends on a warm GPU container.** A cold start adds roughly a minute and is excluded from these figures by warming the lane first.
- **The runs predate the confidence recalibration.** The reported escalation rates are against the old bar of 90.
- **Compliance pass rate is close to a ceiling** at 11 or 12 of 12, so it discriminates poorly; it is reported because it is a stated requirement metric.

## 6. Live system metrics

Separately from the benchmark, the running system computes its own numbers over whatever is in the database, shown on the metrics dashboard and available at `GET /metrics`: ticket volume, escalated against auto-resolved, compliance reviewed and passed, average processing time split into warm and cold, an estimated GPU cost per ticket, average customer rating, and average time to resolution. Those are live operational figures, not a benchmark, and they move as the demo data changes.

## 7. Reproducing

```bash
uv run python bench.py                  # decision behaviour, both modes, the committed ticket set
uv run python eval.py                   # retrieval hit rate, free
uv run python eval.py --classify        # + classification accuracy, one call per ticket
uv run python eval.py --classify --limit 5   # cost fence
```

Both benchmarks cost GPU money on every wake, except `eval.py` without `--classify`, which is free. Warm the lane first and run a whole batch in one window rather than one ticket at a time. Raw results are written to `bench_*.json` and `eval_results.json`.
