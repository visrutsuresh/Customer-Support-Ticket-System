import weaviate
from weaviate.classes.config import Configure, Property, DataType
from app.embed import embed

client = weaviate.connect_to_local()

if client.collections.exists("KBArticle"):
    client.collections.delete("KBArticle")

client.collections.create(
    "KBArticle", 
    vectorizer_config=Configure.Vectorizer.none(),
    properties = [
        Property(name="title",data_type=DataType.TEXT), 
        Property(name="content", data_type = DataType.TEXT)
        ]
    )

kb = client.collections.get("KBArticle")

articles = [
    {
        "title": "Reset your password",
        "content": "If you cannot log in or your password reset link is broken or expired, go to the login page and click 'Forgot password'. Enter your account email and we will send a fresh reset link, valid for 30 minutes. If the link still fails, clear your browser cache, try another browser, and check your spam folder.",
    },
    {
        "title": "Refund policy",
        "content": "Refunds are available within 30 days of purchase for unused items and unused subscription time. Approved refunds return to the original payment method within 5 to 10 business days. To request one, reply with your order number and the reason for the return.",
    },
    {
        "title": "Track your shipment",
        "content": "Once your order ships you receive a tracking number by email. Track delivery status on the carrier's site using that number. Most domestic orders arrive within 3 to 7 business days. If tracking has not updated in 48 hours, or the package shows delivered but is missing, contact us to open an investigation.",
    },
    {
        "title": "Update your account email",
        "content": "To change your account email, sign in, open Account Settings, and edit the email field. We send a confirmation link to the new address and the change takes effect once you click it. If you have lost access to the old email and cannot sign in, contact support to verify your identity manually.",
    },
    {
        "title": "Contact support",
        "content": "Support is available Monday to Friday, 9am to 6pm. Reach us through in-app chat, by replying to any ticket email, or via the help center contact form. For urgent account or billing issues, mark your message high priority so it routes to a specialist.",
    },
]

for a in articles:
    kb.data.insert(properties=a, vector=embed(a["content"]))


print("seeded", len(articles))

client.close()