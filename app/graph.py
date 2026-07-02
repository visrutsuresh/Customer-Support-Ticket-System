from app.state import State,Ticket
from datetime import datetime
from langgraph.graph import StateGraph, START, END
from app.intake import normalize

#building the worker functions
def intake(state:State) -> dict:
    ticket=normalize(state["raw_input"])
    print("intake ran")
    return {"ticket": ticket, "audit":["intake done"]}

def classify(state:State) -> dict:
    print("classify ran")
    return {"audit":["classify done"]}

def route(state:State) -> dict:
    print("route ran")
    return {"audit":["route done"]}

def retrieve(state:State) -> dict:
    print("retrieve ran")
    return {"audit":["retrieve done"]}

def generate(state:State) -> dict:
    print("generate ran")
    return {"audit":["generate done"]}

def review(state:State) -> dict:
    print("review ran")
    return {"audit":["review done"]}

def decide(state:State) -> dict:
    print("decide ran")
    return {"audit":["decide done"]}

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
builder.add_edge("intake","classify")
builder.add_edge("classify","route")
builder.add_edge("route","retrieve")
builder.add_edge("retrieve","generate")
builder.add_edge("generate","review")
builder.add_edge("review","decide")
builder.add_edge("decide",END)

#freeze the builder into a runnable graph
graph = builder.compile()

if __name__=="__main__":
    ticket = Ticket(
        ticket_id="T-001",
        source="email",
        subject="Cannot log in",
        body="I forgot my password and the reset link is broken.",
        created_at=datetime.now(),
    )
    initial_state = {
        "raw_input": {"source": "email", "subject": "Cannot log in", "body": "reset link is broken"},
        "audit": [],
    }

    final_state=graph.invoke(initial_state)
    print("ticket:",final_state["ticket"])
    print("---")
    print("audit log:",final_state["audit"])
