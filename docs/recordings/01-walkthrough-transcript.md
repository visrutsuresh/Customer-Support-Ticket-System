# Enklima, Customer Support Triage: Demo Walkthrough

Runtime 1:43. AI processing shown at 10x; everything else is real time.

**[0:00]** This is Enklima, a customer support system where AI agents read, triage and draft the answer to every ticket, and a person signs off anything the AI is not sure about. We start on the customer side.

**[0:07]** A customer files a request through a guided chat, no ticket form in sight.

**[0:10]** They pick a topic.

**[0:12]** And describe the problem in their own words. This one is spiky on purpose: an unauthorised charge, a chargeback already raised with the bank, and a lawyer in the wings.

**[0:26]** Filing the request starts the agent pipeline: classify the ticket, retrieve similar past tickets and knowledge articles, draft a reply, review it against company policy, then decide whether it is safe to send without a human.

**[0:31]** The pipeline runs on a private GPU lane, shown here at 10 times speed. The customer just sees that the team is on it.

**[0:33]** The agents recognised what this is: money at risk, a possible payment-data problem, and legal language. Policy says none of that gets an automated answer. So nothing was sent. The customer is told a specialist will follow up, and the ticket is routed to a person.

**[0:40]** Now the staff side of the same moment.

**[0:47]** The queue every agent run feeds. Each row already carries its AI triage: source, category, priority, assignee and SLA clock. Two tickets need a human right now, and the one the customer just filed is at the top.

**[0:51]** The first is a straightforward duplicate charge. The pipeline classified it, drafted a full refund reply, but held it for review because it commits money. The machine's verdict sits on the right: escalate, with the grounds and the confidence.

**[0:55]** The draft is waiting, clearly marked not sent, with the customer's history and similar past tickets alongside as evidence.

**[0:58]** The human reads it, agrees, and approves. One click, and the AI's draft goes out with a person's name on the decision.

**[1:06]** The ticket from our customer is stricter still. Faced with a chargeback and a lawyer, the drafting agent declined to answer at all: no draft, straight to a senior billing specialist. The AI knows the edge of its own competence.

**[1:10]** So the specialist answers in their own words.

**[1:17]** And sends. Same system, two different calls: approve the machine's draft, or take over entirely.

**[1:21]** Every ticket feeds the metrics: how many resolved without a human, time to first answer, cost per ticket, and how the autonomous mode compares against the fixed pipeline.

**[1:31]** Back on the customer's screen.

**[1:34]** The specialist's answer is here, minutes after filing. The AI did the reading, the triage and the routing; a person made every call that mattered.

**[1:39]** That is Enklima. AI speed on every ticket, a human hand on every risky one.
