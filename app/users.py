import os
import uuid

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy import Column, String
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()
SECRET = os.getenv("AUTH_SECRET", "")
if not SECRET:
    raise RuntimeError("AUTH_SECRET missing from .env")

# reuse the app's DATABASE_URL but through the async driver fastapi-users needs
ASYNC_DB_URL = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    # customer (open signup) | staff (seeded) | admin (seeded)
    role = Column(String, nullable=False, default="customer")


engine = create_async_engine(ASYNC_DB_URL)
session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_user_table():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_user_db():
    async with session_maker() as session:
        yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request=None):
        # open signup is customer-only; a fresh customer must prove the inbox is theirs
        # before they can file or read tickets (the claim-any-email hole)
        if user.role == "customer" and not user.is_verified:
            try:
                await self.request_verify(user, request)
            except Exception as e:
                print(f"[verify] could not start verification for {user.email}: {e}", flush=True)

    async def on_after_request_verify(self, user: User, token: str, request=None):
        from app.email_channel import send_email  # local import: email creds are optional at boot

        # a blank value in the file must fall back too, not just a missing key
        base = os.getenv("FRONTEND_URL") or "http://localhost:3000"
        body = (
            "Welcome! Confirm this is your inbox by opening the link below.\n\n"
            f"{base}/verify?token={token}\n\n"
            "If you did not sign up, ignore this email."
        )
        try:
            send_email(user.email, "Verify your email", body)
        except Exception as e:
            # mail being down must never break signup; the user can request a resend
            print(f"[verify] could not send verification email to {user.email}: {e}", flush=True)


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


cookie_transport = CookieTransport(cookie_name="enklima", cookie_max_age=60 * 60 * 24 * 7, cookie_secure=False)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=60 * 60 * 24 * 7)


auth_backend = AuthenticationBackend(name="cookie", transport=cookie_transport, get_strategy=get_jwt_strategy)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])
current_user = fastapi_users.current_user(active=True, verified=True)


def require_staff(user: User = Depends(current_user)) -> User:
    if user.role not in ("staff", "admin"):
        raise HTTPException(status_code=403, detail="staff only")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    return user
