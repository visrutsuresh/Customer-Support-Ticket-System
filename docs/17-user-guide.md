# 17. User Guide

**Version 1, 2026-07-28.** For the people using the system, not the people building it. Two audiences: the customer filing a request, and the support agent handling it.

## Part one: the customer

### Creating an account

Open the portal, choose to sign up, and enter an email address and a password. You are signed in straight away: there is no email to open and nothing to confirm.

### Filing a request

Sign in, choose to make a new request, give it a short subject and describe the problem. Submit. The request appears immediately with a progress bar while the system works on it. You do not need to wait on the page.

### What happens next

One of three things:

- **You get an answer.** The reply appears in your thread, usually within a minute.
- **You get a question.** If something is missing, an order number for example, the system asks for it. Reply in the thread and it picks up again.
- **A person takes over.** For anything sensitive, urgent, or that the system is not confident about, a member of staff is assigned and you are told so.

Asking for a human in your message always brings a person in, with no automated reply first.

### Following up and closing

Your requests list shows everything you have filed and its state. Open one to read the thread and reply. When you are satisfied, mark it resolved and optionally leave a rating. If the answer turns out not to have worked, a resolved request can be reopened from the same screen.

## Part two: the support agent

### The queue

Signing in as staff opens the workspace. The queue lists live tickets with their status, category, priority, tags, assignee and age. Filter by status, category or tag, or search the text. A row showing a moving bar is still being processed.

Administrators can also switch the scope to the archive; staff cannot, and instead see one customer's past tickets from inside that customer's live ticket.

### Reviewing a ticket

Opening a ticket shows the conversation on one side and the system's work on the other: how it classified the ticket, whether it judged it sensitive, which knowledge articles it used and how strongly they matched, the drafted reply, the compliance verdict, and the decision with its reason.

Three actions:

| Action | Effect |
|---|---|
| **Approve** | Sends the draft to the customer through the channel the ticket arrived on and hands the conversation back to them. Approving an escalation that has no draft simply records your approval and sends nothing |
| **Edit** | Replace the wording, then send. If the reply had already gone out automatically, your edit corrects the thread record; the copy already delivered by email cannot be recalled |
| **Reject** | Marks the draft unusable. Nothing is sent |

You can also add an internal note, which the customer never sees, and add or remove tags.

### Related tickets

Two different jobs sit in the side panel, and they are not the same thing:

| Action | Effect |
|---|---|
| **Link** | A cross-reference. Both tickets stay open and stay separate. Useful when two customers report the same outage |
| **Fold in** | Folds another ticket into this one and **resolves** that other ticket. The button arms on the first press and fires on the second, because it closes something |

Existing relations show as chips: `↔` for a link, `◀` for a ticket that was folded in. If this ticket was itself folded into another, the panel says so and links you there. A ticket already merged once cannot be merged again.

### Attachments

The side panel lists every file on the ticket with its size, and each name downloads it. **Attach a file** accepts images, PDF, plain text and CSV up to 5 MB; anything else is refused with the reason stated on screen. A resolved ticket is locked, so the upload button disappears.

### Templates, used as macros

The templates library holds canned replies. On a ticket, the saved replies appear as a row of macro chips above the draft: click one and it replaces the draft, which you can then edit before sending. The chip stays marked so you can see which macro is in the box.

Only administrators can create, change or delete templates, and **authoring is still API-only**: there is no templates management screen, so the library is maintained through the API documentation page. Applying them is fully on screen.

### Bringing work in from elsewhere

Two buttons pull work into the queue: one syncs the mailbox and turns unread messages into tickets, ignoring automated mail, and the other pulls new issues from the connected project tracker. Replies go back out through whichever channel the ticket came from.

### Resolving

Resolving archives the ticket, closes the linked tracker issue if there is one, and files the resolution into the knowledge base so future tickets can retrieve it. A resolved ticket is locked: no more approvals, edits, notes or tags. Reopen it if it turns out not to be finished.

### The metrics page

Shows volume, how much was auto-resolved against escalated, the compliance pass rate, average handling time split into warm and cold runs, an estimated cost per ticket, average customer rating, and average time to resolution. It recalculates from live data every time you open it.

## Part three: things worth knowing

- **The first ticket after a quiet period is slow.** The private model server sleeps and takes about a minute to wake. This is why a demonstration starts with a throwaway ticket ten minutes early.
- **Sensitive tickets are handled differently on purpose.** Anything containing personal, financial, medical or legal detail is processed only on the private model, never by an outside provider, and the ticket says so.
- **The system never invents policy.** If the knowledge base does not cover a question, it is meant to ask or escalate rather than guess.
- **Everything is recorded.** Every step is written into a chain that shows if any past entry is altered.
