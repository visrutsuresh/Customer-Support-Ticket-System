from app.state import State
from langgraph.graph import StateGraph, START, END
from app.intake import normalize
import json
from app import router

#building the worker functions
def intake(state:State) -> dict:
    try:
        ticket=normalize(state["raw_input"])
    except Exception as e:
        return {"error": str(e), "audit" : ["intake rejected: malformed"]}
    print("intake ran")
    return {"ticket": ticket, "error": None, "audit":["intake done"]}

def after_intake(state: State) -> str:
    return "decide" if state.get("error") else "classify"

def classify(state:State) -> dict:
    t = state["ticket"]
    prompt=f"""Classify this support ticket.
    category: one of [billing,technical,account,general,shipping,refund,feature_request,complaint]
    priority: one of [low,medium,high,urgent]
    sentiment: one of [positive, neutral, negative]
    Respond with ONLY a JSON object with keys category, priority, sentiment. No other text.
    
    Subject: {t.subject}
    Body: {t.body}
    """
    raw = router.generate(prompt)
    data=json.loads(raw)
    #print("RAW CLASSIFY:",raw)
    print("classify ran")
    return {"classification": data, "audit":["classify done"]}

def route(state:State) -> dict:
    print("route ran")
    return {"audit":["route done"]}

def retrieve(state:State) -> dict:
    print("retrieve ran")
    return {"audit":["retrieve done"]}

def generate(state:State) -> dict:
    t= state["ticket"]
    c = state["classification"]
    prompt=f"""
    You are a customer support agent representing Ascendion Support. Write a helpful, polite reply to this problem.
    Classification: 
        Category: {c["category"]}
        Priority: {c["priority"]}
        Sentiment:{c["sentiment"]}
    Subject: {t.subject}
    Body: {t.body}

    Do not use placeholders such as [YOUR NAME]. Use a generic greeting such as "Hello" or "Hi there!" and sign off as 'The Support Team'. Sound Enthusiastic.
    """

    reply = router.generate(prompt)
    print("DRAFT:",reply)
    print("generate ran")
    return {"draft":{"reply":reply},"audit":["generate done"]}

def review(state:State) -> dict:
    print("review ran")
    return {"audit":["review done"]}

def decide(state:State) -> dict:
    err = state.get("error")
    if err:
        decision = {"action": "escalate", "reason": "malformed intake"}
    else:
        c = state["classification"]
        if c["priority"] in ["urgent", "high"]:
            decision = {"action": "escalate", "reason": "high priority"}
        elif c["category"] in ["refund", "billing"]:
            decision = {"action": "escalate", "reason": "sensitive category"}
        else:
            decision = {"action": "auto_send"}
    print("DECISION:", decision)
    print("decide ran")
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
builder.add_edge("review","decide")
builder.add_edge("decide",END)

#freeze the builder into a runnable graph
graph = builder.compile()

if __name__=="__main__":
    initial_state = {
        "raw_input": {"source": "email", "subject": "Cannot log in", "body": "reset link is broken"},
        "audit": [],
    }

    final_state=graph.invoke(initial_state)
    print("classification:", final_state["classification"])
    print("ticket:",final_state["ticket"])
    print("---")
    print("audit log:",final_state["audit"])
