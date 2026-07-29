"""Seed the canned replies the macro chips offer on a ticket. Idempotent: run any time.

Without this the templates table is empty, the macro row renders nothing, and the
feature looks missing rather than unused. Bodies are deliberately short and end
with a signature line, because a macro is a starting point an agent then edits.
"""
from dotenv import load_dotenv

load_dotenv()

import app.store as store  # noqa: E402

SEEDS = [
    (
        "Refund policy",
        "Thanks for getting in touch. Refunds are available within 30 days of purchase, "
        "and land back on the original payment method within 5 to 7 working days once approved. "
        "I have started that process for you.\n\nNimbus Support",
        "billing",
        ["refund", "money back", "return"],
    ),
    (
        "Password reset",
        "Thanks for getting in touch. I have sent a reset link to the email address on your account. "
        "It is valid for one hour. If it does not arrive, check the spam folder and let me know.\n\nNimbus Support",
        "account",
        ["password", "locked out", "reset", "sign in"],
    ),
    (
        "Outage acknowledgement",
        "Thanks for reporting this. We are aware of the issue and our engineers are working on it now. "
        "I will update you here as soon as service is restored.\n\nNimbus Support",
        "technical",
        ["down", "outage", "not working", "error"],
    ),
    (
        "Shipping delay",
        "Thanks for your patience. Your order has been delayed in transit and the courier now expects "
        "delivery within the next two working days. The tracking link on your order stays live.\n\nNimbus Support",
        "shipping",
        ["delivery", "late", "tracking", "where is my order"],
    ),
    (
        "Asking for more detail",
        "Thanks for getting in touch. So I can get this right, could you send the exact error message "
        "you see and roughly when it started? A screenshot is perfect if you have one.\n\nNimbus Support",
        "general",
        ["unclear", "more information"],
    ),
]


def main():
    store.init_db()
    existing = {t["name"] for t in store.list_templates()}
    for name, body, category, keywords in SEEDS:
        if name in existing:
            print(f"kept {name}")
            continue
        # auto_use stays False on every seed: these are offered to an agent, never
        # sent on their behalf, which is the whole point of a human-in-the-loop desk
        store.create_template(name, body, category, keywords, False)
        print(f"created {name}")


main()
