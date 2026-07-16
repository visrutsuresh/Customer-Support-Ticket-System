from psycopg.rows import dict_row

from app.store import _connect


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
