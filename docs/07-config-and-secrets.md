# 07. Configuration and Secrets

**Version 1, 2026-07-28.**

## 1. Rules

- Every real value lives in a `.env` file at the repository root, which is git-ignored and never committed. The repository carries only `.env.example` with blank placeholders.
- Nothing secret goes in code, in the compose file, or in these documents.
- The lane URL and token are read the moment the model router is imported, so the API will not start without them regardless of which model tier is selected.
- A blank value is not the same as an absent one. Where a default matters, the code falls back on blank as well as missing.

## 2. Variables

### Model lanes

| Name | Required | Meaning |
|---|---|---|
| `PRIVATE_LANE_URL` | yes | HTTPS endpoint of the small open-weight model on serverless GPU |
| `REVIEW_LANE_URL` | yes | HTTPS endpoint of the larger open-weight model |
| `PRIVATE_LANE_TOKEN` | yes | Shared secret both lane endpoints require |
| `MODEL_TIER` | no, defaults `dev` | `dev` runs everything on the small model; `local` puts reasoning and hard replies on the larger one; `full` unlocks the cloud lane |
| `ANTHROPIC_API_KEY` | only for `full` | Cloud lane credential |

### Application

| Name | Required | Meaning |
|---|---|---|
| `DATABASE_URL` | yes | Postgres connection string. Use `127.0.0.1` rather than `localhost` to force IPv4 |
| `AUTH_SECRET` | yes | Signs session cookies and password-reset tokens. Changing it logs everyone out |
| `AGENT_MODE` | no, defaults `deterministic` | `deterministic` or `autonomous` |
| `BRAND_NAME`, `BRAND_TAGLINE` | no | Client branding shown in the portal |

### Email channel

| Name | Required | Meaning |
|---|---|---|
| `EMAIL_USER`, `EMAIL_PASSWORD` | for mail features | Mailbox credentials. Use an application-specific password, never a primary account password |
| `IMAP_HOST` | no, defaults to Gmail | Inbound mail host |
| `SMTP_HOST`, `SMTP_PORT` | no, defaults to Gmail | Outbound mail host |

Mail is optional. Without it, ticket intake and replies still work in-app; only the mailbox sync and outbound email are unavailable.

### Jira channel

| Name | Required | Meaning |
|---|---|---|
| `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` | for Jira features | Site, account, token, and which project to poll |

## 3. Where secrets actually live

| Secret | Home |
|---|---|
| Lane token | The `.env` file on each machine, and a platform secret on the GPU service side |
| GPU platform credentials | The platform's own token file in the user profile, on the personal machine only, never in the repository |
| Cloud model key | The `.env` file, only needed for the full tier |
| Mailbox and Jira tokens | The `.env` file |
| Database password | The `.env` file, and it must match the compose file's value |

## 4. Common configuration mistakes

| Symptom | Cause |
|---|---|
| The API will not start, complaining about a missing key | A lane URL or token is absent |
| Database authentication failed | `DATABASE_URL` disagrees with the compose file's credentials. Postgres only applies those on a first initialisation of an empty volume, so the two must be made to agree, and the volume re-initialised if it was created with the old value |
| Everyone is signed out after a restart | `AUTH_SECRET` changed |
| Ticket processing and seeding hang, then fail | A local proxy is intercepting the vector database's gRPC port. Exclude localhost, see [08-runbook.md](08-runbook.md) |

## 5. Spend control

The GPU lane bills per wake, and a cold wake costs real money, so a hard spend cap is set on the platform dashboard and every measurement run is batched into one warm window. Cost estimates per ticket are shown on the metrics dashboard.
