from app.store import _connect          # reuse the same DB connection
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row

def init_crm() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers(
                email   TEXT PRIMARY KEY,
                name    TEXT,
                tier    TEXT,
                orders  JSONB
            )
        """)

def seed_crm() -> None:
    people = [
        # --- demo customers (emails match demo.py tickets) ---
        ("alice@example.com", "Alice Tan", "free",
         [{"id": "ORD-2001", "item": "Annual Subscription", "status": "active"}]),
        ("bob@example.com", "Bob Rivera", "premium",
         [{"id": "ORD-2002", "item": "Pro Subscription", "status": "active", "refund_eligible": True}]),
        ("chen@example.com", "Chen Wei", "premium",
         [{"id": "ORD-2003", "item": "Pro Subscription", "status": "refund_pending", "days_pending": 14}]),
        ("dana@example.com", "Dana Okoro", "free",
         [{"id": "ORD-2004", "item": "Mechanical Keyboard", "status": "in_transit", "days_since_update": 3}]),
        ("evan@example.com", "Evan Lee", "free",
         [{"id": "ORD-2005", "item": "Smart Home Hub", "status": "delivered"}]),
        ("fiona@example.com", "Fiona Adams", "free", []),
        ("grace@example.com", "Grace Hall", "premium",
         [{"id": "ORD-2006", "item": "Mobile App Pro", "status": "active"}]),
        ("hana@example.com", "Hana Sato", "premium",
         [{"id": "ORD-2007", "item": "Monthly Subscription", "status": "charged"},
          {"id": "ORD-2008", "item": "Monthly Subscription", "status": "charged_duplicate"}]),
        # --- extra customers for realism ---
        ("ivan@example.com", "Ivan Petrov", "free",
         [{"id": "ORD-2009", "item": "USB-C Cable", "status": "delivered"}]),
        ("mei@example.com", "Mei Lin", "premium",
         [{"id": "ORD-2010", "item": "Noise-Cancelling Headphones", "status": "returned"}]),
    ]
    with _connect() as conn:
        for email, name, tier, orders in people:
            conn.execute(
                """INSERT INTO customers(email, name, tier, orders)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (email) DO NOTHING""",
                (email, name, tier, Jsonb(orders)),
            )

def lookup(email: str) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT * FROM customers WHERE email = %s", (email,))
        return cur.fetchone()
