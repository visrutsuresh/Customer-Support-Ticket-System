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
    