"""The three seed-owned customer fixture tables: customers, orders, charges.

One module because all three had the identical init/seed/read shape and all three
are fully owned by the seed (wiped and refilled together by seed_universe.py).
Split across three files they were three copies of the same six lines.
"""

from psycopg.rows import dict_row

from app.store import _connect


# --- customers ---------------------------------------------------------------


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


# --- orders ------------------------------------------------------------------


def init_orders() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders(
                order_id   TEXT PRIMARY KEY,
                email      TEXT,
                item       TEXT,
                amount     NUMERIC(10, 2),
                status     TEXT,
                tracking   TEXT,
                ordered_at DATE
            )
        """)


def seed_orders(customers) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM orders")  # table is fully owned by the seed, so wipe and refill
        for c in customers:
            for o in c["orders"]:
                conn.execute(
                    """INSERT INTO orders (order_id, email, item, amount, status, tracking, ordered_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (o["order_id"], c["email"], o["item"], o["amount"], o["status"], o["tracking"], o["ordered_at"]),
                )


def lookup_order(order_id: str) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
        return cur.fetchone()


def orders_for(email: str) -> list[dict]:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT * FROM orders WHERE email = %s ORDER BY ordered_at DESC", (email,))
        return cur.fetchall()


# --- charges -----------------------------------------------------------------


def init_billing() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS charges(
                id          SERIAL PRIMARY KEY,
                email       TEXT,
                amount      NUMERIC(10, 2),
                description TEXT,
                charged_at  DATE
            )
        """)


def seed_billing(customers) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM charges")
        for c in customers:
            for ch in c["charges"]:
                conn.execute(
                    "INSERT INTO charges (email, amount, description, charged_at) VALUES (%s, %s, %s, %s)",
                    (c["email"], ch["amount"], ch["description"], ch["charged_at"]),
                )


def charges_for(email: str) -> list[dict]:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            "SELECT amount, description, charged_at FROM charges WHERE email = %s ORDER BY charged_at DESC",
            (email,),
        )
        return cur.fetchall()
