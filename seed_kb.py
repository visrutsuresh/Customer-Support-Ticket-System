import weaviate
from weaviate.classes.config import Configure, Property, DataType
from app.embed import embed

client = weaviate.connect_to_local()

if client.collections.exists("Knowledge"):
    client.collections.delete("Knowledge")

client.collections.create(
    "Knowledge", 
    vectorizer_config=Configure.Vectorizer.none(),
    properties = [
        Property(name="title",data_type=DataType.TEXT), 
        Property(name="content", data_type = DataType.TEXT),
        Property(name="source", data_type=DataType.TEXT), #article or text
        ]
    )

kb = client.collections.get("Knowledge")

articles = [
    {"title": "Reset your password", "content": "If you cannot log in or your password reset link is broken or expired, go to the login page and click 'Forgot password'. Enter your account email and we will send a fresh reset link, valid for 30 minutes. If the link still fails, clear your browser cache, try another browser, and check your spam folder."},
    {"title": "Refund policy", "content": "Refunds are available within 30 days of purchase for unused items and unused subscription time. Approved refunds return to the original payment method within 5 to 10 business days. To request one, reply with your order number and the reason for the returto 7 business days. If tracking has not updated in 48 hours, or the package shows delivered but is missing, contact us to open an investigation."},
    {"title": "Update your account email", "content": "To change your account email, sign in, open Account Settings, and edit the email field. We send a confirmation link to the new address and the change takes effect once you click it. If you have lost access to the old email and cannot sign in, contact support to verify your identity manually."},
    {"title": "Contact support", "content": "Support is available Monday to Friday, 9am to 6pm. Reach us through in-app chat, by replying to any ticket email, or via the help center contact form. For urgent account or billing issues, mark your message high priority so it routes to a specialist."},
]

resolved_tickets = [
    {"title": "Password reset link kept expiring", "content": "Customer's reset link expired before use. We sent a fresh 30-minute link and asked them to clear cache first. Resolved on first reply, no escalation."},
    {"title": "Charged twice for one order", "content": "Customer saw a duplicate charge. We confirmed only one order shipped and refunded the duplicate to the original card. Refund landed in 6 business days."},
    {"title": "Wanted refund on unused annual subscription", "content": "Customer requested a refund on an unused annual plan within 30 days. Approved per policy, prorated the unused time, refunded to original payment method."},
    {"title": "Could not change account email", "content": "Customer lost access to their old email and could not receive the confirmation link. We verified identity manually and updated the account email for them."},
]

for a in articles:
    a["source"] = "article"
    kb.data.insert(properties=a, vector=embed(a["title"] + ". " + a["content"]))

for t in resolved_tickets:
    t["source"] = "ticket"
    kb.data.insert(properties=t, vector=embed(t["title"] + ". " + t["content"]))

print("seeded", len(articles), "articles and", len(resolved_tickets), "resolved tickets")


client.close()