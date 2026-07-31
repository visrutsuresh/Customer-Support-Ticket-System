from weaviate.classes.config import Configure, DataType, Property

import seed_data
from app.embed import embed
from app.kb import connect

client = connect()

if client.collections.exists("Knowledge"):
    client.collections.delete("Knowledge")

client.collections.create(
    "Knowledge",
    vectorizer_config=Configure.Vectorizer.none(),
    properties=[
        Property(name="title", data_type=DataType.TEXT),
        Property(name="content", data_type=DataType.TEXT),
        Property(name="source", data_type=DataType.TEXT),  # article or ticket
    ],
)

kb = client.collections.get("Knowledge")

articles = [
    {
        "title": "Reset your password",
        "content": "If you cannot log in or your password reset link is broken or expired, go to the login page and click 'Forgot password'. Enter your account email and Nimbus will send a fresh reset link, valid for 30 minutes. If the link still fails, clear your browser cache, try another browser, and check your spam folder.",
    },
    {
        "title": "Refund policy",
        "content": "Nimbus offers refunds within 30 days of purchase for unused items and unused subscription time. Approved refunds return to the original payment method within 5 to 10 business days. To request one, reply with your order number (or the charge in question) and the reason. Purchases older than 30 days fall outside the refund window and are handled case by case.",
    },
    {
        "title": "Track your order",
        "content": "Track your order with the link in your shipping confirmation email, or under Account > Orders. Carriers (UPS, FedEx, DHL, USPS) refresh tracking every 24 to 48 hours, so short gaps are normal. If tracking has not updated in 48 hours, or the package shows delivered but you have not received it, contact us and we will open an investigation with the carrier.",
    },
    {
        "title": "Plans and billing",
        "content": "Nimbus has three plans: Free (0 dollars), Pro (19.99 dollars per month), and Max (99.99 dollars per month). When you upgrade mid-cycle we charge a prorated amount for the rest of the current billing period, so a partial charge smaller than the full plan price right after an upgrade is normal. You can see every charge under Account > Billing.",
    },
    {
        "title": "Update your account email",
        "content": "To change your account email, sign in, open Account Settings, and edit the email field. Nimbus sends a confirmation link to the new address and the change takes effect once you click it. If you have lost access to the old email and cannot sign in, contact support to verify your identity manually.",
    },
    {
        "title": "App keeps crashing or freezing",
        "content": "If the Nimbus app crashes on launch or freezes, first update to the latest version from your app store, then restart your device. If it still crashes, reinstall the app and clear its cache. Persistent crashes after that are usually a known issue we are tracking; send us your device model and OS version and we will investigate.",
    },
    {
        "title": "Contact support",
        "content": "Nimbus support is available Monday to Friday, 9am to 6pm. Reach us through in-app chat, by replying to any ticket email, or via the help center contact form. For urgent account or billing issues, mark your message high priority so it routes to a specialist.",
    },
    {
        "title": "Damaged or missing items",
        "content": "If your Nimbus order arrives damaged, or an item is missing from the box, contact us within 30 days with your order number and a photo if you can. We will arrange a free replacement or a refund. Do not discard damaged packaging until the claim is resolved, as the carrier may ask to inspect it.",
    },
    {
        "title": "Payment methods and failed payments",
        "content": "Nimbus accepts major credit and debit cards. If a payment fails, check the card has not expired and has funds, then retry under Account > Billing. A failed subscription payment retries automatically for 3 days before the plan is paused; your data is kept and restored once payment succeeds.",
    },
    {
        "title": "Cancel your subscription",
        "content": "You can cancel a Nimbus subscription at any time under Account > Billing, or by asking support. Cancellation stops future charges and takes effect at the end of the current billing period, so you keep access until then. Unused time may be refundable within the 30-day window; see the refund policy.",
    },
    {
        "title": "Account security and sign-in",
        "content": "If you are repeatedly locked out or suspect someone else accessed your account, reset your password immediately and enable two-step verification under Account > Security. Nimbus will never ask for your full password or a one-time code by email or chat; treat any such request as phishing.",
    },
    {
        "title": "Delivery times",
        "content": "Nimbus ships within 1 to 2 business days of an order. Standard delivery then takes 3 to 7 business days depending on your location; express options are shown at checkout. Orders still showing 'processing' after 2 business days have not shipped yet and carry no tracking number until they do.",
    },
]

for a in articles:
    a["source"] = "article"
    kb.data.insert(properties=a, vector=embed(a["title"] + ". " + a["content"]))

# Nimbus resolved tickets: the SAME past tickets seeded into Postgres, deduped so we do not embed
# 30 copies of the pooled templates. The resolved-ticket corpus is now Nimbus, not Bitext.
seen = set()
n_tickets = 0
for c in seed_data.CUSTOMERS:
    for pt in c.get("past_tickets", []):
        key = (pt["subject"], pt["resolution"])
        if key in seen:
            continue
        seen.add(key)
        content = f"Problem: {pt['body']} Resolution: {pt['resolution']}"
        kb.data.insert(properties={"title": pt["subject"], "content": content, "source": "ticket"}, vector=embed(pt["subject"] + ". " + content))
        n_tickets += 1

print(f"seeded {len(articles)} Nimbus articles and {n_tickets} Nimbus resolved tickets")

client.close()
