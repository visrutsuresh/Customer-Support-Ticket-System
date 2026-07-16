# Synthetic Nimbus support roster: each agent has an expertise (ticket category) and an experience tier.
# assign() routes a ticket to someone whose expertise matches its category, preferring a senior for hot tickets.

ROSTER = [
    {"name": "Priya Nair", "email": "priya.nair@nimbus.example.com", "expertise": "refund", "tier": "senior"},
    {"name": "Marcus Reed", "email": "marcus.reed@nimbus.example.com", "expertise": "technical", "tier": "senior"},
    {"name": "Sofia Alvarez", "email": "sofia.alvarez@nimbus.example.com", "expertise": "billing", "tier": "senior"},
    {"name": "Diego Santos", "email": "diego.santos@nimbus.example.com", "expertise": "billing", "tier": "mid"},
    {"name": "Lena Fischer", "email": "lena.fischer@nimbus.example.com", "expertise": "technical", "tier": "mid"},
    {"name": "Tom Becker", "email": "tom.becker@nimbus.example.com", "expertise": "shipping", "tier": "mid"},
    {"name": "Aisha Khan", "email": "aisha.khan@nimbus.example.com", "expertise": "account", "tier": "mid"},
    {"name": "Omar Haddad", "email": "omar.haddad@nimbus.example.com", "expertise": "shipping", "tier": "junior"},
    {"name": "Grace Liu", "email": "grace.liu@nimbus.example.com", "expertise": "account", "tier": "junior"},
    {"name": "Ravi Patel", "email": "ravi.patel@nimbus.example.com", "expertise": "general", "tier": "junior"},
]


def assign(category: str, priority: str, ticket_id: str) -> dict:
    cat = (category or "general").lower()
    prio = (priority or "medium").lower()
    # match expertise; fall back to the generalist, then the whole roster
    pool = [p for p in ROSTER if p["expertise"] == cat] or [p for p in ROSTER if p["expertise"] == "general"] or ROSTER
    if prio in ("critical", "high"):  # hot tickets prefer a senior in that pool
        pool = [p for p in pool if p["tier"] == "senior"] or pool
    # deterministic spread across the pool, no shared counter needed
    agent = pool[sum(ord(ch) for ch in ticket_id) % len(pool)]
    return {"name": agent["name"], "email": agent["email"], "expertise": agent["expertise"], "tier": agent["tier"]}
