# bench.py — item 16a baseline escalation-rate harness (autonomous mode)
# Drives graph_auto directly, so it is autonomous regardless of AGENT_MODE.
# Run under the app's normal env (MODEL_TIER as set in .env) + the work-laptop
# proxy bypass for Weaviate. See the run command in the chat / STATE.
import concurrent.futures
import json
import sys
import time
from statistics import mean

from app import router
from app.graph import graph as graph_det
from app.orchestrator import graph_auto
from app.state import grounded_confidence

# pick the pipeline: pass "deterministic" for the tool-free control, else autonomous (default)
MODE = sys.argv[1] if len(sys.argv) > 1 else "autonomous"
GRAPH = graph_det if MODE.startswith("det") else graph_auto

# Hard per-ticket wall-clock cap: if a ticket's model calls stall past this,
# abandon it, log ERROR, and move on so one hung call can't freeze the batch.
TICKET_TIMEOUT_S = 180

# Fixed batch, committed so the run repeats. First 8 mirror demo.py; the last 4
# add money / shipping-with-order-id / account cases (and seed item 16d's tools).
BATCH = [
    {
        "source": "email",
        "name": "Alice Tan",
        "email": "alice.tan@example.com",
        "subject": "Cannot log in",
        "body": "my password reset link is broken",
    },
    {
        "source": "email",
        "name": "Bob Rivera",
        "email": "bob.rivera@example.com",
        "subject": "Refund request",
        "body": "I want my money back for an unused subscription",
    },
    {
        "source": "chat",
        "name": "Chen Wei",
        "email": "chen.wei@example.com",
        "subject": "Still no refund!!",
        "body": "This is unacceptable, I have waited two weeks and I am furious",
    },
    {
        "source": "email",
        "name": "Dana Okoro",
        "email": "dana.okoro@example.com",
        "subject": "Where is my order",
        "body": "tracking has not updated in three days",
    },
    {
        "source": "chat",
        "name": "Evan Lee",
        "email": "evan.lee@example.com",
        "subject": "It stopped working",
        "body": "nothing works please help",
    },
    {
        "source": "form",
        "name": "Fiona Adams",
        "email": "fiona.adams@example.com",
        "subject": "How do I reset my password",
        "body": "I forgot my password and want to reset it. What are the steps?",
    },
    {
        "source": "email",
        "name": "Grace Hall",
        "email": "grace.hall@example.com",
        "subject": "App keeps crashing on launch",
        "body": "the app crashes every time I open it, please call me back on 555-0142-8890",
    },
    {
        "source": "email",
        "name": "Hana Sato",
        "email": "hana.sato@example.com",
        "subject": "Double charged this month",
        "body": "I was billed twice for my subscription, please refund one charge.",
    },
    {
        "source": "email",
        "name": "Ivan Petrov",
        "email": "ivan.petrov@example.com",
        "subject": "Order 10432 never arrived",
        "body": "My order #10432 was supposed to arrive last week and there is still nothing.",
    },
    {
        "source": "form",
        "name": "Julia Kim",
        "email": "julia.kim@example.com",
        "subject": "Change my email address",
        "body": "I want to update the email on my account to a new one, how do I do that?",
    },
    {
        "source": "chat",
        "name": "Kofi Mensah",
        "email": "kofi.mensah@example.com",
        "subject": "Why was I charged 9.99",
        "body": "I see a 9.99 charge this month and I do not know what it is for.",
    },
    {
        "source": "email",
        "name": "Lena Brooks",
        "email": "lena.brooks@example.com",
        "subject": "Track my package",
        "body": "Can you tell me where my package is right now?",
    },
]


def run_one(raw: dict) -> dict:
    t0 = time.perf_counter()
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(GRAPH.invoke, {"raw_input": raw, "audit": []})
    try:
        final = fut.result(timeout=TICKET_TIMEOUT_S)
    except concurrent.futures.TimeoutError:
        raise RuntimeError(f"timed out after {TICKET_TIMEOUT_S}s (a model call hung)")
    finally:
        ex.shutdown(wait=False)
    dt = time.perf_counter() - t0
    c = final.get("classification") or {}
    d = final.get("decision") or {}
    comp = final.get("compliance") or {}
    draft = final.get("draft") or {}
    retrieval = final.get("retrieval") or []
    raw_conf = draft.get("confidence")
    # always the same blend the gate uses, so every row is on one scale
    grounded = grounded_confidence(raw_conf, retrieval)
    top = max((h.get("score", 0) for h in retrieval), default=0)
    return {
        "subject": raw["subject"],
        "category": c.get("category"),
        "priority": c.get("priority"),
        "action": d.get("action"),
        "reason": d.get("reason"),
        "compliance_verdict": comp.get("verdict"),
        "compliance_issues": comp.get("issues"),
        "grounded_confidence": grounded,
        "raw_confidence": raw_conf,
        "retrieval_top": round(top),
        "latency_s": round(dt, 1),
        "tools": draft.get("tools_called"),
        "steps": draft.get("steps"),
        "finished": draft.get("finished"),
    }


def main() -> None:
    rows = []
    for i, raw in enumerate(BATCH, start=1):
        print(f"[{i}/{len(BATCH)}] {raw['subject']!r} ...", flush=True)
        try:
            rows.append(run_one(raw))
        except Exception as e:
            rows.append({"subject": raw["subject"], "action": "ERROR", "reason": str(e), "latency_s": None})

    total = len(rows)
    esc = [r for r in rows if r["action"] == "escalate"]
    auto = [r for r in rows if r["action"] == "auto_send"]
    confs = [r["grounded_confidence"] for r in rows if isinstance(r.get("grounded_confidence"), (int, float))]
    lats = [r["latency_s"] for r in rows if isinstance(r.get("latency_s"), (int, float))]

    print("\n" + "=" * 100)
    print(f"{'#':>2}  {'category':10} {'priority':8} {'action':10} {'gconf':>5} {'raw':>4} {'top':>4} {'lat':>6}  reason")
    print("-" * 100)
    for i, r in enumerate(rows, start=1):
        print(
            f"{i:>2}  {str(r.get('category')):10} {str(r.get('priority')):8} "
            f"{str(r.get('action')):10} {str(r.get('grounded_confidence')):>5} "
            f"{str(r.get('raw_confidence')):>4} {str(r.get('retrieval_top')):>4} "
            f"{str(r.get('latency_s')):>6}  {r.get('reason')}"
        )
    print("=" * 100)
    print(f"config          : {MODE} / MODEL_TIER={router.MODEL_TIER}")
    print(f"tickets         : {total}")
    print(f"escalation rate : {len(esc)}/{total} = {len(esc) / total:.0%}")
    print(f"auto-send rate  : {len(auto)}/{total} = {len(auto) / total:.0%}")
    print(f"avg grounded cnf: {mean(confs):.0f}" if confs else "avg grounded cnf: n/a")
    print(f"avg latency     : {mean(lats):.1f}s" if lats else "avg latency     : n/a")

    fails = [(i, r) for i, r in enumerate(rows, start=1) if r.get("compliance_verdict") == "fail"]
    if fails:
        print("\ncompliance failures (what the review gate actually objected to):")
        for i, r in fails:
            print(f"  #{i} {r['subject']!r}: {r.get('compliance_issues')}")

    # diagnostics: did the generate agent run out of ReAct steps (fallback -> escalate)? which tools fired?
    from collections import Counter

    fallbacks = [i for i, r in enumerate(rows, start=1) if r.get("finished") is False]
    steps_used = [r["steps"] for r in rows if isinstance(r.get("steps"), int)]
    tool_hist = Counter(t for r in rows for t in (r.get("tools") or []))
    print("\ndiagnostics (generate agent):")
    print(f"  fallback escalates (never finished in MAX_STEPS): {len(fallbacks)}/{total}  tickets {fallbacks}")
    print(f"  avg steps used  : {mean(steps_used):.1f}" if steps_used else "  avg steps used  : n/a")
    print(f"  tool call counts: {dict(tool_hist)}")
    for i, r in enumerate(rows, start=1):
        print(f"  #{i:>2} steps={r.get('steps')} finished={r.get('finished')} action={r.get('action')} tools={r.get('tools')}")

    out = {
        "config": f"{MODE} / MODEL_TIER={router.MODEL_TIER}",
        "tickets": total,
        "escalation_rate": len(esc) / total,
        "auto_send_rate": len(auto) / total,
        "rows": rows,
    }
    outfile = f"bench_{MODE}.json"
    with open(outfile, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nsaved -> {outfile}")


if __name__ == "__main__":
    main()
