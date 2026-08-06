# Enklima: AI support desk walkthrough

Runtime 4:32. AI processing and typing are shown at speed; everything else is real time.


## [0:00] file and autosend

**[0:00]** This is Enklima, a customer support system where AI agents read, triage and answer every ticket, and a person signs off anything the AI is not sure about. We start where a real customer starts.

**[0:07]** The customer portal. No ticket form anywhere. Quick starts for common problems, past entries below, and one writing line: typing here is already starting the conversation.

**[0:11]** The customer writes what happened in their own words, sped up here.

**[0:12]** Their words carry over into a guided chat.

**[0:14]** They pick a topic. The subject line is taken from their own first sentence, nothing is retyped.

**[0:17]** Filing starts the agent pipeline: classify the ticket, retrieve similar past tickets and knowledge articles, draft a reply, review it against company policy, then decide if it is safe to send without a human.

**[0:21]** The pipeline runs on a private GPU lane, shown at ten times speed. The customer just sees the team is on it.

**[0:30]** A how-to question is exactly what policy allows the machine to answer alone. This reply was retrieved from the knowledge base, drafted, compliance-checked and sent with no human in the loop. Routine answers go out at machine speed; risky ones wait for a person.


## [0:35] thread and resolve

**[0:41]** A ticket here is a conversation, not a one-shot form. The customer read the answer and wants one more thing.

**[0:44]** They just reply, sped up here.

**[0:45]** The reply re-runs the whole agent pipeline, and this time the agents read the full thread, not just the new message.

**[0:47]** Ten times speed again while the machine reads the whole thread and drafts.

**[0:55]** A second answer on the same conversation. Still no human involved, still policy-checked before it left.

**[0:59]** The customer got what they needed, so they close it themselves.

**[1:01]** And they score the experience, one to ten. That score feeds the metrics we will see later.

**[1:09]** Resolved, scored nine out of ten. That score feeds the team metrics. And resolving is not a dead end: reopening the request is one click and it goes straight back to the team.


## [1:13] critical refusal

**[1:19]** Now the stakes go up: it is not one customer stuck, it is a whole office.

**[1:23]** Same guided chat, sped up.

**[1:26]** Same pipeline.

**[1:30]** Ten times speed. The triage agent reads this as what it is: an outage taking out a whole office, which the rulebook classifies as critical. And critical never resolves itself, no matter what the draft looks like.

**[1:33]** So nothing went out on its own. The customer is told a specialist will follow up, and the ticket lands in front of a person.

**[1:43]** The staff queue. Every row carries the machine's triage: channel, category, priority, owner, and the clock to the promised answer time. The outage sits at critical, flagged for a person.

**[1:48]** Inside, the machine's verdict sits on the right: escalate, critical priority. The customer's account record and similar past tickets sit alongside as evidence.

**[1:52]** And this time there is no draft at all. Faced with a live outage, the drafting agent declined to answer: anything it invented about the cause would be a guess. The machine knows the edge of its own competence.

**[1:57]** So the specialist takes over in their own words, sped up here.

**[1:59]** Sent under a human name, with an owner and a clock on the promise. Machine triage at machine speed, human judgment where it counts.


## [2:03] channels

**[2:09]** Tickets do not only come from the portal. This desk watches three doors: the chat portal, a real support mailbox, and a real Jira project.

**[2:13]** Sync email reads the actual inbox over IMAP.

**[2:16]** One unread mail just became a ticket, marked with its channel, and the agent pipeline is already reading it. When staff answer, the reply will go back out as a real email.

**[2:21]** Same for Jira: issues raised by an engineering team come in through the API.

**[2:24]** A live Jira issue, now a triaged ticket in the same queue. Replies post back onto the Jira issue as comments.

**[2:29]** Inside the emailed ticket: same triage, same pipeline, and the footer says exactly where a reply will go: back to the sender's inbox.


## [2:36] desk tools

**[2:42]** The emailed invoice request, after the pipeline. This run is a gift for the demo: the drafting agent stumbled, its draft leaked internal fields and lost the required sign-off. The policy reviewer caught exactly that, failed it, and held everything.

**[2:48]** So the flawed draft sits here, plainly marked not sent, with three human buttons on it: approve and send, edit first, or dismiss. Nothing reached the customer. That is the review gate doing its one job.

**[2:53]** Dana takes the case over from the router's pick, one click.

**[2:56]** A tag for the books.

**[2:59]** First, an internal note for the next pair of hands. Customers never see these.

**[3:02]** The reissue checklist is attached, so the file travels with the case.

**[3:05]** The bad draft is dismissed.

**[3:07]** Instead, the macro shelf: approved reply templates for the common cases.

**[3:09]** One click loads it into the composer, flagged: edit before sending.

**[3:15]** Dana tailors it to the case, sped up here.

**[3:16]** And because this ticket walked in through the mailbox, the reply walks out the same door: a real email, under Dana's name.


## [3:20] approve

**[3:26]** One more ticket is waiting: the customer's follow-up on the duplicate charge. The pipeline drafted a full refund reply, and the review gate held it, because it commits money.

**[3:32]** This time the draft is exactly right. It names the double charge, which the machine checked against the recent charges on the rail, promises the refund, and adds a guard against a repeat. The human's job is thirty seconds of reading.

**[3:37]** Approve and send. The machine's words go out under a person's decision, and the ticket moves on.

**[3:47]** On the customer's screen, the refund confirmation has landed.

**[3:51]** Machine-drafted, human-approved, minutes end to end.


## [3:55] metrics and close

**[4:01]** Everything we just watched feeds the performance page, and these are measured numbers, not projections: total tickets, how many resolved with no human, escalation rate, first-contact resolution, the compliance pass rate, and customer scores like the nine we saw given.

**[4:06]** Cost is on the same page, and it is honest about itself: GPU cost per ticket and in total, cloud token cost, and each tile is labelled measured, estimate, or sample so nobody mistakes a guess for a fact.

**[4:11]** And a breakdown by category, so the team can see where the volume and the escalations actually come from.

**[4:19]** And it ends where it started, on the customer's side.

**[4:22]** The first question of the day, answered by the machine alone, resolved and scored by the customer.

**[4:26]** That is Enklima. Machine speed on every ticket, a human hand on every risky one, and every claim on the record.
