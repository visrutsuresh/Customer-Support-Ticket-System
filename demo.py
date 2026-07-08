from app.graph import graph, print_result
from app.adapters import ZendeskAdapter

tickets = [
    {"source": "email", "name": "Alice Tan",   "email": "alice@example.com", "subject": "Cannot log in", "body": "my password reset link is broken"},
    {"source": "email", "name": "Bob Rivera",  "email": "bob@example.com",   "subject": "Refund request", "body": "I want my money back for an unused subscription"},
    {"source": "chat",  "name": "Chen Wei",    "email": "chen@example.com",  "subject": "Still no refund!!", "body": "This is unacceptable, I have waited two weeks and I am furious"},
    {"source": "email", "name": "Dana Okoro",  "email": "dana@example.com",  "subject": "Where is my order", "body": "tracking has not updated in three days"},
    {"source": "chat", "name": "Evan Lee", "email": "evan@example.com", "subject": "It stopped working", "body": "nothing works please help"},
    {"source": "form", "name": "Fiona Adams", "email": "[REDACTED_EMAIL_ADDRESS_8]","subject": "How do I reset my password", "body": "I forgot my password and want to reset it. What are the steps?"},
    {"source": "email", "name": "Grace Hall", "email":"grace@example.com", "subject": "App keeps crashing on launch", "body":"the app crashes every time I open it, please call me back on 555-0142-8890"},
]

for i,raw in enumerate(tickets, start =1):
    print(f"\n\n########## TICKET {i} of {len(tickets)} ##########")
    final = graph.invoke({"raw_input": raw, "audit":[]})
    print_result(final) 

# req 29: a Zendesk-shaped payload enters through the adapter seam, then runs
# through the exact same pipeline as every other ticket
zendesk_payload = {"ticket": {
    "id": 55021,
    "subject": "Double charged this month",
    "description": "I was billed twice for my subscription, please refund one charge.",
    "via": {"channel": "email"},
    "requester": {"id": 4471, "name": "Hana Sato", "email": "hana@example.com"},
}}
print("\n\n########## TICKET (via Zendesk adapter) ##########")
final = graph.invoke({"raw_input": ZendeskAdapter().to_canonical(zendesk_payload), "audit": []})
print_result(final)