# 05. API Specification

**Version 1, 2026-07-28.** Base URL `http://localhost:8000`. A live, always-current version of this is served at `/docs` by the framework; this file is the reviewed narrative version.

## 1. Authentication

Sessions are a signed cookie named `enklima`, valid for seven days. Every endpoint below except `/`, `/config` and the auth routes requires an **active** account. Email verification was removed on 2026-07-29 (ADR-014), so an account's address is asserted, never proved.

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/auth/register` | `{email, password}` | 201 with the new account, always role `customer`. Opens no session, so the client signs in straight after |
| POST | `/auth/login` | form `username`, `password` | 204 and a session cookie; 400 `LOGIN_BAD_CREDENTIALS` |
| POST | `/auth/logout` | none | 204 |
| GET | `/users/me` | none | 200 with the current account |

Roles: `customer` (own tickets only), `staff` (the whole live queue), `admin` (staff powers plus templates and the archive).

## 2. Public

| Method | Path | Returns |
|---|---|---|
| GET | `/` | Health, plus which pipeline mode and model tier are active |
| GET | `/config` | Brand name and tagline for the portal |

## 3. Tickets

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/tickets` | any signed-in account | Returns immediately with `{ticket_id, status: "processing"}`; the pipeline runs in the background. A customer's identity always overrides any address in the payload |
| GET | `/my/tickets` | customer | The caller's own tickets |
| GET | `/tickets` | staff | The queue. Filters: `status`, `category`, `tag`, `q` (free text), `scope` (`live` for everyone, anything else is admin only, 403 otherwise) |
| GET | `/tickets/{id}` | staff | The full stored state |
| GET | `/tickets/{id}/history` | staff | That customer's other tickets, unlocked by having this one open |
| GET | `/tickets/{id}/thread` | owner or staff | The customer-safe message list, internal notes stripped |
| POST | `/tickets/{id}/reply` | owner or staff | Adds a customer turn and re-runs the pipeline in the background |
| POST | `/tickets/{id}/resolve` | owner or staff | Optional `{csat: 1-10}`. Archives the ticket, cancels any in-flight run, closes the Jira issue if there is one, and files the resolution back into the knowledge base |
| POST | `/tickets/{id}/reopen` | staff | Brings an archived ticket back; 409 if it is not a reopenable archived ticket |
| POST | `/my/tickets/{id}/reopen` | customer | Same, for the owner |

`POST /tickets` accepts `{subject, body, source, name?, email?}`. `source` must be one of `chat`, `form`, `email`, `voice_transcript`, `jira`; anything else is rejected as malformed intake.

## 4. Review actions

| Method | Path | Who | Effect |
|---|---|---|---|
| POST | `/tickets/{id}/approve` | staff | Sends the draft if there is one, adds it to the thread, and hands the ball to the customer. An escalation with no draft simply records the approval and sends nothing |
| POST | `/tickets/{id}/reject` | staff | Marks the draft rejected |
| POST | `/tickets/{id}/edit` | staff | `{reply}` replaces the draft. If the reply was already auto-sent, the thread copy is corrected and the status stays `sent` |
| POST | `/tickets/{id}/note` | staff | `{body}` adds an internal note, never visible to the customer |
| POST | `/tickets/{id}/tags` | staff | `{tag}` |
| DELETE | `/tickets/{id}/tags/{tag}` | staff | Removes it |
| POST | `/tickets/{id}/merge` | staff | `{duplicate_id}` folds that ticket into this one; 400 if the ids are equal, missing, or already merged |
| POST | `/tickets/{id}/link` | staff | `{other_id}` marks two tickets related |

A resolved ticket is locked: approve, reject, edit, note and tag all return 409.

## 5. Templates

| Method | Path | Who |
|---|---|---|
| GET | `/templates`, `/templates/{id}` | staff |
| POST, PUT, DELETE | `/templates`, `/templates/{id}` | admin |
| POST | `/tickets/{id}/apply-template` | staff, `{template_id}` overwrites the draft |

## 6. Attachments

| Method | Path | Limits |
|---|---|---|
| POST | `/tickets/{id}/attachments` | staff, multipart file. PNG, JPEG, GIF, WebP, PDF, plain text, CSV only. 5 MB ceiling, 413 above it, 400 on an empty file or a disallowed type |
| GET | `/tickets/{id}/attachments` | staff, the list |
| GET | `/attachments/{id}` | staff, downloads the bytes |

## 7. Channels and metrics

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/email/sync` | staff | Pulls unread mail into tickets; 502 if the mailbox is unreachable. Machine-generated mail is skipped and counted |
| POST | `/jira/sync` | staff | Pulls new issues into tickets and remembers the issue key; 502 if Jira is unreachable |
| GET | `/metrics` | staff | Volumes, escalation split, compliance pass rate, latency (warm and cold), estimated GPU cost, ratings, and resolution time |

## 8. Status codes used

| Code | Meaning here |
|---|---|
| 200, 201, 202, 204 | Success, created, accepted, success with no body |
| 400 | Bad credentials, invalid merge or link, bad attachment |
| 401 | No session, or a session for an account that is no longer active |
| 403 | Wrong role, someone else's ticket, archive browsing as non-admin |
| 404 | Unknown ticket, template, or attachment |
| 409 | The ticket is resolved and locked, or not reopenable |
| 413 | Attachment above 5 MB |
| 502 | An upstream channel (mail or Jira) failed |
