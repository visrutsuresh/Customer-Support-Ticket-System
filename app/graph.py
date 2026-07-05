from app.state import State
from langgraph.graph import StateGraph, START, END
from app.intake import normalize
import json
import re
import os
from app import router
from app.kb import search
import warnings
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
    raw = router.generate(prompt)
    data=_parse_json(raw)
    data = {k: (v.lower() if isinstance(v, str) else v) for k, v in data.items()}
    #print("RAW CLASSIFY:",raw)
    #print("classify ran")
    return {"classification": data, "audit":["classify done"]}

def route(state:State) -> dict:
    c = state["classification"]
    sensitive = {"refund", "billing", "account"}
    lane = "private" if c["category"] in sensitive else "cloud"
    routing = {"lane": lane, "model": "qwen2.5-3b"}
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

    greeting = f"Hi {t.customer_name.split()[0]}," if t.customer_name else "Hi there!"

    prompt=f"""
    You are a customer support agent representing a company's support team. Write a helpful, polite reply to this problem.
    Classification: 
        Category: {c["category"]}
        Priority: {c["priority"]}
        Sentiment:{c["sentiment"]}
    Subject: {t.subject}
    Body: {t.body}

    Use ONLY the knowledge base articles below to answer. If they do not cover the question, say you will escalate to a specialist rather than inventing details. Mention which article you relied on by its title.

    If the ticket is missing a specific detail you would need to actually resolve it (for example a refund with no order number, or a vague problem with no specifics), do NOT invent a full solution. Instead reply with a short, polite message asking the customer for the exact missing detail, and nothing else.

    Knowledge base: {kb_text}

    Begin your response with a single control line: "KIND: answer" if you are answering the question, or "KIND: question" if you are instead asking the customer for missing information. Put the actual reply on the lines after that control line.

    Do not use placeholders such as [YOUR NAME]. Open the reply with exactly this greeting : {greeting} and sign off as 'The Support Team'. Sound helpful and warm.
    """

    reply = router.generate(prompt)
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

    if os.getenv("REVIEW_LLM","on").lower() == "on":
        # full-policy judgement on the stronger 14B review lane
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
        raw = router.generate_review(prompt).strip()
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
    return {"decision":decision,"audit":["decide done"]}

#building the graph
builder = StateGraph(State)

#register each worker under a name
builder.add_node("intake",intake)
builder.add_node("classify",classify)
builder.add_node("route",route)
builder.add_node("retrieve",retrieve)
builder.add_node("generate",generate)
builder.add_node("review",review)
builder.add_node("decide",decide)

#drawing the arrws: Start -> intake ->.... -> decide -> END
builder.add_edge(START,"intake")
builder.add_conditional_edges(
    "intake",
    after_intake,
    {"classify": "classify","decide":"decide" },
)
builder.add_edge("classify","route")
builder.add_edge("route","retrieve")
builder.add_edge("retrieve","generate")
builder.add_edge("generate","review")
builder.add_conditional_edges(
    "review",
    after_review,
    {"generate":"generate","decide":"decide"},
)
builder.add_edge("decide",END)

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

    r = final["routing"]
    print("\nROUTING")
    print(f"  Lane  : {r['lane']}")
    print(f"  Model : {r['model']}")

    print("\nRETRIEVED ARTICLES")
    for h in final["retrieval"]:
        print(f"  - {h['title']} ({h['score']}% relevant)")

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
