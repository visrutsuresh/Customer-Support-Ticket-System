# single source of truth for the fake company's data
import random
from datetime import date, timedelta

from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

# the one place prices and rules are defined
PLANS = {"free": 0.00, "pro": 19.99, "max": 99.99}
REFUND_WINDOW_DAYS = 30
CARRIERS = ["UPS", "FedEx", "DHL", "USPS"]
ITEMS = [
    "Mechanical Keyboard",
    "Wireless Mouse",
    "USB-C Cable",
    "Noise-Cancelling Headphones",
    "Smart Home Hub",
    "Webcam 1080p",
    "Laptop Stand",
    "Portable SSD",
]

# a fixed 'today' so that "5 days ago" is reproducible for the bench
TODAY = date(2026, 7, 15)


def days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


# service_status tool reads this; one live incident so the tool has something to show
SERVICE_INCIDENTS = [
    {
        "id": "INC-204",
        "component": "mobile app",
        "status": "investigating",
        "summary": "Some users report intermittent crashes on launch.",
        "started": days_ago(1),
    },
]


def customer(name, email, plan, account_status="active", subscription_status="active", signup_days_ago=200, orders=None, charges=None, past_tickets=None):
    return {
        "name": name,
        "email": email,
        "plan": plan,
        "tier": "premium" if plan in ("pro", "max") else "standard",  # derived, not a second source of truth
        "account_status": account_status,
        "subscription_status": subscription_status if plan != "free" else "none",
        "signup_date": days_ago(signup_days_ago),
        "orders": orders or [],
        "charges": charges or [],
        "past_tickets": past_tickets or [],
    }


def order(order_id, item, amount, status, ordered_days_ago, tracking=None):
    return {
        "order_id": order_id,
        "item": item,
        "amount": amount,
        "status": status,
        "tracking": tracking,
        "ordered_at": days_ago(ordered_days_ago),
    }


def charge(amount, description, charged_days_ago):
    return {
        "amount": amount,
        "description": description,
        "charged_at": days_ago(charged_days_ago),
    }


# each of the 12 is built so its bench ticket becomes answerable by a tool
BENCH = [
    customer("Alice Tan", "alice.tan@example.com", "free", signup_days_ago=200),  # login how-to (KB)
    customer(
        "Bob Rivera",
        "bob.rivera@example.com",
        "pro",
        signup_days_ago=300,
        charges=[charge(19.99, "Pro plan monthly", 10)],
    ),  # refund: charge 10d ago, inside 90d window
    customer(
        "Chen Wei",
        "chen.wei@example.com",
        "pro",
        subscription_status="refund_pending",
        signup_days_ago=400,
        charges=[charge(19.99, "Pro plan monthly", 20)],
        past_tickets=[
            {"subject": "Refund request", "body": "Cancelled and want a refund.", "category": "refund",
             "priority": "high", "sentiment": "negative", "resolution": "Refund requested, pending review.", "csat": 6}
        ],
    ),  # "still no refund" -> in progress
    customer(
        "Dana Okoro",
        "dana.okoro@example.com",
        "free",
        signup_days_ago=60,
        orders=[order("10310", "Mechanical Keyboard", 79.99, "in_transit", 5, "1Z9A7X4421")],
    ),  # where is my order
    customer("Evan Lee", "evan.lee@example.com", "pro", signup_days_ago=90),  # vague; service incident is the hook
    customer("Fiona Adams", "fiona.adams@example.com", "free", signup_days_ago=30),  # password how-to (KB)
    customer(
        "Grace Hall",
        "grace.hall@example.com",
        "pro",
        signup_days_ago=500,
        past_tickets=[{"subject": "App crash", "body": "App crashed on launch.", "category": "technical",
                       "priority": "medium", "sentiment": "negative", "resolution": "Advised reinstall; monitoring.", "csat": 7}],
    ),  # crashing ticket
    customer(
        "Hana Sato",
        "hana.sato@example.com",
        "pro",
        signup_days_ago=250,
        charges=[charge(19.99, "Pro plan monthly", 3), charge(19.99, "Pro plan monthly", 3)],
    ),  # double charge (two same-day)
    customer(
        "Ivan Petrov",
        "ivan.petrov@example.com",
        "free",
        signup_days_ago=150,
        orders=[order("10432", "Portable SSD", 129.99, "delayed", 10, "1Z8B2Q9910")],
    ),  # order 10432 never arrived
    customer("Julia Kim", "julia.kim@example.com", "free", signup_days_ago=120),  # change email how-to (KB)
    customer(
        "Kofi Mensah",
        "kofi.mensah@example.com",
        "pro",
        signup_days_ago=80,
        charges=[charge(9.99, "Prorated upgrade (Free to Pro)", 2)],
    ),  # why charged 9.99
    customer(
        "Lena Brooks",
        "lena.brooks@example.com",
        "free",
        signup_days_ago=45,
        orders=[order("10455", "Webcam 1080p", 59.99, "in_transit", 4, "1Z5C3R7742")],
    ),  # track my package
    # --- the account states the generated crowd never produces -----------------
    # Everyone above is active. account_status and subscription_status are what the
    # agent's account_status / subscription_details tools return, so a state that
    # exists in no customer is a branch the agent can never be asked about. Two of
    # each, so a demo question about "a suspended account" is never a sample of one.
    customer(
        "Marco Silva",
        "marco.silva@example.com",
        "pro",
        account_status="suspended",
        subscription_status="past_due",
        signup_days_ago=420,
        charges=[charge(19.99, "Pro plan monthly", 40)],
        past_tickets=[{"subject": "Why can I not sign in", "body": "My account says suspended and I do not know why.",
                       "category": "account", "priority": "high", "sentiment": "negative",
                       "resolution": "Explained the failed payment and how to clear it.", "csat": 6, "source": "chat"}],
    ),  # suspended for non-payment
    customer(
        "Nadia Rahman",
        "nadia.rahman@example.com",
        "max",
        account_status="suspended",
        subscription_status="past_due",
        signup_days_ago=610,
        charges=[charge(49.99, "Max plan monthly", 35)],
    ),  # a second suspended account, so the state is never a sample of one
    customer(
        "Omar Haddad",
        "omar.haddad@example.com",
        "pro",
        account_status="closed",
        subscription_status="cancelled",
        signup_days_ago=800,
        past_tickets=[{"subject": "Closing my account", "body": "Please close my account and delete my data.",
                       "category": "account", "priority": "medium", "sentiment": "neutral",
                       "resolution": "Account closed and deletion confirmed in writing.", "csat": 9,
                       "source": "voice_transcript"}],
    ),  # closed, and one of the few voice_transcript tickets in the estate
    customer(
        "Priya Raman",
        "priya.raman@example.com",
        "max",
        account_status="closed",
        subscription_status="cancelled",
        signup_days_ago=950,
    ),  # a second closed account
    customer(
        "Quentin Roy",
        "quentin.roy@example.com",
        "max",
        subscription_status="refund_pending",
        signup_days_ago=260,
        charges=[charge(49.99, "Max plan monthly", 8)],
        orders=[order("10502", "Studio Monitor", 349.99, "delivered", 30, "1Z7D4T1188")],
    ),  # a second refund_pending, plus a high-value delivered order
    customer(
        "Rosa Iglesias",
        "rosa.iglesias@example.com",
        "max",
        signup_days_ago=340,
        orders=[order("10517", "Docking Station", 189.99, "processing", 1, "")],
        past_tickets=[{"subject": "Escalating a repeat fault", "body": "This is the third time this has happened.",
                       "category": "technical", "priority": "critical", "sentiment": "negative",
                       "resolution": "Escalated to engineering; replacement issued.", "csat": 5, "source": "jira"}],
    ),  # the only 'critical' priority in the seeded history, arriving over Jira
]


# realistic past tickets, drawn on by the background cast; each is internally coherent
# (subject <-> category <-> priority <-> resolution <-> csat) so history makes sense
# the five source values app/state.py::Ticket accepts. voice_transcript has a parser
# but no endpoint (the known FR-1 gap), so seeding it is the only place it is visible.
TICKET_SOURCES = ["email", "form", "chat", "jira", "voice_transcript"]

PAST_TICKET_POOL = [
    {"subject": "Whole team locked out mid-launch", "body": "Nobody on our account can sign in and we go live in an hour.", "category": "technical", "priority": "critical", "sentiment": "negative", "resolution": "Restored access within the hour and issued a post-incident note.", "csat": 7},
    {"subject": "Payment taken twice on the same day", "body": "You charged the card twice for one renewal.", "category": "billing", "priority": "critical", "sentiment": "negative", "resolution": "Refunded the duplicate and added a duplicate-charge guard to the account.", "csat": 8},
    {"subject": "Unexpected charge on my card", "body": "I saw a charge I did not recognise.", "category": "billing", "priority": "medium", "sentiment": "neutral", "resolution": "Explained the charge and confirmed it was a valid subscription renewal.", "csat": 8},
    {"subject": "App would not open after an update", "body": "The app crashed on launch after updating.", "category": "technical", "priority": "medium", "sentiment": "negative", "resolution": "Walked the customer through a reinstall, which cleared the crash.", "csat": 7},
    {"subject": "Package arrived damaged", "body": "My order turned up with a cracked case.", "category": "shipping", "priority": "high", "sentiment": "negative", "resolution": "Arranged a free replacement shipment.", "csat": 9},
    {"subject": "Locked out of my account", "body": "I could not sign in after too many attempts.", "category": "account", "priority": "high", "sentiment": "negative", "resolution": "Verified identity and restored access.", "csat": 8},
    {"subject": "Refund for a cancelled order", "body": "I cancelled and wanted my money back.", "category": "refund", "priority": "medium", "sentiment": "neutral", "resolution": "Processed the refund within the 30-day window.", "csat": 9},
    {"subject": "How do I change my plan", "body": "I wanted to move from Pro to Max.", "category": "billing", "priority": "low", "sentiment": "positive", "resolution": "Explained the upgrade steps and prorated billing.", "csat": 8},
    {"subject": "Tracking had not updated", "body": "My parcel tracking was stuck for days.", "category": "shipping", "priority": "medium", "sentiment": "negative", "resolution": "Opened a carrier investigation; the parcel was located and delivered.", "csat": 7},
    {"subject": "Needed to update my email", "body": "I wanted to change my account email.", "category": "account", "priority": "low", "sentiment": "neutral", "resolution": "Guided the customer through the email change and confirmation.", "csat": 9},
]


def _background(n):
    out = []
    next_order = 20000  # sequential ids so background orders never collide (birthday-clash with random ids)
    for i in range(n):
        name = fake.name()
        email = fake.unique.email()
        plan = random.choices(["free", "pro", "max"], weights=[3, 4, 3])[0]
        signup = random.randint(30, 900)

        charges = []
        if plan != "free":
            months = min(6, signup // 30)  # a handful of recent monthly charges
            charges = [charge(PLANS[plan], f"{plan.title()} plan monthly", 30 * m + random.randint(0, 5)) for m in range(months)]

        orders = []
        for _ in range(random.randint(0, 4)):
            status = random.choice(["delivered", "in_transit", "processing", "delayed"])
            tracking = fake.bothify("1Z####??####") if status != "processing" else None
            orders.append(
                order(
                    str(next_order),
                    random.choice(ITEMS),
                    round(random.uniform(15, 200), 2),
                    status,
                    random.randint(1, 120),
                    tracking,
                )
            )
            next_order += 1

        past = [dict(pt) for pt in random.sample(PAST_TICKET_POOL, random.randint(0, 2))]
        # every source the canonical Ticket allows appears in the seeded history, not
        # just email: the intake normaliser handles five and only one was ever exercised
        for k, pt in enumerate(past):
            pt["source"] = TICKET_SOURCES[(i + k) % len(TICKET_SOURCES)]

        out.append(customer(name, email, plan, signup_days_ago=signup, orders=orders, charges=charges, past_tickets=past))
    return out


# the whole universe: the 12 wired customers + 100 realistic extras
CUSTOMERS = BENCH + _background(100)

if __name__ == "__main__":
    print(f"universe: {len(CUSTOMERS)} customers")
    print(f"  with orders : {sum(1 for c in CUSTOMERS if c['orders'])}")
    print(f"  with charges: {sum(1 for c in CUSTOMERS if c['charges'])}")
