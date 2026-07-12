"""Autonomous mode: a LangGraph orchestrator that dynamically routes a ticket
through the 5 ReAct agents. The deterministic pipeline still lives in graph.py."""
from app.state import State
from langgraph.graph import StateGraph, START, END
from app.intake import normalize
from app import router
from app.agents import (classify_agent, retrieve_agent, generate_agent,
                        review_agent, learn_agent)

# --- node wrappers: read shared state, run the agent, write results back ---

def node_intake(state: State) -> dict:
    try:
        ticket = normalize(state["raw_input"])
    except Exception as e:
        return {"error": str(e),
                "decision": {"action": "escalate", "reason": "malformed intake"},
                "audit": ["intake rejected: malformed"]}
    return {"ticket": ticket, "error": None, "audit": ["intake done"]}

def node_classify(state: State) -> dict:
    c = classify_agent(state["ticket"])
    c = {k: (v.lower() if isinstance(v, str) else v) for k, v in c.items()}   # match old normalization
    return {"classification": c, "audit": ["classify (agent) done"]}

def node_retrieve(state: State) -> dict:
    return {"retrieval": retrieve_agent(state["ticket"]), "audit": ["retrieve (agent) done"]}

def node_generate(state: State) -> dict:
    r = state.get("routing") or {"lane": "cloud", "tier": "complex"}   # 2x2 wired in the next step
    draft = generate_agent(state["ticket"], state["retrieval"], r["lane"], r["tier"])
    return {"draft": draft, "audit": ["generate (agent) done"]}

def node_review(state: State) -> dict:
    reply = state.get("draft", {}).get("reply", "")
    if not reply:                                   # nothing to review (agent chose escalate)
        return {"compliance": {"verdict": "pass", "issues": []}, "audit": ["review skipped (no draft)"]}
    return {"compliance": review_agent(state["ticket"], reply),
            "review_count": state.get("review_count", 0) + 1, "audit": ["review (agent) done"]}

def node_decide(state: State) -> dict:
    c = state["classification"]
    comp = state.get("compliance", {})
    kind = state.get("draft", {}).get("kind")
    if comp.get("verdict") == "fail":
        decision = {"action": "escalate", "reason": "failed compliance review"}
    elif c.get("priority") in ["critical", "high"]:
        decision = {"action": "escalate", "reason": "high priority"}
    elif c.get("business_impact") == "high":
        decision = {"action": "escalate", "reason": "high business impact"}
    elif c.get("category") in ["refund", "billing"]:
        decision = {"action": "escalate", "reason": "sensitive category"}
    elif kind == "escalate":
        decision = {"action": "escalate", "reason": "agent suggested escalation"}
    elif kind == "question":
        decision = {"action": "auto_send", "reason": "requesting more information"}
    else:
        decision = {"action": "auto_send"}
    return {"decision": decision, "audit": ["decide done"]}

def node_learn(state: State) -> dict:
    d = state.get("decision", {})
    kind = state.get("draft", {}).get("kind")
    resolved = d.get("action") == "auto_send" and kind == "answer"
    out = learn_agent(state["ticket"], state.get("draft", {}).get("reply", ""), resolved)
    return {"learned": out.get("learned", False), "audit": ["learn done"]}

# --- the orchestrator: pick the next agent given what is already done (dynamic, LLM-driven) ---

NODES = ["classify", "retrieve", "generate", "review", "decide", "learn"]

def route_next(state: State) -> str:
    if state.get("error"):
        return "done"                                   # malformed intake already escalated

    # plain code walks the obvious sequence, no AI needed
    if state.get("classification") is None: return "classify"
    if state.get("retrieval")      is None: return "retrieve"
    if state.get("draft")          is None: return "generate"
    if state.get("compliance")     is None: return "review"

    # THE ONE REAL FORK: review is done, decision not made yet
    if state.get("decision") is None:
        failed = state["compliance"]["verdict"] == "fail"
        if failed and state.get("review_count", 0) < 2:
            # let the AI make the call: rewrite the reply, or escalate as-is?
            choice = router.think(
                f'A support reply failed compliance for: {state["compliance"]["issues"]}. '
                f'Reply with ONE word: "generate" to rewrite it, or "decide" to escalate as-is.',
                max_new_tokens=8).strip().lower()
            return "generate" if "generate" in choice else "decide"
        return "decide"

    if state.get("learned") is None: return "learn"
    return "done"

# --- build the autonomous graph ---

_b = StateGraph(State)
_b.add_node("intake", node_intake)
for _n, _fn in [("classify", node_classify), ("retrieve", node_retrieve),
                ("generate", node_generate), ("review", node_review),
                ("decide", node_decide), ("learn", node_learn)]:
    _b.add_node(_n, _fn)

_PATHMAP = {**{n: n for n in NODES}, "done": END}
_b.add_edge(START, "intake")
_b.add_conditional_edges("intake", route_next, _PATHMAP)
for _n in NODES:
    _b.add_conditional_edges(_n, route_next, _PATHMAP)

graph_auto = _b.compile()
