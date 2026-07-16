from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.store import _connect  # reuse the same DB connection


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
        # new columns added as a migration seam, same pattern as store.init_db
        conn.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS plan TEXT")
        conn.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS account_status TEXT")
        conn.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS subscription_status TEXT")
        conn.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS signup_date DATE")


def seed_crm(customers) -> None:
    with _connect() as conn:
        for c in customers:
            conn.execute(
                """INSERT INTO customers
                     (email, name, tier, orders, plan, account_status, subscription_status, signup_date)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (email) DO UPDATE SET
                     name=EXCLUDED.name, tier=EXCLUDED.tier, orders=EXCLUDED.orders, plan=EXCLUDED.plan,
                     account_status=EXCLUDED.account_status, subscription_status=EXCLUDED.subscription_status,
                     signup_date=EXCLUDED.signup_date""",
                (c["email"], c["name"], c["tier"], Jsonb(c["orders"]), c["plan"], c["account_status"], c["subscription_status"], c["signup_date"]),
            )


def lookup(email: str) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT * FROM customers WHERE email = %s", (email,))
        return cur.fetchone()
