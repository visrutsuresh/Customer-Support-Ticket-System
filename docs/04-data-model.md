# 04. Data Model

**Version 1, 2026-07-28.** Two stores: Postgres holds the system of record, Weaviate holds the searchable knowledge.

## 1. Postgres, database `tickets`

Tables are created at API startup by `store.init_db()`, which is idempotent: new columns are added with `ADD COLUMN IF NOT EXISTS`, so an existing database migrates itself on boot.

### `tickets`

| Column | Type | Meaning |
|---|---|---|
| `ticket_id` | TEXT, primary key | `T-xxxxxxxx` while live, `HIST-xxxxxxxx` once archived |
| `subject` | TEXT | Ticket title |
| `category`, `priority` | TEXT | Denormalised from the classification, for queue filters |
| `action` | TEXT | `auto_send` or `escalate`, the pipeline's decision |
| `assignee` | TEXT | Staff member named on escalation |
| `human_status` | TEXT | `pending`, `approved`, `rejected`, `edited`, `sent`, `error` |
| `lifecycle` | TEXT | `open`, `awaiting_customer`, `resolved` |
| `created_at`, `due_at`, `resolved_at` | TIMESTAMPTZ | Timestamps, stored aware in UTC |
| `tags` | JSONB | Auto and manual tags |
| `state` | JSONB | The entire pipeline state, including the audit chain and the message thread |
| `csat` | INT | Customer rating, 1 to 10, optional |
| `merged_into` | TEXT | Set when this ticket was folded into another |
| `customer_email` | TEXT | Ownership key for the customer view |
| `processing_seconds` | DOUBLE PRECISION | Wall clock of the last pipeline run, feeds the dashboard |

The `state` column is deliberately the whole object rather than a normalised expansion: the pipeline shape is still changing, and the audit requirement wants the record kept as produced.

### Supporting tables

| Table | Columns | Purpose |
|---|---|---|
| `ticket_links` | `a`, `b` (composite key) | Related-ticket links, stored once per pair |
| `jira_links` | `ticket_id`, `issue_key` | Maps a ticket to the Jira issue it came from |
| `templates` | `id`, `name`, `body`, `category`, `keywords`, `auto_use` | Canned replies; seeded once if the table is empty |
| `attachments` | `id`, `ticket_id`, `filename`, `content_type`, `size`, `data`, `created_at` | Files stored as bytes, 5 MB ceiling |

### Accounts

Managed by the auth library in its own table: id, email, hashed password, active flag, verified flag, superuser flag, and a `role` column of `customer`, `staff`, or `admin`. Passwords are stored only as hashes. **The verified flag is inert:** it belongs to the auth library's own model, and since email verification was removed on 2026-07-29 (ADR-014) nothing writes or reads it. It is left in place because dropping a library-owned column would need a migration for no gain.

## 2. Weaviate, collection `Knowledge`

| Property | Meaning |
|---|---|
| `title` | Article or past-ticket title |
| `content` | The body text that gets retrieved |
| `source` | `article` for curated knowledge, `ticket` for a past resolution |

Vectors are 384 numbers produced locally by a small embedding model, so no text is sent anywhere to be indexed. Search converts cosine distance to a 0 to 100 relevance score and drops anything below 60.

The collection grows by itself: resolving a ticket files the resolution back as a new `ticket` entry, which is the learning loop.

## 3. Message thread

Threads live inside `tickets.state.messages`, oldest first, each with a role:

| Role | Visible to the customer | Written by |
|---|---|---|
| `customer` | yes | The portal, an inbound email, or a Jira comment |
| `agent` | yes | An auto-sent reply, or a staff approval |
| `internal` | **no** | Staff notes |

One shared filter produces the customer-safe view, so no reader can forget to strip internal notes.

## 4. Identifiers

| Kind | Format |
|---|---|
| Live ticket | `T-` plus eight hex characters |
| Archived ticket | Same id with the prefix swapped to `HIST-` |
| Attachment, template | Auto-incrementing integer |
| Account | UUID |

Archiving renames rather than deletes, so a resolved ticket keeps a traceable identity, and reopening renames it back and reconnects its Jira link.

## 5. Retention and volume

All data is synthetic. Nothing is purged automatically: resolved tickets are archived in place and stay queryable by administrators. Current seeded volume is a few hundred knowledge entries and a few hundred tickets, which is the intended scale, see [11-nfr.md](11-nfr.md).

## 6. Backup and recovery

Both stores are Docker volumes on the developer machine. There is no scheduled backup; recovery means re-running the seed scripts, which is acceptable because the data is synthetic and reproducible. The commands are in [08-runbook.md](08-runbook.md).
