import os
import psycopg #type:ignore
from dotenv import load_dotenv
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb #type:ignore
from psycopg.rows import dict_row #type:ignore
from datetime import timedelta

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]

#minutes from ticket arrival to the resolution deadline, by priority
SLA_RESOLUTION_MINUTES = {"critical": 60, "high": 120, "medium": 180, "low": 240}

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
                lifecycle TEXT DEFAULT 'open',
                created_at TIMESTAMPTZ,
                due_at TIMESTAMPTZ,
                tags JSONB DEFAULT '[]',
                state JSONB
            )
        """)
        conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS lifecycle TEXT DEFAULT 'open'")
        conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'")
        conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS due_at TIMESTAMPTZ")

def save(state: dict) -> None:
    t = state["ticket"]
    c = state.get("classification", {})
    d = state.get("decision", {})
    assignee = (d.get("assignee") or {}).get("name")

    priority = (c.get("priority") or "medium").lower()
    minutes = SLA_RESOLUTION_MINUTES.get(priority,SLA_RESOLUTION_MINUTES["medium"])
    due_at = t.created_at + timedelta(minutes=minutes)

    with _connect() as conn:
        conn.execute(
            """INSERT INTO tickets
                 (ticket_id, subject, category, priority, action, assignee, human_status, created_at,due_at, state)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (ticket_id) DO UPDATE SET
                 subject=EXCLUDED.subject, category=EXCLUDED.category, priority=EXCLUDED.priority,
                 action=EXCLUDED.action, assignee=EXCLUDED.assignee,
                 human_status=EXCLUDED.human_status, created_at=EXCLUDED.created_at,due_at=EXCLUDED.due_at, state=EXCLUDED.state""",
            (t.ticket_id, t.subject, c.get("category"), c.get("priority"),
             d.get("action"), assignee, "pending", t.created_at,due_at,
             Jsonb(jsonable_encoder(state))),
        )

def save_pending(ticket_id, subject, body, source, name, email, created_at) -> None:
    # store a ticket as "processing" BEFORE the pipeline runs, so the customer's submit is instant
    minimal = {
        "ticket": {"subject": subject, "body": body, "source": source,
                   "customer_name": name, "customer_email": email},
        "classification": {}, "decision": {}, "draft": {},
    }
    with _connect() as conn:
        conn.execute(
            """INSERT INTO tickets (ticket_id, subject, human_status, created_at, state)
               VALUES (%s, %s, 'processing', %s, %s)
               ON CONFLICT (ticket_id) DO NOTHING""",
            (ticket_id, subject, created_at, Jsonb(minimal)),
        )

def list_all(status=None, category=None,tag=None,q=None) -> list[dict]:
    clauses,params = [],[]
    if status:
        clauses.append("human_status =%s")
        params.append(status)
    if category:
        clauses.append("LOWER(category)=LOWER(%s)")
        params.append(category)
    if tag:
        clauses.append("tags @> %s::jsonb")
        params.append(Jsonb([tag]))
    if q:
        clauses.append("(subject ILIKE %s OR state -> 'ticket' ->>'body' ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(f"""SELECT ticket_id, subject, category, priority, action,
                              assignee, human_status,lifecycle, tags, created_at, due_at, (due_at IS NOT NULL AND due_at <now() AND lifecycle <> 'resolved') AS sla_breached
                       FROM tickets {where} ORDER BY created_at DESC""", params)
        return cur.fetchall()

def get(ticket_id: str) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT state, human_status, lifecycle, tags,due_at,(due_at IS NOT NULL AND due_at < now() AND lifecycle <> 'resolved') AS sla_breached FROM tickets WHERE ticket_id = %s", (ticket_id,))
        row = cur.fetchone()
    if row is None:
        return None
    state = row["state"]
    state["human_status"] = row["human_status"]
    state["lifecycle"] = row["lifecycle"]
    state["tags"] = row["tags"]
    state["due_at"] = row["due_at"]
    state["sla_breached"] = row["sla_breached"]
    return state

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

def metrics() -> dict:
    with _connect() as conn:
        cur= conn.cursor(row_factory=dict_row)
        cur.execute("""
        SELECT
         COUNT(*)    AS total,
         COUNT(*) FILTER (WHERE action = 'escalate') AS escalated,
         COUNT(*) FILTER (WHERE action = 'auto_send') AS auto_resolved
        FROM tickets
        """)
        result = cur.fetchone()

        cur.execute("""
        SELECT category, COUNT(*) AS n
        FROM tickets
        WHERE category  IS NOT NULL
        GROUP BY category
        ORDER BY n DESC
        """)
        by_category = cur.fetchall()

        return {**result, "by_category": by_category}

def append_message(ticket_id : str, role: str,body: str) -> bool:
    #push one turn onto state.messages and, when the customer writes, reopen the ticket
    with _connect() as conn:
        cur = conn.execute(
            """ UPDATE tickets
            SET state = jsonb_set(state, '{messages}', COALESCE(state-> 'messages','[]'::jsonb) || %s::jsonb), lifecycle = CASE WHEN %s = 'customer' THEN 'open' ELSE lifecycle END WHERE ticket_id=%s""",(Jsonb([{"role": role, "body": body}]),role, ticket_id),
        )
        return cur.rowcount>0

def set_lifecycle(ticket_id: str, lifecycle:str) ->bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE tickets SET lifecycle = %s WHERE ticket_id = %s",(lifecycle,ticket_id),
        )
        return cur.rowcount>0

def add_tag(ticket_id: str, tag:str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE tickets SET tags = tags || %s::jsonb WHERE ticket_id = %s AND NOT tags @> %s::jsonb",
            (Jsonb([tag]),ticket_id, Jsonb([tag])),
        )
        return cur.rowcount>0
def remove_tag(ticket_id: str, tag:str) -> bool:
    with _connect() as conn:
        cur = conn.execute("""
        UPDATE tickets SET tags = COALESCE(
            (SELECT jsonb_agg(t) FROM jsonb_array_elements(tags) t WHERE t <> %s::jsonb),'[]'::jsonb)
            WHERE ticket_id = %s""",(Jsonb(tag),ticket_id),
            )
    return cur.rowcount>0
