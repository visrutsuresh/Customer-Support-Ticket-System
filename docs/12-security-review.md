# 12. Security Review

**Version 1, 2026-07-28.** A threat model for a single-machine demonstration system: what an attacker would try, and what stops them today.

## 1. Assets worth protecting

Customer ticket content and threads; account credentials; the model lane token; the mailbox and Jira credentials; the audit chain's integrity.

## 2. Trust boundaries

| Boundary | Who is on the other side |
|---|---|
| Browser to API | Anyone who can reach port 8000 |
| API to model lanes | An internet-reachable GPU endpoint, and optionally a cloud model provider |
| API to mailbox and Jira | Third-party services holding real credentials |
| API to data stores | Local Docker containers |

## 3. Threats and controls

| # | Threat | Control today | Residual risk |
|---|---|---|---|
| 1 | Someone signs up claiming an address they do not own, then reads that person's tickets | Sign-in is gated on a verified inbox; ticket ownership is matched on the account address, never on a form field | The verification email itself can be intercepted if the mailbox is compromised |
| 2 | Account enumeration through the resend endpoint | It answers 202 for every address, real or not | None material |
| 3 | Password guessing | Passwords are stored hashed by the auth library | **No rate limiting or lockout.** This is the clearest missing control |
| 4 | Session theft | Signed cookie, seven-day life, secret in the environment | The cookie is not marked secure because the demo runs over plain HTTP locally. That must change before any real deployment |
| 5 | A customer reads someone else's ticket | Every ticket route checks ownership against the account address | None known |
| 6 | Staff browse the whole archive | Archive scope is administrator-only, and staff instead get need-to-know access to one customer's history from a live ticket | An administrator can read everything, by design |
| 7 | Sensitive ticket content leaks to a third-party model | The lane decision is made before any model call and the private lane cannot reach a cloud provider | Detection of sensitivity is heuristic: a pattern scan, a category rule and a model judgement. A novel phrasing could be misjudged |
| 8 | An outbound reply leaks personal data | The draft is scanned during review and a hit fails the review | Same heuristic limit |
| 9 | The lane token is stolen and someone else spends the GPU budget | Shared-secret token, hard spend cap on the platform | The endpoint is internet reachable; the cap is the real backstop |
| 10 | The audit trail is edited to hide an action | Hash chain, with a verifier that returns the first broken entry | Tamper evident, not tamper proof. Nothing external notarises the chain |
| 11 | Malicious file upload | Type allowlist, 5 MB ceiling, files stored as bytes and served with the stored content type | Files are not virus scanned, and are served back with their declared type |
| 12 | Prompt injection through ticket text, aiming to make the agent misbehave or call a tool | Write tools require a confirmation code derived from the ticket; the compliance review inspects the draft before anything is sent; the human gate stands for everything not auto-sent | **Not systematically tested.** A crafted ticket steering retrieval or tone is plausible |
| 13 | Denial of service by flooding tickets | A per-run time cap stops one ticket jamming the queue | No rate limiting on ticket creation |
| 14 | Secrets committed to the repository | Secrets live only in a git-ignored environment file; the repository holds blank placeholders | A careless paste remains possible; nothing scans commits |

## 4. What would have to change before real users

In priority order:

1. Rate limiting and lockout on sign-in and on ticket creation.
2. HTTPS everywhere, with the session cookie marked secure.
3. A tested policy for prompt injection, including tool-call review.
4. Virus scanning of attachments, and serving them with a forced download type.
5. Secret scanning in the commit path, and rotation of the seeded development credentials.

## 5. Deliberate non-goals

No penetration test has been performed. No dependency vulnerability scanning is in place. There is no authorisation model beyond the three roles. All of this is consistent with a demonstration system on synthetic data, and none of it should be read as production readiness.
