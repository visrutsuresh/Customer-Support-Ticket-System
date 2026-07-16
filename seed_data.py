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
            {
                "subject": "Refund request",
                "body": "Cancelled and want a refund.",
                "resolution": "Refund requested, pending review.",
            }
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
        past_tickets=[{"subject": "App crash", "body": "App crashed on launch.", "resolution": "Advised reinstall; monitoring."}],
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
]


def _background(n):
    out = []
    for _ in range(n):
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
                    str(random.randint(20000, 99999)),
                    random.choice(ITEMS),
                    round(random.uniform(15, 200), 2),
                    status,
                    random.randint(1, 120),
                    tracking,
                )
            )

        past = []
        if random.random() < 0.3:
            past = [{"subject": "Previous question", "body": "Had an issue before.", "resolution": "Resolved by support."}]

        out.append(customer(name, email, plan, signup_days_ago=signup, orders=orders, charges=charges, past_tickets=past))
    return out


# the whole universe: the 12 wired customers + 100 realistic extras
CUSTOMERS = BENCH + _background(100)

if __name__ == "__main__":
    print(f"universe: {len(CUSTOMERS)} customers")
    print(f"  with orders : {sum(1 for c in CUSTOMERS if c['orders'])}")
    print(f"  with charges: {sum(1 for c in CUSTOMERS if c['charges'])}")
