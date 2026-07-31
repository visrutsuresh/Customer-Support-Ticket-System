"""Load the KB from the Bitext support dataset.

First run pulls ~400 rows from Hugging Face and saves them to data/kb_seed.jsonl.
After that (and on the work laptop) it reads that file instead, so no download needed.
Adds to the existing Knowledge collection, does not wipe it.

    uv run python kb_import.py
"""

import json
import os
import re

from app.embed import embed
from app.kb import connect

N_ARTICLES, N_TICKETS = 250, 150
SEED_FILE = "data/kb_seed.jsonl"

_PROFANITY = re.compile(
    r"\b(motherf\w*|fuck\w*|bastard\w*|bitch\w*|asshole\w*)\b",
    re.I,
)


def clean(text: str) -> str:
    # drop Bitext's {{Order Number}} style tokens and squeeze the whitespace
    text = re.sub(r"\{\{([^}]+)\}\}", lambda m: m.group(1).lower(), text)
    text = _PROFANITY.sub("", text)  # keep the anger, drop the swearing
    return " ".join(text.split())


def map_category(cat: str) -> str:
    # squeeze Bitext's categories into ours; substring match so small naming changes don't break it
    c = cat.lower()
    if "refund" in c or "cancel" in c:
        return "refund"
    if "payment" in c or "invoice" in c or "subscription" in c:
        return "billing"
    if "shipping" in c or "delivery" in c:
        return "shipping"
    if "account" in c:
        return "account"
    if "feedback" in c:
        return "complaint"
    return "general"


def load_rows() -> list[dict]:
    if os.path.exists(SEED_FILE):
        with open(SEED_FILE) as f:
            rows = [json.loads(line) for line in f]
        print(f"loaded {len(rows)} rows from {SEED_FILE}")
        return rows
    # no cache yet, so pull from HF and save it for next time
    from datasets import load_dataset

    print("downloading Bitext dataset...")
    ds = load_dataset("bitext/Bitext-customer-support-llm-chatbot-training-dataset", split="train")
    ds = ds.shuffle(seed=42).select(range(N_ARTICLES + N_TICKETS))
    rows = [{"instruction": r["instruction"], "response": r["response"], "category": r["category"], "intent": r["intent"]} for r in ds]
    os.makedirs(os.path.dirname(SEED_FILE), exist_ok=True)
    with open(SEED_FILE, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"saved {len(rows)} rows to {SEED_FILE}")
    return rows


rows = load_rows()

client = connect()
try:
    kb = client.collections.get("Knowledge")
    with kb.batch.dynamic() as batch:
        for i, r in enumerate(rows):
            cat = map_category(r["category"])
            intent = r["intent"].replace("_", " ")
            answer = clean(r["response"])
            if i < N_ARTICLES:
                title, content, source = f"{cat.title()}: {intent}", answer, "article"
            else:
                problem = clean(r["instruction"])
                title, content, source = problem[:70], f"Problem: {problem} Resolution: {answer}", "ticket"
            batch.add_object(
                properties={"title": title, "content": content, "source": source},
                vector=embed(title + ". " + content),
            )
            if (i + 1) % 50 == 0:
                print(f"  indexed {i + 1}/{len(rows)}")
    print(f"done: {N_ARTICLES} articles + {N_TICKETS} tickets added")
finally:
    client.close()
