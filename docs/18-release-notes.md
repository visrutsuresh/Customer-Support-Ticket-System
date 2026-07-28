# 18. Release Notes

**Version 1, 2026-07-28.** Grouped by theme rather than by tag: this project has no version tags, 98 commits, first on 2026-07-05 and latest on 2026-07-28. Full detail is in the commit history.

## 2026-07-28 later, Ledger refined

- **The interface gained a component layer.** The styling already had a deliberate printed-paper identity and a full token set, but no named components, so every button and input was a hand-typed string of utility classes retyped across ten pages, and the pages had begun to drift apart. `globals.css` now defines the controls once (`.btn` and its variants, `.card`, `.panel`, `.input`, `.field`, `.badge`, `.chip`, `.row`), referencing only the existing tokens and the three font variables, and the five core pages (staff queue, staff ticket detail, customer thread, login, new request) were rewritten onto them. No endpoint changed, so the tests and both benchmark results stay valid by construction.
- **A font swap is now a one-file job:** the components name only the font variables, so replacing the three families means dropping new files into the fonts folder and editing `fonts.ts`.
- **Two dead pre-auth pages deleted.** One rendered the company metrics page to any visitor without a session (the API behind it did require one); the other duplicated the real staff ticket page. Neither was linked from anywhere.
- **The queue now shows the assignee.** The backend always computed it; only the detail page displayed it.
- Two literal colours that bypassed the token set were removed along the way.

## 2026-07-28, verification hard gate

- Sign-in now requires a verified email address. An unverified attempt is refused with its own distinct reason, so the interface can tell it apart from a wrong password, and no session is issued.
- Signing up no longer signs you in. The screen asks you to open the link, with a resend option that cannot be used to discover which addresses exist.
- **Breaking, and caught by testing:** the gate initially locked out every seeded staff and administrator account, because the seeder only marked the verified flag on accounts it created. The seeder now repairs existing accounts. Re-run it after pulling this change.
- A blank `FRONTEND_URL` now falls back to the local address instead of producing a link with no host.

## 2026-07-27, lifecycle, access control and the first tests

- Reopen a resolved ticket from either side, which renames it back to a live identifier and reconnects its tracker link.
- Archive browsing became administrator-only, with staff instead getting need-to-know access to one customer's history from inside a live ticket.
- Progress bars on rows and detail screens while a ticket is being processed.
- Email verification built: link sending, a verification page, and a check-your-inbox state.
- **The repository got its first automated tests**, ten of them, free and free of model calls. Fixed a real defect on the way: the API needed a live database merely to import, which made testing impossible.
- Performance dashboard with latency and estimated cost.

## 2026-07-21, resolve semantics and real auto-send

- Resolving became atomic and safe against a race with an in-flight pipeline run, so a resolved ticket can no longer be resurrected.
- Auto-send genuinely sends, immediately, through the channel the ticket arrived on, rather than waiting for a human click.
- A resolved ticket is locked against further action, returning a conflict rather than silently accepting it.
- Queue gained scope filtering, a status vocabulary, and tag and creation columns.
- Timestamps stamped as aware UTC; the previous naive local time skewed sort order and the service clocks by hours.

## 2026-07-18 to 2026-07-19, accounts and the interface

- Accounts, roles and cookie sessions, with ownership walls so a customer reaches only their own tickets.
- The full web interface: queue, ticket detail with the system's reasoning panel, customer portal, thread view, ratings.
- Project-tracker channel with reply-back and status sync.

## 2026-07-16 to 2026-07-17, agent quality and cost

- Twelve-tool universe for the autonomous agents, plus a coherent synthetic world of customers, orders and charges for those tools to read.
- Confidence bar recalibrated from 90 to 85 after correct answers scoring 87 were being escalated; escalation fell from a third of the batch to roughly one ticket in twelve.
- Tool-loop deduplication and a forced finish, so an agent cannot spin.
- Mailbox channel with a whole-run time cap, and one retry on timeout to absorb a cold model container.

## 2026-07-13 to 2026-07-14, from single answers to conversations

- Multi-turn threads with a lifecycle, replies that re-run the pipeline over the whole conversation, and knowledge write-back moved to the resolve action so only confirmed answers are learned.
- Helpdesk features: tags, search and filters, internal notes, service timers, ratings, templates, merge and link, attachments.

## 2026-07-12 and earlier, the skeleton

- The fixed pipeline with its ten nodes, the two-by-two model router, the private and cloud lanes, the knowledge base with a seeded corpus, the hash-chain audit trail, and the mode switch that keeps both the fixed and the autonomous pipelines available.

## Known issues carried forward

- The transcript intake format has a parser but no endpoint to reach it.
- A private-lane outage ends in an error status rather than an escalation to a person.
- Cloud token cost is not tracked, so full-tier runs under-report cost.
- Retrieval finds the right article in the top five 100 percent of the time but puts it first only 36 percent of the time.
- Merge, link, attachments and the templates library work and are tested at the API but still have no buttons on screen.
