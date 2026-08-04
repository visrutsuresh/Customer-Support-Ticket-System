import os
from datetime import timedelta

import psycopg  # type:ignore
from dotenv import load_dotenv
from fastapi.encoders import jsonable_encoder
from psycopg.rows import dict_row  # type:ignore
from psycopg.types.json import Jsonb  # type:ignore

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]

# minutes from ticket arrival to the resolution deadline, by priority
SLA_RESOLUTION_MINUTES = {"critical": 60, "high": 120, "medium": 180, "low": 240}

# --- Performance Dashboard: cost + latency constants (added 2026-07-27) ---
# Modal bills GPU WALL-CLOCK time, not tokens. This is the private-lane GPU rate.
# Source: Modal pricing page (https://modal.com/pricing).
# TODO(confirm): verify the exact current A10G / T4 $/second on the Modal pricing page.
#   CLAUDE.md pins the privacy lane to gpu="T4"; the value below is the T4 rate.
GPU_DOLLARS_PER_SECOND = 0.000164  # Tesla T4 on Modal, ~= $0.59/hr (TODO confirm current rate)
# Heuristic only: a per-ticket wall-clock at/above this likely included a Modal cold-container spin-up.
COLD_START_THRESHOLD_S = 30.0
# Published Claude cloud-lane token prices (USD per token). Only MODEL_TIER='full' hits the cloud lane.
# Verified against the Anthropic price table (per MTok): haiku 4.5 = $1/$5, sonnet 4.6 = $3/$15.
# NOTE: per-ticket token counts are NOT captured yet, so these are defined but not yet applied.
# TODO: add server-side generate_seconds + token counts to modal_lane/llm_service.py (personal laptop)
#       for precise timing, and capture Anthropic usage in app/router.py for exact cloud cost.
CLAUDE_HAIKU_INPUT_PER_TOKEN = 1.00 / 1_000_000
CLAUDE_HAIKU_OUTPUT_PER_TOKEN = 5.00 / 1_000_000
CLAUDE_SONNET_INPUT_PER_TOKEN = 3.00 / 1_000_000
CLAUDE_SONNET_OUTPUT_PER_TOKEN = 15.00 / 1_000_000

# templates: (name, category, keywords, auto_use, body). auto_use OFF by default = manual only (8b auto-send opt-in).
DEFAULT_TEMPLATES = [
    (
        "ask_order_number",
        "refund",
        ["order number", "order id", "refund"],
        False,
        "Hi there, thanks for reaching out. So we can look into this, could you reply with your order number? Once we have it we will get this sorted right away.\n\nThe Support Team",
    ),
    (
        "password_reset",
        "account",
        ["password", "reset password", "can't log in", "cannot log in", "sign in"],
        True,
        "Hi there, sorry for the trouble signing in. Please use the 'Forgot password' link on the login page to set a new one. That reset link is valid for 30 minutes, so use it soon after requesting it.\n\nThe Support Team",
    ),
    (
        "shipping_delay",
        "shipping",
        ["where is my order", "shipping", "tracking", "delivery", "not arrived"],
        True,
        "Hi there, thanks for your patience. Your order is on its way but running a little behind. You can follow it with the tracking link in your shipping confirmation email. Let us know if it has not arrived in the next few days.\n\nThe Support Team",
    ),
]


_pool = None


def _connect():
    # one shared pool instead of a fresh TCP+TLS handshake per query: the classic
    # works-alone, falls-over-under-concurrency fix. Lazy so plain imports (tests,
    # seed scripts) never open sockets.
    global _pool
    if _pool is None:
        from psycopg_pool import ConnectionPool

        # timeout: a checkout against a dead database fails in seconds, so the
        # health check reports "down" instead of hanging the caller
        _pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=True, timeout=5)
    return _pool.connection()


def _seed_templates(conn):
    # only fills the shelf if it is empty, so restarts never pile up duplicates
    n = conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
    if n == 0:
        for name, category, keywords, auto_use, body in DEFAULT_TEMPLATES:
            conn.execute(
                "INSERT INTO templates (name,category,keywords,auto_use,body) VALUES (%s,%s,%s,%s,%s)",
                (name, category, Jsonb(keywords), auto_use, body),
            )


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
                state JSONB,
                csat INT
            )
        """)
        conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS lifecycle TEXT DEFAULT 'open'")
        conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'")
        conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS due_at TIMESTAMPTZ")
        conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS csat INT")
        conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS merged_into TEXT")
        conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS customer_email TEXT")
        conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS processing_seconds DOUBLE PRECISION")
        conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS ticket_links(
            a TEXT,
            b TEXT,
            PRIMARY KEY (a,b)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS jira_links(
            ticket_id TEXT PRIMARY KEY,
            issue_key TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS templates(
            id SERIAL PRIMARY KEY,
            name TEXT,
            body TEXT,
            category TEXT,
            keywords JSONB DEFAULT '[]',
            auto_use BOOLEAN DEFAULT false
            )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS attachments(
            id SERIAL PRIMARY KEY,
            ticket_id TEXT,
            filename TEXT,
            content_type TEXT,
            size INT,
            data BYTEA,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """)

        _seed_templates(conn)


def save(state: dict) -> None:
    t = state["ticket"]
    if is_historical(t.ticket_id):
        return  # resolved + refiled while the pipeline ran: never resurrect a zombie
    c = state.get("classification", {})
    d = state.get("decision", {})
    assignee = (d.get("assignee") or {}).get("name")

    priority = (c.get("priority") or "medium").lower()
    minutes = SLA_RESOLUTION_MINUTES.get(priority, SLA_RESOLUTION_MINUTES["medium"])
    due_at = t.created_at + timedelta(minutes=minutes)

    with _connect() as conn:
        conn.execute(
            """INSERT INTO tickets
                 (ticket_id, subject, category, priority, action, assignee, human_status, created_at,due_at, state, customer_email)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (ticket_id) DO UPDATE SET
                 subject=EXCLUDED.subject, category=EXCLUDED.category, priority=EXCLUDED.priority,
                 action=EXCLUDED.action,
                 -- a human's manual assignment outranks the pipeline's suggestion:
                 -- once the column holds a name, a late-finishing run must not wipe it
                 assignee=COALESCE(tickets.assignee, EXCLUDED.assignee),
                 human_status=EXCLUDED.human_status, created_at=EXCLUDED.created_at,due_at=EXCLUDED.due_at,
                 state=EXCLUDED.state, customer_email=EXCLUDED.customer_email""",
            (
                t.ticket_id,
                t.subject,
                c.get("category"),
                c.get("priority"),
                d.get("action"),
                assignee,
                "pending",
                t.created_at,
                due_at,
                Jsonb(jsonable_encoder(state)),
                t.customer_email,
            ),
        )


def sweep_stale_processing() -> list[str]:
    """Boot-time repair: the app runs one worker, so any ticket still 'processing'
    at startup was orphaned by a restart mid-pipeline and would spin forever."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE tickets SET human_status = 'error' WHERE human_status = 'processing' RETURNING ticket_id"
        )
        return [r[0] for r in cur.fetchall()]


def save_pending(ticket_id, subject, body, source, name, email, created_at) -> None:
    # store a ticket as "processing" BEFORE the pipeline runs, so the customer's submit is instant
    minimal = {
        "ticket": {"subject": subject, "body": body, "source": source, "customer_name": name, "customer_email": email},
        "classification": {},
        "decision": {},
        "draft": {},
        "messages": [{"role": "customer", "body": body}],  # visible in the portal thread immediately, not only after the pipeline saves
    }
    with _connect() as conn:
        conn.execute(
            """INSERT INTO tickets (ticket_id, subject, human_status, created_at, state, customer_email)
               VALUES (%s, %s, 'processing', %s, %s, %s)
               ON CONFLICT (ticket_id) DO NOTHING""",
            (ticket_id, subject, created_at, Jsonb(minimal), email),
        )


def add_jira_link(ticket_id: str, issue_key: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO jira_links (ticket_id, issue_key) VALUES (%s, %s) ON CONFLICT (ticket_id) DO NOTHING",
            (ticket_id, issue_key),
        )


def get_jira_link(ticket_id: str) -> str | None:
    with _connect() as conn:
        row = conn.execute("SELECT issue_key FROM jira_links WHERE ticket_id = %s", (ticket_id,)).fetchone()
        return row[0] if row else None


def list_by_email(email: str) -> list[dict]:
    # the customer portal's "my requests": tickets born from this email, newest first.
    # a ticket can exist as both T-x and HIST-x (old zombie rows); the archived one wins.
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            """SELECT ticket_id, subject, human_status, lifecycle, created_at
               FROM tickets WHERE lower(customer_email) = lower(%s) AND merged_into IS NULL
               ORDER BY created_at DESC LIMIT 200""",
            (email,),
        )
        rows = cur.fetchall()
    winner = {}
    for r in rows:
        sfx = r["ticket_id"].split("-", 1)[-1]
        if sfx not in winner or r["ticket_id"].startswith("HIST-"):
            winner[sfx] = r["ticket_id"]
    return [r for r in rows if winner[r["ticket_id"].split("-", 1)[-1]] == r["ticket_id"]]


def set_assignee(ticket_id: str, assignee: str | None) -> bool:
    with _connect() as conn:
        cur = conn.execute("UPDATE tickets SET assignee = %s WHERE ticket_id = %s", (assignee, ticket_id))
        return cur.rowcount > 0


# whitelisted ORDER BY fragments; the sort key never touches SQL as user text
SORTS = {
    "newest": "created_at DESC",
    "oldest": "created_at ASC",
    "sla": "(due_at IS NULL) ASC, due_at ASC, created_at DESC",  # most urgent deadline first, undated last
}


def list_all(status=None, category=None, tag=None, q=None, scope="live", limit=200, offset=0, sort="newest") -> list[dict]:
    clauses, params = ["merged_into IS NULL"], []
    if scope == "live":
        clauses.append("ticket_id NOT LIKE %s")
        params.append("HIST-%")
    elif scope == "archive":
        clauses.append("ticket_id LIKE %s")
        params.append("HIST-%")
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
    where = " WHERE " + " AND ".join(clauses)

    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            f"""SELECT ticket_id, subject, category, priority, action,
                              assignee, human_status,lifecycle, tags, created_at, due_at, (due_at IS NOT NULL AND due_at <now() AND lifecycle <> 'resolved') AS sla_breached,
                              state -> 'ticket' ->> 'source' AS source,
                              left(state -> 'ticket' ->> 'body', 90) AS preview
                       FROM tickets {where} ORDER BY {SORTS.get(sort, SORTS["newest"])} LIMIT %s OFFSET %s""",
            params + [limit, offset],
        )
        return cur.fetchall()


def get(ticket_id: str) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            "SELECT state, human_status, lifecycle, tags,due_at,(due_at IS NOT NULL AND due_at < now() AND lifecycle <> 'resolved') AS sla_breached,csat, merged_into FROM tickets WHERE ticket_id = %s",
            (ticket_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        state = row["state"]
        state["human_status"] = row["human_status"]
        state["lifecycle"] = row["lifecycle"]
        state["tags"] = row["tags"]
        state["due_at"] = row["due_at"]
        state["sla_breached"] = row["sla_breached"]
        state["csat"] = row["csat"]
        state["merged_into"] = row["merged_into"]

        cur.execute("SELECT a, b FROM ticket_links WHERE a = %s OR b = %s", (ticket_id, ticket_id))
        state["related"] = [r["b"] if r["a"] == ticket_id else r["a"] for r in cur.fetchall()]
        cur.execute("SELECT ticket_id FROM tickets WHERE merged_into = %s", (ticket_id,))
        state["merged_from"] = [r["ticket_id"] for r in cur.fetchall()]
    return state


def set_status(ticket_id: str, status: str) -> bool:
    # human reviewer verdict: approved / rejected
    with _connect() as conn:
        cur = conn.execute("UPDATE tickets SET human_status = %s WHERE ticket_id = %s", (status, ticket_id))
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


def replace_last_agent_message(ticket_id: str, body: str) -> bool:
    # retcon the newest agent turn: used when staff edit a reply that was already auto-sent
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT state -> 'messages' AS m FROM tickets WHERE ticket_id = %s", (ticket_id,))
        row = cur.fetchone()
        if row is None or not row["m"]:
            return False
        msgs = row["m"]
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i]["role"] == "agent":
                msgs[i]["body"] = body
                conn.execute("UPDATE tickets SET state = jsonb_set(state, '{messages}', %s) WHERE ticket_id = %s", (Jsonb(msgs), ticket_id))
                return True
    return False


def metrics() -> dict:
    # Cross-cutting: computed at the SHARED layer from stored ticket state, so BOTH pipelines
    # (deterministic graph.py + autonomous orchestrator.py) feed the same dashboard. Both write
    # decision.action ('escalate'/'auto_send') to the `action` column and compliance.verdict into
    # the jsonb `state`. Recomputed on every call, so latency/cost stay truthful as volume grows.
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            """
        SELECT
         COUNT(*) AS total,
         COUNT(*) FILTER (WHERE action = 'escalate') AS escalated,
         COUNT(*) FILTER (WHERE action = 'auto_send') AS auto_resolved,
         AVG(csat) AS avg_csat,
         COUNT(csat) AS csat_count,
         COUNT(*) FILTER (WHERE lifecycle = 'resolved') AS resolved_count,
         COUNT(*) FILTER (WHERE state -> 'compliance' ->> 'verdict' IS NOT NULL) AS compliance_reviewed,
         COUNT(*) FILTER (WHERE lower(state -> 'compliance' ->> 'verdict') = 'pass') AS compliance_passed,
         COUNT(processing_seconds) AS timing_count,
         AVG(processing_seconds) AS avg_processing_seconds,
         COALESCE(SUM(processing_seconds), 0) AS total_processing_seconds,
         COUNT(*) FILTER (WHERE processing_seconds >= %(cold)s) AS cold_count,
         AVG(processing_seconds) FILTER (WHERE processing_seconds >= %(cold)s) AS cold_avg_seconds,
         COUNT(*) FILTER (WHERE processing_seconds < %(cold)s) AS warm_count,
         AVG(processing_seconds) FILTER (WHERE processing_seconds < %(cold)s) AS warm_avg_seconds,
         COUNT(*) FILTER (WHERE resolved_at IS NOT NULL AND created_at IS NOT NULL) AS resolution_time_count,
         AVG(EXTRACT(EPOCH FROM (resolved_at - created_at))) FILTER (WHERE resolved_at IS NOT NULL AND created_at IS NOT NULL) AS avg_resolution_seconds
        FROM tickets
        """,
            {"cold": COLD_START_THRESHOLD_S},
        )
        r = cur.fetchone()

        cur.execute("""
        SELECT category, COUNT(*) AS n
        FROM tickets
        WHERE category  IS NOT NULL
        GROUP BY category
        ORDER BY n DESC
        """)
        by_category = cur.fetchall()

    def _f(v):
        return float(v) if v is not None else None

    total = r["total"] or 0
    escalated = r["escalated"] or 0
    auto_resolved = r["auto_resolved"] or 0
    decided = escalated + auto_resolved  # tickets that actually reached a decision
    timing_count = r["timing_count"] or 0
    reviewed = r["compliance_reviewed"] or 0
    passed = r["compliance_passed"] or 0
    total_gpu_seconds = _f(r["total_processing_seconds"]) or 0.0
    gpu_cost_total = total_gpu_seconds * GPU_DOLLARS_PER_SECOND

    return {
        # --- existing keys kept for backward compatibility ---
        "total": total,
        "escalated": escalated,
        "auto_resolved": auto_resolved,
        "avg_csat": _f(r["avg_csat"]),
        "csat_count": r["csat_count"] or 0,
        "by_category": by_category,
        # --- REAL: rates from stored decisions ---
        "decided": decided,
        "escalation_rate": (escalated / decided) if decided else None,
        "first_contact_resolution_rate": (auto_resolved / decided) if decided else None,
        "resolved_count": r["resolved_count"] or 0,
        # --- REAL: compliance PASS RATE (the review agent's stored verdict) ---
        "compliance": {
            "reviewed": reviewed,
            "passed": passed,
            "pass_rate": (passed / reviewed) if reviewed else None,
            "note": "share of reviewed replies the compliance agent passed (pass RATE, not ground-truth accuracy)",
        },
        # --- REAL: latency, cumulative running average recomputed every call ---
        "latency": {
            "sample_size": timing_count,
            "avg_seconds": _f(r["avg_processing_seconds"]),
            "cold": {"count": r["cold_count"] or 0, "avg_seconds": _f(r["cold_avg_seconds"])},
            "warm": {"count": r["warm_count"] or 0, "avg_seconds": _f(r["warm_avg_seconds"])},
            "cold_threshold_seconds": COLD_START_THRESHOLD_S,
            "note": "app-side wall-clock per ticket (pipeline invoke). cold/warm is a heuristic split on the threshold, not a Modal-reported cold start.",
        },
        # --- REAL (forward-looking): resolution time from timestamps ---
        "resolution_time": {
            "sample_size": r["resolution_time_count"] or 0,
            "avg_seconds": _f(r["avg_resolution_seconds"]),
            "note": "created_at -> resolved_at, real; only covers tickets resolved after resolved_at capture shipped (older/seeded tickets have no resolved_at)",
        },
        # --- COST: labelled running ESTIMATE ---
        "cost": {
            "estimate": True,
            "gpu_seconds_measured": total_gpu_seconds,
            "gpu_dollars_per_second": GPU_DOLLARS_PER_SECOND,
            "gpu_cost_total": gpu_cost_total,
            "priced_tickets": timing_count,
            "cost_per_ticket": (gpu_cost_total / timing_count) if timing_count else None,
            "cloud_token_cost": {
                "available": False,
                "note": "Claude 'full'-tier per-ticket token counts are not captured yet; exact cloud cost pending. Price constants defined in store.py.",
            },
            "note": "ESTIMATE. Modal bills GPU wall-clock; app-side wall-clock is used as a proxy for GPU-active seconds (overstates slightly). TODO: reconcile the computed total against the Modal dashboard.",
        },
        # --- SAMPLE: no real source ---
        "csat_improvement": {
            "value": 12.0,
            "unit": "percent",
            "sample": True,
            "note": "SAMPLE placeholder, not measured. No baseline-CSAT source exists to compute a real improvement.",
        },
    }


def append_message(ticket_id: str, role: str, body: str) -> bool:
    # push one turn onto state.messages and, when the customer writes, reopen the ticket
    with _connect() as conn:
        cur = conn.execute(
            """ UPDATE tickets
            SET state = jsonb_set(state, '{messages}', COALESCE(state-> 'messages','[]'::jsonb) || %s::jsonb), lifecycle = CASE WHEN %s = 'customer' THEN 'open' ELSE lifecycle END WHERE ticket_id=%s""",
            (Jsonb([{"role": role, "body": body}]), role, ticket_id),
        )
        return cur.rowcount > 0


def set_lifecycle(ticket_id: str, lifecycle: str) -> bool:
    # stamp resolved_at the first time a ticket becomes resolved (real resolution-time source)
    with _connect() as conn:
        cur = conn.execute(
            """UPDATE tickets
               SET lifecycle = %s,
                   resolved_at = CASE WHEN %s = 'resolved' AND resolved_at IS NULL THEN now() ELSE resolved_at END
               WHERE ticket_id = %s""",
            (lifecycle, lifecycle, ticket_id),
        )
        return cur.rowcount > 0

def set_processing_seconds(ticket_id: str, seconds: float) -> bool:
    # wall-clock of the shared api.py pipeline run for this ticket (latest run wins)
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE tickets SET processing_seconds = %s WHERE ticket_id = %s",
            (seconds, ticket_id),
        )
        return cur.rowcount > 0


def add_tag(ticket_id: str, tag: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE tickets SET tags = tags || %s::jsonb WHERE ticket_id = %s AND NOT tags @> %s::jsonb",
            (Jsonb([tag]), ticket_id, Jsonb([tag])),
        )
        return cur.rowcount > 0


def remove_tag(ticket_id: str, tag: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            """
        UPDATE tickets SET tags = COALESCE(
            (SELECT jsonb_agg(t) FROM jsonb_array_elements(tags) t WHERE t <> %s::jsonb),'[]'::jsonb)
            WHERE ticket_id = %s""",
            (Jsonb(tag), ticket_id),
        )
    return cur.rowcount > 0


def set_csat(ticket_id: str, score: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("UPDATE tickets SET csat = %s WHERE ticket_id = %s", (score, ticket_id))
        return cur.rowcount > 0


def list_templates() -> list[dict]:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT id, name, body, category, keywords, auto_use FROM templates ORDER BY name")
        return cur.fetchall()


def get_template(template_id: int) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT id, name, body, category, keywords, auto_use FROM templates WHERE id = %s", (template_id,))
        return cur.fetchone()


def create_template(name: str, body: str, category: str | None, keywords: list, auto_use: bool) -> dict:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            "INSERT INTO templates (name, body, category, keywords, auto_use) VALUES (%s, %s, %s, %s, %s) RETURNING id, name, body, category, keywords, auto_use",
            (name, body, category, Jsonb(keywords or []), auto_use),
        )
        return cur.fetchone()


def update_template(template_id: int, name: str, body: str, category: str | None, keywords: list, auto_use: bool) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            "UPDATE templates SET name = %s, body = %s, category = %s, keywords = %s, auto_use = %s WHERE id = %s RETURNING id, name, body, category, keywords, auto_use",
            (name, body, category, Jsonb(keywords or []), auto_use, template_id),
        )
        return cur.fetchone()


def delete_template(template_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM templates WHERE id = %s", (template_id,))
        return cur.rowcount > 0


def merge_tickets(duplicate_id: str, primary_id: str) -> bool:
    # fold the duplicate into the primary and move its messages over, close it, point it home
    if duplicate_id == primary_id:
        return False
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT ticket_id, merged_into FROM tickets WHERE ticket_id IN (%s, %s)", (duplicate_id, primary_id))
        found = {r["ticket_id"]: r for r in cur.fetchall()}
        if duplicate_id not in found or primary_id not in found:
            return False
        if found[duplicate_id]["merged_into"] is not None:
            return False  # already merged once, do not merge again
        conn.execute(
            """
            UPDATE tickets p
            SET state = jsonb_set(p.state, '{messages}',
                COALESCE(p.state -> 'messages', '[]'::jsonb) || COALESCE(d.state -> 'messages', '[]'::jsonb))
            FROM tickets d
            WHERE p.ticket_id = %s AND d.ticket_id = %s
        """,
            (primary_id, duplicate_id),
        )
        conn.execute(
            "UPDATE tickets SET lifecycle = 'resolved', merged_into = %s WHERE ticket_id = %s",
            (primary_id, duplicate_id),
        )
    return True


def link_tickets(a: str, b: str) -> bool:
    # relate two tickets without merging (symmetric, one card per pair)
    if a == b:
        return False
    lo, hi = sorted([a, b])
    with _connect() as conn:
        cur = conn.execute("SELECT ticket_id FROM tickets WHERE ticket_id IN (%s,%s)", (a, b))
        if len(cur.fetchall()) != 2:
            return False
        conn.execute("INSERT INTO ticket_links (a,b) VALUES (%s, %s) ON CONFLICT DO NOTHING", (lo, hi))
    return True


def add_attachment(ticket_id: str, filename: str, content_type: str, data: bytes) -> dict:
    # store the raw bytes; return metadata only (never ship the blob back on upload)
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            "INSERT INTO attachments (ticket_id, filename, content_type, size, data) VALUES (%s, %s, %s, %s, %s) RETURNING id, ticket_id, filename, content_type, size, created_at",
            (ticket_id, filename, content_type, len(data), data),
        )
        return cur.fetchone()


def list_attachments(ticket_id: str) -> list[dict]:
    # metadata only, no bytes, so the list stays light
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            "SELECT id, filename, content_type, size, created_at FROM attachments WHERE ticket_id = %s ORDER BY created_at",
            (ticket_id,),
        )
        return cur.fetchall()


def get_attachment(attachment_id: int) -> dict | None:
    # this one DOES pull the bytes, for the download endpoint
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT filename, content_type, data FROM attachments WHERE id = %s", (attachment_id,))
        return cur.fetchone()


def past_tickets(email: str) -> list[dict]:
    # this customer's resolved history, read from the tickets table by email
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            """SELECT subject, state FROM tickets
               WHERE customer_email = %s AND lifecycle = 'resolved'
               ORDER BY created_at DESC""",
            (email,),
        )
        return [{"subject": r["subject"], "resolution": (r["state"] or {}).get("resolution", "")} for r in cur.fetchall()]


def is_historical(ticket_id: str) -> bool:
    # has this ticket already been refiled under HIST-? if so its T- life is over
    hist_id = "HIST-" + ticket_id.split("-", 1)[-1]
    with _connect() as conn:
        return conn.execute("SELECT 1 FROM tickets WHERE ticket_id = %s", (hist_id,)).fetchone() is not None


def file_as_history(ticket_id: str) -> str:
    # a resolved ticket is a past ticket now: swap its T- prefix for HIST-, keep the 8-char suffix
    new_id = "HIST-" + ticket_id.split("-", 1)[-1]
    if new_id == ticket_id:  # already filed
        return ticket_id
    with _connect() as conn:
        conn.execute("UPDATE tickets SET ticket_id = %s WHERE ticket_id = %s", (new_id, ticket_id))
        conn.execute("UPDATE attachments SET ticket_id = %s WHERE ticket_id = %s", (new_id, ticket_id))
        conn.execute("UPDATE ticket_links SET a = %s WHERE a = %s", (new_id, ticket_id))
        conn.execute("UPDATE ticket_links SET b = %s WHERE b = %s", (new_id, ticket_id))
    return new_id


def reopen_from_history(ticket_id: str) -> str | None:
    # reverse of file_as_history: HIST-x becomes T-x again and rejoins the live queue.
    # the rename also reconnects jira_links rows, which never left the T- id.
    if not ticket_id.startswith("HIST-"):
        return None
    live_id = "T-" + ticket_id.split("-", 1)[-1]
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE ticket_id = %s", (live_id,)).fetchone():
            return None  # a live twin exists (old zombie row): refuse rather than collide
        cur = conn.execute(
            "UPDATE tickets SET ticket_id = %s, lifecycle = 'open', human_status = 'pending' WHERE ticket_id = %s",
            (live_id, ticket_id),
        )
        if cur.rowcount == 0:
            return None
        conn.execute("UPDATE attachments SET ticket_id = %s WHERE ticket_id = %s", (live_id, ticket_id))
        conn.execute("UPDATE ticket_links SET a = %s WHERE a = %s", (live_id, ticket_id))
        conn.execute("UPDATE ticket_links SET b = %s WHERE b = %s", (live_id, ticket_id))
    return live_id


def seed_history(customers) -> None:
    # resolved tickets per customer so past_tickets has data; deterministic ids, never touches real tickets.
    # every reporting field is filled so history reads like real, worked tickets.
    import hashlib
    from datetime import datetime, timedelta

    from app.roster import assign

    with _connect() as conn:
        conn.execute("DELETE FROM tickets WHERE ticket_id LIKE 'HIST-%'")  # clear old HIST, leave real tickets alone
        for c in customers:
            for i, pt in enumerate(c.get("past_tickets", [])):
                tid = "HIST-" + hashlib.sha1(f"{c['email']}-{i}".encode()).hexdigest()[:8]  # 8-char id, HIST prefix
                category = pt.get("category", "general")
                priority = pt.get("priority", "medium")
                sentiment = pt.get("sentiment", "neutral")
                escalated = priority in ("high", "critical")
                action = "escalate" if escalated else "auto_send"
                owner = assign(category, priority, tid)  # every worked ticket has an owner
                created = datetime(2026, 7, 15) - timedelta(days=20 + sum(ord(ch) for ch in tid) % 160)  # spread out
                due_at = created + timedelta(minutes=SLA_RESOLUTION_MINUTES.get(priority, SLA_RESOLUTION_MINUTES["medium"]))
                tags = [category] + ([priority] if escalated else []) + (["unhappy"] if sentiment == "negative" else [])
                state = {
                    "ticket": {"subject": pt["subject"], "body": pt["body"], "source": pt.get("source", "email"),
                               "customer_name": c["name"], "customer_email": c["email"]},
                    "classification": {"category": category, "priority": priority, "sentiment": sentiment},
                    "decision": {"action": action, "assignee": owner},
                    "messages": [{"role": "customer", "body": pt["body"]}, {"role": "agent", "body": pt["resolution"]}],
                    "resolution": pt["resolution"],
                }
                conn.execute(
                    """INSERT INTO tickets
                         (ticket_id, subject, category, priority, action, assignee, human_status, lifecycle,
                          created_at, due_at, tags, state, csat, customer_email)
                       VALUES (%s, %s, %s, %s, %s, %s, 'approved', 'resolved', %s, %s, %s, %s, %s, %s)""",
                    (tid, pt["subject"], category, priority, action, owner["name"], created, due_at, Jsonb(tags), Jsonb(state), pt.get("csat"), c["email"]),
                )
