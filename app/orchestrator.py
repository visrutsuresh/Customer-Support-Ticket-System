"""Autonomous mode: a LangGraph orchestrator that dynamically routes a ticket
through the 5 ReAct agents. The deterministic pipeline still lives in graph.py."""

from langgraph.graph import END, START, StateGraph

from app import router
from app.agents import classify_agent, generate_agent, retrieve_agent, review_agent
from app.intake import normalize
from app.pii import scan
from app.state import State, grounded_confidence, confidence_threshold

# --- node wrappers: read shared state, run the agent, write results back ---


def node_intake(state: State) -> dict:
    try:
        ticket = normalize(state["raw_input"])
    except Exception as e:
        return {
            "error": str(e),
            "decision": {"action": "escalate", "reason": "malformed intake"},
            "audit": ["intake rejected: malformed"],
        }
    return {"ticket": ticket, "error": None, "audit": ["intake done"]}


def node_classify(state: State) -> dict:
    c = classify_agent(state["ticket"])
    c = {
        k: (v.lower() if isinstance(v, str) else v) for k, v in c.items()
    }  # match old normalization
    return {"classification": c, "audit": ["classify (agent) done"]}


def node_route(state: State) -> dict:
    # 2x2 routing, deterministic: agent's opinion + a hard PII/category floor for privacy.
    t, c = state["ticket"], state["classification"]
    pii = scan(f"{t.subject} {t.body}")
    category_hit = c.get("category") in {"refund", "billing"}
    is_sensitive = bool(pii) or category_hit or bool(c.get("sensitive"))
    lane = "private" if is_sensitive else "cloud"
    tier = c.get("difficulty", "simple")
    return {
        "sensitivity": {"is_sensitive": is_sensitive, "pii_types": pii},
        "routing": {
            "lane": lane,
            "tier": tier,
            "model": router.intended_model(lane, tier),
        },
        "audit": ["route done (2x2, folded)"],
    }


def node_retrieve(state: State) -> dict:
    return {
        "retrieval": retrieve_agent(state["ticket"]),
        "audit": ["retrieve (agent) done"],
    }


def node_generate(state: State) -> dict:
    r = state.get("routing") or {
        "lane": "cloud",
        "tier": "complex",
    }  # 2x2 wired in the next step
    draft = generate_agent(
        state["ticket"],
        state["retrieval"],
        r["lane"],
        r["tier"],
        state.get("messages", []),
    )
    return {"draft": draft, "audit": ["generate (agent) done"]}


def node_review(state: State) -> dict:
    reply = state.get("draft", {}).get("reply", "")
    if not reply:  # nothing to review (agent chose escalate)
        return {
            "compliance": {"verdict": "pass", "issues": []},
            "audit": ["review skipped (no draft)"],
        }
    return {
        "compliance": review_agent(state["ticket"], reply),
        "review_count": state.get("review_count", 0) + 1,
        "audit": ["review (agent) done"],
    }


def node_decide(state: State) -> dict:
    c = state["classification"]
    comp = state.get("compliance", {})
    draft = state.get("draft", {})
    kind = draft.get("kind")
    reply = (draft.get("reply") or "").strip()
    # a real answer that passed review, graded by how confident we are it is right
    answerable = kind == "answer" and bool(reply) and comp.get("verdict") != "fail"
    grounded = grounded_confidence(draft.get("confidence"), state.get("retrieval"))
    threshold = confidence_threshold(c.get("category"), c.get("priority"))
    if comp.get("verdict") == "fail":
        decision = {"action": "escalate", "reason": "failed compliance review"}
    elif c.get("priority") == "critical":
        decision = {"action": "escalate", "reason": "critical priority"}
    elif kind == "escalate":
        decision = {"action": "escalate", "reason": "agent suggested escalation"}
    elif answerable and grounded >= threshold:
        decision = {"action": "auto_send", "reason": "answerable from KB", "confidence": grounded}
    elif answerable:
        decision = {"action": "escalate", "reason": f"low confidence ({grounded} < {threshold})", "confidence": grounded}
    elif kind == "question":
        decision = {"action": "auto_send", "reason": "requesting more information"}
    else:
        decision = {"action": "escalate", "reason": "no usable draft"}
    return {"decision": decision, "audit": ["decide done"]}


def node_learn(state: State) -> dict:
    # KB write-back is deferred to the /resolve action, not fired on every auto_send
    return {"learned": False, "audit": ["learn: deferred to resolve"]}


# --- the orchestrator: pick the next agent given what is already done (dynamic, LLM-driven) ---

NODES = ["classify", "route", "retrieve", "generate", "review", "decide", "learn"]


def route_next(state: State) -> str:
    if state.get("error"):
        return "done"  # malformed intake already escalated

    # plain code walks the obvious sequence, no AI needed
    if state.get("classification") is None:
        return "classify"
    if state.get("routing") is None:
        return "route"
    if state.get("retrieval") is None:
        return "retrieve"
    if state.get("draft") is None:
        return "generate"
    if state.get("compliance") is None:
        return "review"

    # THE ONE REAL FORK: review is done, decision not made yet
    if state.get("decision") is None:
        failed = state["compliance"]["verdict"] == "fail"
        if failed and state.get("review_count", 0) < 2:
            # let the AI make the call: rewrite the reply, or escalate as-is?
            choice = (
                router.think(
                    f"A support reply failed compliance for: {state['compliance']['issues']}. "
                    f'Reply with ONE word: "generate" to rewrite it, or "decide" to escalate as-is.',
                    max_new_tokens=8,
                )
                .strip()
                .lower()
            )
            return "generate" if "generate" in choice else "decide"
        return "decide"

    if state.get("learned") is None:
        return "learn"
    return "done"


# --- build the autonomous graph ---

_b = StateGraph(State)
_b.add_node("intake", node_intake)
for _n, _fn in [
    ("classify", node_classify),
    ("route", node_route),
    ("retrieve", node_retrieve),
    ("generate", node_generate),
    ("review", node_review),
    ("decide", node_decide),
    ("learn", node_learn),
]:
    _b.add_node(_n, _fn)

_PATHMAP = {**{n: n for n in NODES}, "done": END}
_b.add_edge(START, "intake")
_b.add_conditional_edges("intake", route_next, _PATHMAP)
for _n in NODES:
    _b.add_conditional_edges(_n, route_next, _PATHMAP)

graph_auto = _b.compile()
