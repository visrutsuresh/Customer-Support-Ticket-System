# 13. Privacy and Data Handling

**Version 1, 2026-07-28.**

## 1. Position

All data in this system is synthetic. No real customer information has ever been processed. The privacy design exists so that the architecture does not have to change if real data ever arrives, and so the privacy claim can be demonstrated rather than asserted.

## 2. What personal data the system touches

| Data | Where it comes from | Where it is stored |
|---|---|---|
| Name and email address | The account, or an inbound email or Jira issue | The accounts table and the ticket row |
| Ticket subject and body, which may contain anything the customer typed | The portal, a mailbox, or Jira | The ticket row, inside the stored state |
| Conversation thread | Replies from both sides, plus internal staff notes | Inside the stored state |
| Attachments | Staff upload | The attachments table, as bytes |
| Satisfaction rating | The customer on resolve | The ticket row |

Internal notes are stored in the same thread but carry a role that the customer-safe view filters out, through one shared function so no reader can forget.

## 3. The sensitivity decision

Before any model is called, three checks run:

1. A pattern scan for email addresses, phone numbers, national identifier formats, and card numbers validated by checksum.
2. A category rule: refunds, billing and account tickets are treated as sensitive by default.
3. A model judgement on the ticket text, covering financial, identity, health, authentication, legal and protected-trait information.

Any one of the three makes the ticket sensitive. The result is recorded on the ticket with its reasons.

## 4. Where data flows

| Flow | Sensitive ticket | Non-sensitive ticket |
|---|---|---|
| Classification and reasoning | Self-hosted open-weight model on a private GPU endpoint | Same, by default |
| Reply drafting | Private GPU endpoint only | Private endpoint, or a cloud model when the full tier is enabled |
| Retrieval and embedding | Local vector database, embeddings computed on the machine | Same |
| Storage | Local Postgres | Same |

**Nothing sensitive is ever sent to a third-party model provider.** That is enforced by the routing table: the private lane maps only to the self-hosted endpoints, and there is no fallback path from private to cloud. If the private lane is unavailable, the ticket fails visibly rather than being downgraded.

The one qualification worth stating: the private lane is self-hosted on rented GPU infrastructure, not on premises. The model weights and the runtime are ours and no provider trains on the traffic, but the data does leave the local machine over an authenticated HTTPS connection to that endpoint.

## 5. Outbound leak control

Before any reply is judged compliant, the draft is scanned with the same pattern set. A reply that carries personal data fails review, which either forces a regeneration or escalates it to a human. This is the control against the model echoing sensitive input, or pulling another customer's detail out of retrieved material.

## 6. Retention

| Data | Retention |
|---|---|
| Live tickets | Kept indefinitely |
| Resolved tickets | Archived in place under a new identifier, still queryable by administrators |
| Resolutions filed into the knowledge base | Kept indefinitely, and retrievable for future tickets |
| Accounts | Kept until deleted by hand |
| Attachments | Kept with the ticket |

There is no automatic deletion, no retention schedule, and no subject-access or erasure workflow. On synthetic data that is acceptable; with real data it would not be, and it is the first thing to build.

## 7. Access

Three roles. A customer reaches only tickets matching their account address, which since 2026-07-29 is asserted at signup rather than proved (ADR-014). Staff reach the live queue and, from a live ticket, that one customer's past tickets. Administrators reach everything including the raw archive and the templates. Internal notes are never exposed to customers by any route.

## 8. Learning loop and privacy

Resolving a ticket files the resolution into the knowledge base, where it can be retrieved for later tickets from other customers. Today the entry is the reply text that was actually sent, which had already passed the outbound personal-data scan. That scan is therefore doing double duty: it protects the customer receiving the reply, and it keeps the shared knowledge base clean. If real data were introduced, this loop would need an explicit redaction step rather than relying on that scan.

## 9. Gaps to close before real data

1. A retention schedule and a deletion path, including from the knowledge base.
2. An explicit redaction step on the learning write-back.
3. Encryption at rest for both stores, and HTTPS in transit for the browser session.
4. A record of which model saw which ticket, retained for audit.
