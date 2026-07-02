from app.graph import graph, print_result

tickets = [
    {"source": "email", "subject": "Cannot log in", "body": "my password reset link is broken"},
    {"source": "email", "subject": "Refund request", "body": "I want my money back for an unused subscription"},
    {"source": "chat",  "subject": "Still no refund!!", "body": "This is unacceptable, I have waited two weeks and I am furious"},
    {"source": "email", "subject": "Where is my order", "body": "tracking has not updated in three days"},
]

for i,raw in enumerate(tickets, start =1):
    print(f"\n\n########## TICKET {i} of {len(tickets)} ##########")
    final = graph.invoke({"raw_input": raw, "audit":[]})
    print_result(final) 