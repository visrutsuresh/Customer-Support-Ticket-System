from app.state import State
from langgraph.graph import StateGraph, START, END
from app.intake import normalize
import json
import re
from app import router
from app.kb import search, index_resolved
import warnings
from app.pii import scan
from app.roster import assign
from app.audit import verify
warnings.filterwarnings("ignore")

def _parse_json(raw: str) -> dict:
    #small LLMs wrap JSON in markdown fences or add prose; grab the first {...} block and parse that
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in model output: {raw!r}")
    return json.loads(raw[start:end+1])

#building the worker functions
def intake(state:State) -> dict:
    try:
        ticket=normalize(state["raw_input"])
    except Exception as e:
        return {"error": str(e), "audit" : ["intake rejected: malformed"]}
    #print("intake ran")
    return {"ticket": ticket, "error": None, "audit":["intake done"]}

def after_intake(state: State) -> str:
    return "decide" if state.get("error") else "classify"

def classify(state:State) -> dict:
    t = state["ticket"]
    prompt=f"""Classify this support ticket. Choose the best label in each group using the definitions.

    category: one of [billing,technical,account,general,shipping,refund,feature_request,complaint]
      billing = charges, invoices, payment methods, pricing disputes
      technical = product not working, errors, bugs, broken links, cannot access or log in
      account = managing account details: profile, settings, changing email or password
      shipping = delivery, tracking, lost or delayed packages
      refund = wants money returned or to cancel for a refund
      feature_request = asking for something the product does not do yet
      complaint = venting dissatisfaction with no specific fixable request
      general = anything that fits none of the above

    priority: one of [Critical,High,Medium,Low]
      Critical = service down, a security or data breach, a legal threat, or a vulnerable customer at risk
      High = money is at stake, the customer is angry, or there is a hard deadline
      Medium = a normal problem that needs help but is not urgent
      Low = a simple how-to, self-serve, or informational question

    business_impact: one of [low,medium,high]
      high = risks losing the customer, a large sum of money, many users affected, or legal/reputational exposure
      medium = meaningfully affects one customer's experience but is recoverable
      low = minor inconvenience, easily resolved, little consequence if it waits

    sentiment: one of [positive,neutral,negative]
      positive = happy, grateful, complimentary
      neutral = matter-of-fact, no strong emotion
      negative = frustrated, angry, disappointed

    Respond with ONLY a JSON object with keys category, priority, business_impact, sentiment. No other text.
    
    Subject: {t.subject}
    Body: {t.body}
    """
    raw = router.think(prompt)
    data=_parse_json(raw)
    data = {k: (v.lower() if isinstance(v, str) else v) for k, v in data.items()}
    #print("RAW CLASSIFY:",raw)
    #print("classify ran")
    return {"classification": data, "audit":["classify done"]}

def auto_tags(c:dict) -> list[str]:
    tags=[]
    category = (c.get("category") or "").lower()
    priority = (c.get("priority") or "").lower()
    sentiment = (c.get("sentiment") or "").lower()

    if category:
        tags.append(category)
    if priority in {"critical", "high"}:
        tags.append(priority)
    if sentiment == "negative":
        tags.append("unhappy")
    return tags 

def score_difficulty(state: State) -> dict:
    t = state["ticket"]
    prompt = f"""Rate how hard this support ticket is to resolve well.

    simple = a routine, self-serve request a knowledge-base article can answer directly in one step (for example: how to reset a password, store hours, order tracking status).
    complex = needs judgement, multiple steps, investigation, or careful handling (for example: an angry weeks-old refund dispute, account recovery, a vague "nothing works" with no details, anything with money or a frustrated customer at stake).

    Respond with ONLY a JSON object with keys level and reason. level is exactly "simple" or "complex". reason is one short phrase. No other text.

    Subject: {t.subject}
    Body: {t.body}
    """
    raw = router.think(prompt)
    data = _parse_json(raw)
    data["level"] = data.get("level", "simple").lower()
    return {"difficulty": data, "audit": ["score_difficulty done"]}

def detect_sensitivity(state: State) -> dict:
    t = state["ticket"]
    c = state["classification"]

    #1 deterministic: regex PII + senstitive category ( free,always runs but matches against known expression patterns)
    pii = scan(f"{t.subject} {t.body}")
    category_hit = c["category"] in {"refund", "billing", "account"}
    
    # 2 model judgement: catches contextual sensitivity that the regex misses 
    sensitive_info = """
    - Financial account data: bank account or routing
    numbers, full card numbers, tax IDs, salary or income figures
    - Government or identity data: national ID / SSN, passport, driver's
    license, date of birth
    - Health or medical data: any medical condition, diagnosis,
    disability, treatment, or prescription
    - Authentication data: passwords, PINs, security-question answers,
    one-time / 2FA codes, API keys or tokens
    - Legal matters: lawsuits, legal threats, law-enforcement or
    regulatory complaints
    - Protected personal traits: home address, race or ethnicity,
    religion, sexual orientation, immigration status, political views"""

    prompt = f"""Decide if this support ticket contains or disucsses sensitive information.
    Treat any of the following as sensitive:
    {sensitive_info}

    Respond with ONLY a JSON object with keys sensitive, types, reason.
    sensitive is true or false. types is a list of the atching categories above (empty if none).
    reason is one short phrase. No other text.

    Subject: {t.subject}
    Body: {t.body}
    """

    try:
        llm = _parse_json(router.think(prompt))
        llm_sensitive = bool(llm.get("sensitive"))
    except Exception:
        llm, llm_sensitive = {}, False #parse failed; regex + category still guard
    
    is_sensitive = bool(pii) or category_hit or llm_sensitive

    reasons =[]
    if pii:
        reasons.append("PII found:" + ", ".join(pii))
    if category_hit:
        reasons.append(f"sensitive category: {c['category']}")
    if llm_sensitive:
        types = llm.get("types") or []
        if isinstance(types, str):
            types=[types]
        reasons.append(f"model flagged: {', '.join(types) or 'unspecified'}")


    sensitivity = {
        "is_sensitive": is_sensitive,
        "pii_types": pii,
        "reason": "; ".join(reasons) or "none"
        }
    return {"sensitivity": sensitivity,"audit": ["detect_sensitivity done"]}

def route(state:State) -> dict:
    s = state["sensitivity"]
    lane = "private" if s["is_sensitive"] else "cloud"
    level = state["difficulty"]["level"]
    model = router.intended_model(lane,level)
    routing = {"lane": lane, "tier": level, "model": model}
    #print("route ran")
    return {"routing":routing, "audit":["route done"]}

def retrieve(state:State) -> dict:
    t = state["ticket"]
    hits = search(f"{t.subject} {t.body}")
    #print("RETRIEVED:",[h["title"] for h in hits])
    #print("retrieve ran")
    return {"retrieval":hits, "audit":["retrieve done"]}

def generate(state:State) -> dict:
    t= state["ticket"]
    c = state["classification"]
    hits = state["retrieval"]
    kb_text = "\n\n".join(f"[{h['title']}]\n{h['content']}" for h in hits)

    history = state.get("messages", [])
    convo = "\n".join(
        f"{'Customer' if m['role'] == 'customer' else 'Support'}:{m['body']}" for m in history
    )

    greeting = f"Hi {t.customer_name.split()[0]}," if t.customer_name else "Hi there!"

    prompt=f"""
    You are a customer support agent representing a company's support team. Write a helpful, polite reply to this problem.
    Classification: 
        Category: {c["category"]}
        Priority: {c["priority"]}
        Sentiment:{c["sentiment"]}
    Subject: {t.subject}
    Body: {t.body}

    Conversation so far (oldest first):
    {convo}

    The last line above is the customer's latest message.
    Reply to that, using the earlier turns for context. Do not repeat a solution you already gave, and do not contradict an earlier reply.

    Use ONLY the knowledge base articles below to answer. If they do not cover the question, say you will escalate to a specialist rather than inventing details. Mention which article you relied on by its title.

    If the ticket is missing a specific detail you would need to actually resolve it (for example a refund with no order number, or a vague problem with no specifics), do NOT invent a full solution. Instead reply with a short, polite message asking the customer for the exact missing detail, and nothing else.

    Knowledge base: {kb_text}

    Begin your response with a single control line: "KIND: answer" if you are answering the question, or "KIND: question" if you are instead asking the customer for missing information. Put the actual reply on the lines after that control line.

    Do not use placeholders such as [YOUR NAME]. Open the reply with exactly this greeting : {greeting} and sign off as 'The Support Team'. Sound helpful and warm.
    """

    r = state["routing"]
    reply = router.generate_reply(prompt, r['lane'], r['tier'])
    #print("DRAFT:",reply)
    #print("generate ran")
    lines = reply.strip().split("\n",1)
    if lines[0].strip().lower().startswith("kind:"):
        kind = lines[0].split(":",1)[1].strip().lower()
        reply=lines[1].strip() if len(lines) > 1 else ""
    else:
        kind="answer"
        

    return {"draft":{"reply":reply,"kind":kind},"audit":["generate done"]}

def review(state:State) -> dict:
    draft = state["draft"]["reply"]
    
    issues = []
    
    # deterministic checks (free, always correct)
    if re.search(r"\[[A-Za-z0-9 _/]+\]", draft):
        issues.append("contains an unfilled placeholder in square brackets")
    if "The Support Team" not in draft:
        issues.append("missing the 'The Support Team' sign-off")
    #data-privacy :an outbound reply must not carry PII (echoed sensitive data, or another customer's data leaked in)
    leaked = scan(draft)
    if leaked:
        issues.append("reply exposes PII: " + ", ".join(leaked))

    # full-policy judgement on the check model (14B in local/full, 3B in dev)
    policy = open("policy.md").read()
    prompt = f"""You are a compliance reviewer for a customer support reply.
    Check the reply against the numbered policy rules below. FAIL only if the reply text clearly
    breaks a rule. Asking the customer for their email, order number, or more information is
    allowed and PASSES. When unsure, PASS.

    Policy:
    {policy}

    Reply to check:
    {draft}

    Respond in EXACTLY this format and nothing else:
    PASS
    or
    FAIL: <one short reason>
    """
    raw = router.think(prompt).strip()
    if raw.upper().startswith("FAIL"):
        reason = raw.split(":", 1)[1].strip() if ":" in raw else "policy violation"
        issues.append(reason)

    verdict = "fail" if issues else "pass"
    count = state.get("review_count", 0) + 1
    return {"compliance": {"verdict": verdict, "issues": issues}, "review_count": count, "audit": ["review done"]}

def after_review(state: State) -> str:
    #on a clear compliance fail, loop back to generate ONCE (review_count caps it), else move on
    failed = state["compliance"]["verdict"] == "fail"
    return "generate" if failed and state["review_count"] < 2 else "decide"

def decide(state:State) -> dict:
    err = state.get("error")
    if err:
        decision = {"action": "escalate", "reason": "malformed intake"}
    else:
        c = state["classification"]
        comp = state.get("compliance", {})
        if comp.get("verdict") == "fail":
            decision = {"action": "escalate", "reason": "failed compliance review"}
        elif c["priority"] in ["critical", "high"]:
            decision = {"action": "escalate", "reason": "high priority"}
        elif c.get("business_impact") == "high":
            decision={"action":"escalate","reason":"high business impact"}
        elif c["category"] in ["refund", "billing"]:
            decision = {"action": "escalate", "reason": "sensitive category"}
        elif state["draft"].get("kind") == "question":
            decision = {"action": "auto_send", "reason":"requesting more information"}
        else:
            decision = {"action": "auto_send"}
    #print("DECISION:", decision)
    #print("decide ran")
    if not err and decision["action"] == "escalate":
        decision["assignee"] = assign(c["priority"], state["ticket"].ticket_id)
    return {"decision":decision,"audit":["decide done"]}

def learn(state: State) -> dict:
    # KB write-back is deferred to the /resolve action; one auto_send is not a resolved conversation
    return {"learned": False, "audit": ["learn: deferred to resolve"]}

#building the graph
builder = StateGraph(State)

#register each worker under a name
builder.add_node("intake",intake)
builder.add_node("classify",classify)
builder.add_node("score_difficulty", score_difficulty)
builder.add_node("detect_sensitivity",detect_sensitivity)
builder.add_node("route",route)
builder.add_node("retrieve",retrieve)
builder.add_node("generate",generate)
builder.add_node("review",review)
builder.add_node("decide",decide)
builder.add_node("learn",learn)

#drawing the arrws: Start -> intake ->.... -> decide -> END
builder.add_edge(START,"intake")
builder.add_conditional_edges(
    "intake",
    after_intake,
    {"classify": "classify","decide":"decide" },
)
builder.add_edge("classify","detect_sensitivity")
builder.add_edge("detect_sensitivity","score_difficulty")
builder.add_edge("score_difficulty","route")
builder.add_edge("route","retrieve")
builder.add_edge("retrieve","generate")
builder.add_edge("generate","review")
builder.add_conditional_edges(
    "review",
    after_review,
    {"generate":"generate","decide":"decide"},
)
builder.add_edge("decide","learn")
builder.add_edge("learn",END)

#freeze the builder into a runnable graph
graph = builder.compile()

def print_result(final: dict) -> None:
    print("\n" + "="*60)
    print("TICKET")
    print("="*60)
    print(f"  Subject : {final['ticket'].subject}")
    print(f"  Body    : {final['ticket'].body}")

    c = final["classification"]
    print("\nCLASSIFICATION")
    print(f"  Category  : {c['category'].title()}")
    print(f"  Priority  : {c['priority'].title()}")
    print(f"  Business impact : {c['business_impact'].title()}")
    print(f"  Sentiment : {c['sentiment'].title()}")

    s = final["sensitivity"]
    print("\nSENSITIVITY")
    print(f" Sensitive: {s['is_sensitive']}")
    print(f" PII types: {','.join(s['pii_types']) or 'none'}")
    print(f" Reason   : {s['reason']}")

    diff = final["difficulty"]
    print("\nDIFFICULTY")
    print(f" Level : {diff['level'].title()}")
    print(f" Reason: {diff.get('reason', '')}")

    r = final["routing"]
    print("\nROUTING")
    print(f"  Lane  : {r['lane']}")
    print(f"  Model : {r['model']}")

    print("\nRETRIEVED ARTICLES")
    for h in final["retrieval"]:
        print(f"  - {h['source']} {h['title']} ({h['score']}% relevant)")

    print("\nDRAFT REPLY")
    print("-"*60)
    print(final["draft"]["reply"].strip())
    print("="*60)

    comp = final["compliance"]
    print("\nCOMPLIANCE")
    print(f"  Verdict : {comp['verdict']}")
    if comp.get("issues"):
        for issue in comp["issues"]:
            print(f"  Issue   : {issue}")

    d = final["decision"]
    print("\nDECISION")
    print(f"  Action : {d['action']}")
    if d.get("reason"):
        print(f"  Reason : {d['reason']}")
    if d.get("assignee"):
        a = d["assignee"]
        print(f" Assigned : {a['name']} ({a['tier']} tier)")

    print("\nLEARNING")
    print(f"  Filed back into KB : {final.get('learned', False)}")

    print("\nAUDIT TRAIL")
    log = final.get("audit", [])
    for e in log:
        print(f" {e['hash'][:8]} {e['step']}")
    broken = verify(log)
    print(f" Chain:{'intact' if broken < 0 else f'BROKEN at step {broken}'}")


if __name__=="__main__":
    initial_state = {
        "raw_input": {"source": "email", "subject": "Cannot log in", "body": "reset link is broken"},
        "audit": [],
    }

    final_state=graph.invoke(initial_state)

    print_result(final_state)

    #print("classification:", final_state["classification"])
    #print("ticket:",final_state["ticket"])
    #print("---")
    print("audit log:",final_state["audit"])
