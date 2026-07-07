#Synthetic support roster.
#Maps a ticket's priority to an experience tier.
#Then picks a specific assignee from that tier.

ROSTER={
    "senior":[
        {
            "name": "Priya Nair",
            "email": "priya.nair@support.example.com",
        },
        {
            "name": "Marcus Reed",
            "email": "marcus.reed@support.example.com",
        },
    ],
    "mid":[
        {
            "name": "Sofia Alvarez",
            "email": "sofia.alvarez@support.example.com",
        },
        {
            "name": "Tom Becker",
            "email":"tom.becker@support.example.com",

        }
    ],
    "junior": [
        {
            "name": "Aisha Khan",
            "email": "aisha.khan@support.example.com",
        },
    ],
}

#which experience tier handles each priority
TIER_FOR_PRIORITY = {
    "critical" : "senior",
    "high" : "senior",
    "medium": "mid",
    "low": "low",
}

def assign(priority: str, ticket_id: str) -> dict:
    tier = TIER_FOR_PRIORITY.get(priority, "mid") #unknown priority gets sent -> mid (safe default)
    team = ROSTER[tier]

    # spread load deterministically across the tier, no shared counter needed
    agent = team[sum(ord(ch) for ch in ticket_id) % len(team)]
    return {"tier": tier, "name": agent["name"], "email": agent["email"]}