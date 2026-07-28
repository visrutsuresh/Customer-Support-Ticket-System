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

## 4. Limits, stated plainly

- **Twelve tickets is a batch, not a sample.** No confidence intervals are claimed and none should be.
- **There is no ground truth.** These runs measure what the system decided, not whether it decided correctly. Classification accuracy and retrieval hit rate are unmeasured, see [09-test-plan-and-report.md](09-test-plan-and-report.md).
- **Latency depends on a warm GPU container.** A cold start adds roughly a minute and is excluded from these figures by warming the lane first.
- **The runs predate the confidence recalibration.** The reported escalation rates are against the old bar of 90.
- **Compliance pass rate is close to a ceiling** at 11 or 12 of 12, so it discriminates poorly; it is reported because it is a stated requirement metric.

## 5. Live system metrics

Separately from the benchmark, the running system computes its own numbers over whatever is in the database, shown on the metrics dashboard and available at `GET /metrics`: ticket volume, escalated against auto-resolved, compliance reviewed and passed, average processing time split into warm and cold, an estimated GPU cost per ticket, average customer rating, and average time to resolution. Those are live operational figures, not a benchmark, and they move as the demo data changes.

## 6. Reproducing

```bash
uv run python bench.py            # both modes over the committed ticket set
```

This costs GPU money on every wake. Warm the lane first and run the whole batch in one window rather than one ticket at a time.
