from psycopg.rows import dict_row

from app.store import _connect  # reuse the same DB connection


def init_crm() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers(
                email   TEXT PRIMARY KEY,
                name    TEXT,
                tier    TEXT
            )
        """)
        # new columns added as a migration seam, same pattern as store.init_db
        conn.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS plan TEXT")
        conn.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS account_status TEXT")
        conn.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS subscription_status TEXT")
        conn.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS signup_date DATE")
        conn.execute("ALTER TABLE customers DROP COLUMN IF EXISTS orders")  # orders moved to their own table


def seed_crm(customers) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM customers")  # table is fully owned by the seed, wipe orphans then refill
        for c in customers:
            conn.execute(
                """INSERT INTO customers (email, name, tier, plan, account_status, subscription_status, signup_date)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (c["email"], c["name"], c["tier"], c["plan"], c["account_status"], c["subscription_status"], c["signup_date"]),
            )


def lookup(email: str) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT * FROM customers WHERE email = %s", (email,))
        return cur.fetchone()
