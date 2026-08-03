"""One command builds the whole demo world: accounts, KB, corpus, tickets, macros.

    uv run python seed_all.py

Runs the individual seeds in runbook order. All of them are idempotent, so
re-running after a partial failure is safe.

This is the seeding half of onboarding a client. `provision_client.py` wraps it
with the configuration checks and the handover notes, and imports STEPS from
here so the order is defined in exactly one place.
"""

import subprocess
import sys

STEPS = [
    "seed_users.py",      # staff, admin and demo customer accounts
    "seed_kb.py",         # knowledge collection (wipes and recreates it)
    "kb_import.py",       # larger article corpus, offline after first run
    "seed_data.py",       # synthetic customers and orders
    "seed_universe.py",   # demo tickets
    "seed_templates.py",  # canned replies for the macro chips
]


def run_all() -> None:
    for step in STEPS:
        print(f"\n=== {step} ===", flush=True)
        code = subprocess.run([sys.executable, step]).returncode
        if code != 0:
            sys.exit(f"\n{step} failed (exit {code}). Fix it and re-run, finished steps are safe to repeat.")


# guarded: provision_client.py imports STEPS from this module, and merely importing
# a seeder must never seed a database
if __name__ == "__main__":
    run_all()
    print("\nDemo world seeded. Start the API and the frontend next.")
