"""Seed the staff accounts plus a demo customer. Idempotent: run any time."""
import asyncio

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


async def main():
    await u.create_user_table()
    async with u.session_maker() as session:
        db = u.SQLAlchemyUserDatabase(session, u.User)
        mgr = u.UserManager(db)
        for email, password, role in SEEDS:
            try:
                user = await mgr.create(UserCreate(email=email, password=password))
                # seeded accounts skip inbox verification: they are ours by definition
                await db.update(user, {"role": role, "is_verified": True})
                print(f"created {email} as {role}")
            except UserAlreadyExists:
                # the flag matters now, so repair accounts seeded before verification existed
                existing = await db.get_by_email(email)
                await db.update(existing, {"role": role, "is_verified": True})
                print(f"repaired {email} as {role}")


asyncio.run(main())
