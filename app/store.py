import os
import psycopg
from dotenv import load_dotenv
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]

def _connect():
    return psycopg.connect(DATABASE_URL)

def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets(
                ticket_id TEXT PRIMARY KEY,
                subject TEXT,
                category TEXT,
                priority TEXT,
                action TEXT,
                assignee TEXT,
                human_status TEXT,
                created_at TIMESTAMPTZ,
                state JSONB
            )
        """)

def save(state: dict) -> None:
    t = state["ticket"]
    c = state.get("classification", {})
    d = state.get("decision", {})
    assignee = (d.get("assignee") or {}).get("name")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO tickets
                 (ticket_id, subject, category, priority, action, assignee, human_status, created_at, state)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (ticket_id) DO UPDATE SET
                 subject=EXCLUDED.subject, category=EXCLUDED.category, priority=EXCLUDED.priority,
                 action=EXCLUDED.action, assignee=EXCLUDED.assignee,
                 human_status=EXCLUDED.human_status, created_at=EXCLUDED.created_at, state=EXCLUDED.state""",
            (t.ticket_id, t.subject, c.get("category"), c.get("priority"),
             d.get("action"), assignee, "pending", t.created_at,
             Jsonb(jsonable_encoder(state))),
        )

def list_all() -> list[dict]:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("""SELECT ticket_id, subject, category, priority, action,
                              assignee, human_status, created_at
                       FROM tickets ORDER BY created_at DESC""")
        return cur.fetchall()

def get(ticket_id: str) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT state FROM tickets WHERE ticket_id = %s", (ticket_id,))
        row = cur.fetchone()
    return row["state"] if row else None

def set_status(ticket_id: str, status: str) -> bool:
    # human reviewer verdict: approved / rejected
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE tickets SET human_status = %s WHERE ticket_id = %s",
            (status, ticket_id),
        )
        return cur.rowcount > 0

def edit_reply(ticket_id: str, new_reply: str) -> bool:
    # reviewer rewrites the draft: patch draft.reply inside the jsonb state, mark edited
    with _connect() as conn:
        cur = conn.execute(
            """UPDATE tickets
               SET state = jsonb_set(state, '{draft,reply}', to_jsonb(%s::text)),
                   human_status = 'edited'
               WHERE ticket_id = %s""",
            (new_reply, ticket_id),
        )
        return cur.rowcount > 0
