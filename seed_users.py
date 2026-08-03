"""Seed the staff accounts plus a demo customer. Idempotent: run any time.

The passwords below are DEVELOPMENT defaults and this repository is public, so anyone
can read them. A deployment must override them from the environment:

    SEED_ADMIN_PASSWORD=... SEED_STAFF_PASSWORD=... SEED_CUSTOMER_PASSWORD=... \\
    DATABASE_URL=<the deployed database> uv run python seed_users.py

Run that way against a database whose accounts already exist and it ROTATES their
passwords, which is how a leaked development credential actually gets retired.
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

import app.users as u  # noqa: E402
from app.schemas import UserCreate  # noqa: E402
from fastapi_users.exceptions import UserAlreadyExists  # noqa: E402

SEEDS = [
    ("admin@nimbus.dev", "admin-dev-password", "admin"),
    ("dana@nimbus.dev", "staff-dev-password", "staff"),
    ("marco@nimbus.dev", "staff-dev-password", "staff"),
    ("customer@nimbus.dev", "customer-dev-password", "customer"),
]

# Per-role overrides. The literals above stay as the local-development default, so
# nothing changes on a developer machine, but a deployment can and must supply its own.
_OVERRIDES = {
    "admin": os.getenv("SEED_ADMIN_PASSWORD", "").strip(),
    "staff": os.getenv("SEED_STAFF_PASSWORD", "").strip(),
    "customer": os.getenv("SEED_CUSTOMER_PASSWORD", "").strip(),
}
SEEDS = [(email, _OVERRIDES.get(role) or pw, role) for email, pw, role in SEEDS]


async def main():
    await u.create_user_table()
    async with u.session_maker() as session:
        db = u.SQLAlchemyUserDatabase(session, u.User)
        mgr = u.UserManager(db)
        for email, password, role in SEEDS:
            try:
                user = await mgr.create(UserCreate(email=email, password=password))
                await db.update(user, {"role": role})
                print(f"created {email} as {role}")
            except UserAlreadyExists:
                # re-running must still correct the role on an account that already exists
                existing = await db.get_by_email(email)
                patch = {"role": role}
                if _OVERRIDES.get(role):
                    # an override was supplied, so this run is a ROTATION: replace the
                    # stored hash too, or the published default would keep working.
                    # hashed explicitly, because db.update writes the column raw
                    patch["hashed_password"] = mgr.password_helper.hash(password)
                await db.update(existing, patch)
                what = "repaired + rotated" if _OVERRIDES.get(role) else "repaired"
                print(f"{what} {email} as {role}")

    if not any(_OVERRIDES.values()):
        print(
            "\nNOTE: seeded with the development passwords published in this public "
            "repository. Fine locally. For any reachable deployment, set "
            "SEED_ADMIN_PASSWORD, SEED_STAFF_PASSWORD, SEED_CUSTOMER_PASSWORD "
            "and run this again to rotate them."
        )


# guarded: importing this module must not seed a database
if __name__ == "__main__":
    asyncio.run(main())
