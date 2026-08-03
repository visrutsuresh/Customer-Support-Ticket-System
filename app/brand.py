"""The client's name, read from configuration instead of baked into the pipeline.

Enklima is the PRODUCT; the company running it is per-client CONFIG. The brand
already drove the front end through `GET /config`, but the reply generator and
its reviewer had the demo client's name written into their prompts, so a second
deployment would have signed its replies with the first client's name. This is
the one place that name now comes from.

`BRAND_SIGNOFF` lets a client set the wording outright ("The Nimbus Care Team");
otherwise it is derived from `BRAND_NAME`, which api.py already serves.
"""

import os

from dotenv import load_dotenv

# api.py imports app.agents before app.users, and app.users is what normally loads
# the .env. Loading it here too means the brand is correct whatever the import order.
load_dotenv()

DEFAULT_BRAND = "Support"  # matches api.py's fallback


def brand_name() -> str:
    return os.getenv("BRAND_NAME", DEFAULT_BRAND).strip() or DEFAULT_BRAND


def sign_off() -> str:
    """How outbound replies are signed, e.g. 'The Nimbus Support Team'."""
    explicit = os.getenv("BRAND_SIGNOFF", "").strip()
    if explicit:
        return explicit
    name = brand_name()
    # avoid "The Support Support Team" when no brand is configured
    return "The Support Team" if name.lower() == "support" else f"The {name} Support Team"
