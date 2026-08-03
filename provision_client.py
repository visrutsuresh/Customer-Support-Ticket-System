"""Onboard a company as an Enklima client.

Enklima is the PRODUCT. A client is three things and nothing else:

  1. a deployment of its own (this database, this vector store, this model lane),
  2. configuration (the brand, the channels, the private lane credentials),
  3. that client's own content (its help articles, its policy, its staff).

Nothing about a client lives in the product code, which is why the same skeleton
also became the contract-review and AI-governance systems. This command is the
front door to points 1 and 3, and it tells you exactly what to set for point 2.

One deployment serves ONE client, deliberately: the product's promise is that a
client's sensitive tickets never leave its own infrastructure, and a shared
database would undo that. Multi-tenancy is a roadmap line, not a missing feature.

    uv run python provision_client.py --brand Nimbus --tagline "Support that answers"

Idempotent, like every seed it runs, so it is safe to repeat.
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from seed_all import STEPS, run_all

load_dotenv()

# without these the seeds cannot reach the client's own stores, and the failure
# further in is much harder to read than the one below
# WEAVIATE_URL is deliberately absent: app/kb.py falls back to local Docker, so
# only the cloud path needs it set
REQUIRED = {
    "DATABASE_URL": "Postgres for tickets, accounts and the audit trail",
    "AUTH_SECRET": "signs the session cookie; must be unique per deployment",
}

# the client writes these, not us. Shipping ours to a second client would give
# them another company's refund window and another company's staff.
CLIENT_OWNED = {
    "policy.md": "the rules every outgoing reply is checked against",
    "seed_kb.py": "the help articles the answers are grounded in",
    "app/roster.py": "the support staff tickets are assigned to",
    "seed_data.py": "in production this is the client's real CRM, orders and billing",
}


def preflight(brand: str) -> None:
    missing = [f"  {k:<14} {why}" for k, why in REQUIRED.items() if not os.getenv(k)]
    if missing:
        sys.exit(
            "Cannot provision: this deployment is not configured yet.\n\n"
            "Missing from the environment (put them in .env):\n"
            + "\n".join(missing)
            + "\n\nCopy .env.example to .env and fill it in, then run this again."
        )
    print(f"Provisioning Enklima for: {brand}")
    print(f"  database   {_host_only(os.getenv('DATABASE_URL', ''))}")
    vectors = os.getenv("WEAVIATE_URL") or f"local Docker ({os.getenv('WEAVIATE_HOST', 'localhost')})"
    print(f"  vectors    {vectors}")
    print(f"  model tier {os.getenv('MODEL_TIER', 'local')}")
    lane = "configured" if os.getenv("PRIVATE_LANE_URL") else "NOT configured, sensitive tickets have nowhere private to go"
    print(f"  private lane {lane}")
    print(f"\nSeeding {len(STEPS)} steps. All idempotent.")


def _host_only(url: str) -> str:
    """Never print a connection string: it carries the password."""
    if "@" in url:
        return url.rsplit("@", 1)[-1]
    return url or "(unset)"


def handover(brand: str, tagline: str) -> None:
    print("\n" + "=" * 68)
    print(f"{brand} is provisioned.")
    print("=" * 68)
    print("\n1. Put the brand in .env so the API and every reply use it:\n")
    print(f"   BRAND_NAME={brand}")
    if tagline:
        print(f"   BRAND_TAGLINE={tagline}")
    print("\n   The portal repaints from GET /config, and both pipelines sign replies")
    print(f"   as 'The {brand} Support Team'. No code change, no rebuild.")
    print("\n2. Replace the demo content with the client's own:\n")
    for path, what in CLIENT_OWNED.items():
        print(f"   {path:<16} {what}")
    print("\n3. Add the client's channels to .env if they want them:\n")
    print("   the support inbox (IMAP/SMTP), the Jira site and token,")
    print("   and PRIVATE_LANE_URL + PRIVATE_LANE_TOKEN for sensitive tickets.")
    print("\n4. Start it:\n")
    print("   uv run uvicorn api:app --reload      # API on :8000")
    print("   cd frontend && npm run dev           # portal on :3000")


def main() -> None:
    ap = argparse.ArgumentParser(description="Onboard a company as an Enklima client.")
    ap.add_argument("--brand", default=os.getenv("BRAND_NAME", "Nimbus"), help="the client's name, shown to its customers")
    ap.add_argument("--tagline", default=os.getenv("BRAND_TAGLINE", ""), help="the line under the client's name")
    ap.add_argument("--skip-seeds", action="store_true", help="configuration report only, touch no data")
    args = ap.parse_args()

    preflight(args.brand)
    if args.skip_seeds:
        print("\n--skip-seeds given, no data touched.")
    else:
        # the seeds load the client's own content; the brand reaches the running
        # app through the environment, which step 1 of the handover explains
        os.environ["BRAND_NAME"] = args.brand
        if args.tagline:
            os.environ["BRAND_TAGLINE"] = args.tagline
        run_all()
    handover(args.brand, args.tagline)


if __name__ == "__main__":
    main()
