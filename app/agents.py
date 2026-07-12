import json 
from app import router, tools

MAX_STEPS = 5

def _parse(raw:str) -> dict:
    #same trick as graph.py: grab the first {...} block the model emitted
    s, e = raw.find("{"), raw.rfind("}")
    return json.loads(raw[s:e+1])

CLASSIFY_SYSTEM = """
You are the Classification and Prioritization agent for customer support.
Decide the ticket's category, priority, business_impact, and sentiment.
You MAY look the customer up first to inform priority (a premium customer, or money at stake, raises it).

Tool available:
  crm_lookup(email) -> the customer's record (tier, order history) or null

Reply every turn with ONE JSON object, nothing else.
  To use the tool:  {"thought": "...", "action": "crm_lookup", "args": {"email": "<email>"}}
  To finish:        {"thought": "...", "action": "finish", "result": {"category": "...", "priority": "...", "business_impact": "...", "sentiment": "..."}}

Definitions:
  category:        [billing, technical, account, general, shipping, refund, feature_request, complaint]
  priority:        [Critical, High, Medium, Low]
  business_impact: [low, medium, high]
  sentiment:       [positive, neutral, negative]
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
    return {"category": "general", "priority": "Medium", "business_impact" : "medium", "sentiment" : "neutral"}

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