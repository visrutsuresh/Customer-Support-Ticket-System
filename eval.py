"""eval.py - score the pipeline against the labelled set in data/eval_set.jsonl.

Closes the two requirement metrics bench.py cannot report, because bench.py has no
ground truth: CLASSIFICATION ACCURACY and RETRIEVAL HIT RATE.

Two halves, deliberately separable by cost:

    uv run python eval.py                      # retrieval only. $0, no model calls
    uv run python eval.py --classify           # + classification. ONE model call per ticket
    uv run python eval.py --classify --limit 5 # cost fence: first 5 tickets only

Needs Docker up and the knowledge base seeded (seed_kb.py, then kb_import.py).
On a machine with a TLS-intercepting proxy, export the localhost bypass first or
the vector search hangs:  NO_PROXY=127.0.0.1,localhost no_grpc_proxy=127.0.0.1,localhost

Writes eval_results.json (per-ticket rows + the summary) so runs can be compared.
"""

import json
import sys
import time
from collections import Counter

from app.intake import normalize
from app.kb import search

EVAL_FILE = "data/eval_set.jsonl"
OUT_FILE = "eval_results.json"

DO_CLASSIFY = "--classify" in sys.argv
LIMIT = None
if "--limit" in sys.argv:
    LIMIT = int(sys.argv[sys.argv.index("--limit") + 1])


def load_set() -> list[dict]:
    with open(EVAL_FILE, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return rows[:LIMIT] if LIMIT else rows


def score_retrieval(row: dict) -> dict:
    """Did the knowledge base surface an article that actually answers this ticket?

    Hit rate is measured only over tickets that HAVE a right answer. The eight
    no-coverage tickets (complaints, feature requests, an outage) are scored the
    other way round: the honest result there is a weak top score, because the
    knowledge base genuinely does not cover them.
    """
    query = f"{row['subject']} {row['body']}"
    hits = search(query)
    titles = [h["title"] for h in hits]
    wanted = row["expect"]["kb_titles"]
    rank = next((i + 1 for i, t in enumerate(titles) if t in wanted), None)
    return {
        "returned": len(hits),
        "top_title": titles[0] if titles else None,
        "top_score": hits[0]["score"] if hits else 0,
        "hit": rank is not None,
        "rank": rank,
        "covered": bool(wanted),
    }


def score_classification(row: dict) -> dict:
    """One model call per ticket: the classify node, judged against the labels."""
    from app.graph import classify  # imported late so retrieval-only runs need no lane

    ticket = normalize({"source": row["source"], "subject": row["subject"], "body": row["body"]})
    got = classify({"ticket": ticket})["classification"]
    want = row["expect"]
    got_cat = str(got.get("category", "")).lower()
    got_pri = str(got.get("priority", "")).lower()
    return {
        "got_category": got_cat,
        "got_priority": got_pri,
        "category_ok": got_cat == want["category"],
        "priority_ok": got_pri == want["priority"],
    }


def pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def main() -> None:
    rows = load_set()
    print(f"eval set: {len(rows)} tickets{' (limited)' if LIMIT else ''}")
    print(f"classification: {'ON, one model call per ticket' if DO_CLASSIFY else 'OFF ($0 run)'}\n")

    results, errors = [], 0
    t0 = time.monotonic()
    for row in rows:
        out = {"id": row["id"], "expect": row["expect"]}
        try:
            out["retrieval"] = score_retrieval(row)
            if DO_CLASSIFY:
                out["classification"] = score_classification(row)
        except Exception as e:  # one bad ticket must never kill the batch
            errors += 1
            out["error"] = str(e)
            print(f"  {row['id']} ERROR {e}")
        results.append(out)

        r = out.get("retrieval", {})
        mark = "hit " if r.get("hit") else ("--  " if r.get("covered") else "n/a ")
        line = f"  {row['id']} {mark} top={str(r.get('top_title'))[:34]:<34} score={r.get('top_score')}"
        if DO_CLASSIFY and "classification" in out:
            c = out["classification"]
            line += f" | cat {'ok' if c['category_ok'] else 'X ' } {c['got_category']:<15} pri {'ok' if c['priority_ok'] else 'X '} {c['got_priority']}"
        print(line)

    covered = [r for r in results if r.get("retrieval", {}).get("covered")]
    uncovered = [r for r in results if "retrieval" in r and not r["retrieval"]["covered"]]
    hits = [r for r in covered if r["retrieval"]["hit"]]
    ranks = [r["retrieval"]["rank"] for r in hits]

    summary = {
        "tickets": len(rows),
        "errors": errors,
        "retrieval": {
            "answerable_tickets": len(covered),
            "hits": len(hits),
            "hit_rate_pct": pct(len(hits), len(covered)),
            "mean_rank_of_hit": round(sum(ranks) / len(ranks), 2) if ranks else None,
            "top1_hits": sum(1 for r in ranks if r == 1),
            "no_coverage_tickets": len(uncovered),
            "no_coverage_returned_something": sum(1 for r in uncovered if r["retrieval"]["returned"]),
        },
        "elapsed_s": round(time.monotonic() - t0, 1),
    }

    if DO_CLASSIFY:
        scored = [r for r in results if "classification" in r]
        cat_ok = sum(1 for r in scored if r["classification"]["category_ok"])
        pri_ok = sum(1 for r in scored if r["classification"]["priority_ok"])
        both = sum(1 for r in scored if r["classification"]["category_ok"] and r["classification"]["priority_ok"])
        confusions = Counter(
            f"{r['expect']['category']} -> {r['classification']['got_category']}"
            for r in scored
            if not r["classification"]["category_ok"]
        )
        summary["classification"] = {
            "scored": len(scored),
            "category_accuracy_pct": pct(cat_ok, len(scored)),
            "priority_accuracy_pct": pct(pri_ok, len(scored)),
            "both_correct_pct": pct(both, len(scored)),
            "category_confusions": confusions.most_common(),
        }

    print("\n" + "=" * 60)
    print(json.dumps(summary, indent=2))
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": results}, f, indent=1)
    print(f"\nwrote {OUT_FILE}")


if __name__ == "__main__":
    main()
