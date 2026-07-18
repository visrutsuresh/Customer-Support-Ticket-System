"""Seed the three staff accounts. Idempotent: run any time."""
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
]


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
                print(f"exists  {email}")


asyncio.run(main())
