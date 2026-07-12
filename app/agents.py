import json 
import re
from app.pii import scan
from app import router, tools
from app.kb import index_resolved

MAX_STEPS = 5

def _parse(raw:str) -> dict:
    #same trick as graph.py: grab the first {...} block the model emitted
    s, e = raw.find("{"), raw.rfind("}")
    return json.loads(raw[s:e+1])

CLASSIFY_SYSTEM = """
You are the Classification and Prioritization agent for customer support.
Decide the ticket's category, priority, business_impact, sentiment, difficulty, and whether it is sensitive.
You MAY look the customer up first to inform priority (a premium customer, or money at stake, raises it).

Tool available:
  crm_lookup(email) -> the customer's record (tier, order history) or null

Reply every turn with ONE JSON object, nothing else.
  To use the tool:  {"thought": "...", "action": "crm_lookup", "args": {"email": "<email>"}}
  To finish:        {"thought": "...", "action": "finish", "result": {"category": "...", "priority": "...", "business_impact": "...", "sentiment": "...", "difficulty": "...", "sensitive": true}}

Definitions:
  category:        [billing, technical, account, general, shipping, refund, feature_request, complaint]
  priority:        [Critical, High, Medium, Low]
  business_impact: [low, medium, high]
  sentiment:       [positive, neutral, negative]
  difficulty:      simple = a routine self-serve request a KB article answers in one step (password reset, order status).
                   complex = needs judgement, multiple steps, investigation, or careful handling (angry refund, account recovery, vague "nothing works", anything with money or a frustrated customer).
  sensitive:       true if the ticket contains or discusses sensitive data (financial/card/bank, government ID, health, passwords/2FA, legal matters, protected personal traits), else false.
"""

def classify_agent(ticket) -> dict:
    context = (f"Ticket:\n from: {ticket.customer_name} <{ticket.customer_email}>\n"
                f"  subject: {ticket.subject}\n body:{ticket.body}")
    
    transcript = ""

    for _ in range(MAX_STEPS):
        prompt = f"{CLASSIFY_SYSTEM}\n\n {context}\n{transcript}\nYour JSON:"
        move = _parse(router.think(prompt, max_new_tokens = 512))
        if move.get("action") == "finish":
            return move["result"]
        
        #else it's a tool call: run it, feed the result back into the loop
        obs = tools.run_tool(move.get("action"), move.get(f"args",{}))
        transcript += f"\nYou called {move.get('action')} ({move.get('args',{})}) -> {obs}"
    
    #fallback: it never finished in MAX_STEPS return a safe default
    return {"category": "general", "priority": "Medium", "business_impact": "medium",
            "sentiment": "neutral", "difficulty": "simple", "sensitive": False}

RETRIEVE_SYSTEM = """
You are the Knowledge Retrieval agent for customer support.
Find the knowledge-base articles most relevant to solving this ticket.
You may search more than once, refining the query, until you have good coverage.
Do not repeat a query you already ran. As soon as a search gives results you can use, finish.

Tool available:
  kb_search(query) -> a ranked list of articles, each {title, score}

Reply every turn with ONE JSON object, nothing else.
  To search:  {"thought": "...", "action": "kb_search", "args": {"query": "<query>"}}
  To finish:  {"thought": "...", "action": "finish", "result": {"relevant_titles": ["<title>", ...]}}
Search at least once before finishing. Keep only titles that genuinely help.
"""

def retrieve_agent(ticket) -> list:
    context=f"Ticket:\n subject: {ticket.subject}\n body:{ticket.body}"
    transcript = ""
    seen={} #title -> full article dict
    for _ in range(MAX_STEPS):
        prompt = f"{RETRIEVE_SYSTEM}\n\n{context}\n{transcript}\nYOUR JSON:"
        move = _parse(router.think(prompt,max_new_tokens=512))
        if move.get("action") =="finish":
            titles = move["result"].get("relevant_titles",[])
            chosen = [seen[t] for t in titles if t in seen]
            return chosen or list(seen.values())
        if move.get("action")== "kb_search":
            hits = tools.kb_search(move.get("args",{}).get("query",""))
            for h in hits:
                seen[h["title"]] = h
            summary = [{"title": h["title"], "score": h["score"]} for h in hits]
            transcript += f"\nkb_search({move['args']}) -> {summary}"
        else:
            transcript += f"\nunknown action {move.get('action')!r}"
    return list(seen.values())

GENERATE_SYSTEM = """
You are the Response Generation agent for customer support.
Decide how to handle this ticket, gathering any context you need first.
You MAY look the customer up to personalize the reply.

Tool available:
  crm_lookup(email) -> customer record (tier, orders) or null
Do not repeat a tool call you already made. Once you have what you need, finish.

Choose one outcome:
  answer   - the knowledge base covers it; we can reply helpfully
  question - a key detail is missing; we must ask the customer for exactly that
  escalate - the KB does not cover it, or it needs a human

Reply every turn with ONE JSON object, nothing else.
  To use the tool: {"thought":"...","action":"crm_lookup","args":{"email":"<email>"}}
  To finish:       {"thought":"...","action":"finish","result":{"kind":"answer|question|escalate","notes":"<what to say, what is missing, or why escalate>"}}
"""

def _write_reply(ticket,articles,customer,notes,lane,tier) -> str:
    kb_text = "\n\n".join(f"[{a['title']}]\n{a['content']}" for a in articles)
    greeting = f"Hi {ticket.customer_name.split()[0]}," if ticket.customer_name else "Hi there,"
    cust = (f"tier={customer['tier']}, orders={customer['orders']}"
            if customer else "no customer record found")
    prompt = f"""
    You are a warm, helpful customer support agent. Write a reply to this ticket.
    Customer: {cust}
    Subject: {ticket.subject}
    Body: {ticket.body}
    Guidance from triage: {notes}
    Use ONLY these knowledge base articles, do not invent details:
    {kb_text}
    Open with exactly "{greeting}" and sign off as 'The Support Team'. No placeholders like [NAME.
    """
    return router.generate_reply(prompt,lane,tier)

def generate_agent(ticket, articles, lane="cloud", tier="complex") -> dict:
    context = (f"Ticket:\n from: {ticket.customer_name} <{ticket.customer_email}>\n"
                f"  subject: {ticket.subject}\n body{ticket.body}")
    transcript,customer="", None
    for _ in range(MAX_STEPS):
        move = _parse(router.think(f"{GENERATE_SYSTEM}\n\n{context}\n{transcript}\nYour JSON:",max_new_tokens=512))
        if move.get("action") == "finish":
            r = move["result"]
            kind = r.get("kind", "escalate")
            if kind == "escalate":
                return {"kind": "escalate", "reply": ""}
            reply = _write_reply(ticket, articles, customer, r.get("notes", ""), lane, tier)
            return {"kind": kind, "reply": reply.strip()}
        if move.get("action") == "crm_lookup":
            customer = tools.crm_lookup(**move.get("args", {}))
            transcript += f"\ncrm_lookup -> {customer}"
        else:
            transcript += f"\nunknown action {move.get('action')!r}"
    return {"kind": "escalate", "reply": ""}      # fallback: never decided

REVIEW_SYSTEM = """
You are the Compliance and Quality Review agent for customer support.
Check the draft reply against the policy rules AND for factual accuracy.
You MAY look the customer up to verify any claim the reply makes about their account or orders.

Tool available:
  crm_lookup(email) -> customer record (tier, orders) or null

Reply every turn with ONE JSON object, nothing else.
  To use the tool: {"thought":"...","action":"crm_lookup","args":{"email":"<email>"}}
  To finish:       {"thought":"...","action":"finish","result":{"verdict":"pass|fail","issues":["<reason>", ...]}}
FAIL if the reply breaks a policy rule, or states something about the customer's account/orders
that the CRM contradicts. Asking the customer for information is allowed and PASSES. When unsure, PASS.
"""

def review_agent(ticket, draft_reply) -> dict:
    # deterministic safety checks (always run, never optional)
    issues = []
    if re.search(r"\[[A-Za-z0-9 _/]+\]", draft_reply):
        issues.append("contains an unfilled placeholder in square brackets")
    if "The Support Team" not in draft_reply:
        issues.append("missing the 'The Support Team' sign-off")
    leaked = scan(draft_reply)
    if leaked:
        issues.append("reply exposes PII: " + ", ".join(leaked))

    # autonomous policy + fact-check pass
    with open("policy.md") as f:
        policy = f.read()
    context = (f"Customer email: {ticket.customer_email}\n"
               f"Ticket: {ticket.subject} - {ticket.body}\n"
               f"Draft reply to check:\n{draft_reply}")
    transcript = ""
    for _ in range(MAX_STEPS):
        prompt = f"{REVIEW_SYSTEM}\n\nPolicy:\n{policy}\n\n{context}\n{transcript}\nYour JSON:"
        move = _parse(router.think(prompt, max_new_tokens=512))
        if move.get("action") == "finish":
            if move["result"].get("verdict") == "fail":
                issues.extend(move["result"].get("issues", []))
            break
        if move.get("action") == "crm_lookup":
            transcript += f"\ncrm_lookup -> {tools.crm_lookup(**move.get('args', {}))}"
        else:
            transcript += f"\nunknown action {move.get('action')!r}"

    return {"verdict": "fail" if issues else "pass", "issues": issues}

LEARN_SYSTEM = """You are the Learning agent for customer support.
A ticket has just been resolved. Decide whether its problem+solution is worth saving to the
knowledge base to help FUTURE tickets. Save ONLY if it is general and reusable (not a one-off,
no personal data, no customer-specific details). If worth saving, write a concise reusable article.

Reply with ONE JSON object, nothing else:
  {"thought":"...", "save": true, "title":"<short general title>", "content":"<concise problem + solution, no personal data>"}
  or
  {"thought":"...", "save": false}
"""

def learn_agent(ticket, draft_reply, resolved: bool) -> dict:
    if not resolved or not draft_reply:
        return {"learned": False, "reason": "ticket not resolved"}
    # autonomous quality gate: is this resolution worth keeping?
    prompt = (f"A support ticket was resolved. Decide if its resolution is general and reusable "
              f"enough to help future tickets (not a one-off, no sensitive personal data).\n"
              f"Ticket: {ticket.subject} - {ticket.body}\n"
              f"Resolution: {draft_reply}\n"
              f'Reply with ONE JSON object: {{"thought":"...","save":true}} or {{"thought":"...","save":false}}')
    move = _parse(router.think(prompt, max_new_tokens=256))
    if move.get("save"):
        content = f"Problem: {ticket.body} Resolution: {draft_reply}"
        index_resolved(ticket.subject, content)      # stays a resolved-ticket record, source preserved
        return {"learned": True}
    return {"learned": False, "reason": "not general enough"}