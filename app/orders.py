from psycopg.rows import dict_row

from app.store import _connect


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
