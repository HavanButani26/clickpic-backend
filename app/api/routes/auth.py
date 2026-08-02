from datetime import timedelta

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import redis_client
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, MessageResponse, RegisterRequest, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_KEY_PREFIX = "refresh_token:"
USER_SESSIONS_PREFIX = "user_sessions:"


def _set_auth_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


async def _issue_session(response: Response, user: User) -> None:
    access_token = create_access_token(str(user.id))
    refresh_token = generate_refresh_token()

    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    await redis_client.set(
        f"{REFRESH_KEY_PREFIX}{refresh_token}",
        str(user.id),
        ex=timedelta(seconds=ttl_seconds),
    )

    # Track this token under the user's session set so a password reset (or
    # a future "log out everywhere" feature) can revoke every active
    # session for this user, not just the one tied to the current cookie.
    sessions_key = f"{USER_SESSIONS_PREFIX}{user.id}"
    await redis_client.sadd(sessions_key, refresh_token)
    await redis_client.expire(sessions_key, ttl_seconds)

    _set_auth_cookies(response, access_token, refresh_token)


async def _revoke_session(user_id: str, refresh_token: str) -> None:
    await redis_client.delete(f"{REFRESH_KEY_PREFIX}{refresh_token}")
    await redis_client.srem(f"{USER_SESSIONS_PREFIX}{user_id}", refresh_token)


async def revoke_all_sessions(user_id: str) -> None:
    """Kill every active session for this user — used by password reset."""
    sessions_key = f"{USER_SESSIONS_PREFIX}{user_id}"
    tokens = await redis_client.smembers(sessions_key)
    for token in tokens:
        await redis_client.delete(f"{REFRESH_KEY_PREFIX}{token}")
    await redis_client.delete(sessions_key)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        account_type=payload.account_type,
        studio_name=payload.studio_name,
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Sending the code involves a real SMTP round-trip and can take a
    # couple of seconds — backgrounded so the client gets its 201 response
    # immediately instead of waiting on email delivery.
    from app.api.routes.verification import send_verification_code

    background_tasks.add_task(send_verification_code, user.email)

    return user


@router.post("/login", response_model=UserOut)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
    )

    if not user or not verify_password(payload.password, user.hashed_password):
        raise invalid_credentials

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in.",
        )

    await _issue_session(response, user)
    return user


@router.post("/refresh", response_model=MessageResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session",
    )

    if not refresh_token:
        raise unauthorized

    redis_key = f"{REFRESH_KEY_PREFIX}{refresh_token}"
    user_id = await redis_client.get(redis_key)
    if not user_id:
        raise unauthorized

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise unauthorized

    # Rotate: the old refresh token is invalidated and a brand new pair is
    # issued. This limits how long a stolen refresh token stays useful.
    await _revoke_session(user_id, refresh_token)
    await _issue_session(response, user)

    return {"message": "Session refreshed"}


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
) -> dict:
    if refresh_token:
        user_id = await redis_client.get(f"{REFRESH_KEY_PREFIX}{refresh_token}")
        if user_id:
            await _revoke_session(user_id, refresh_token)

    _clear_auth_cookies(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
