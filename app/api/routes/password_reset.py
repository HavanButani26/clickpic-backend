import secrets
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

from app.api.routes.auth import revoke_all_sessions
from app.core.config import settings
from app.core.database import get_db
from app.core.email import send_email
from app.core.email_templates import password_reset_code_email
from app.core.otp import generate_otp
from app.core.redis_client import redis_client
from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.verification import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyResetCodeRequest,
)

router = APIRouter(prefix="/api/v1/auth/password-reset", tags=["password-reset"])

CODE_PREFIX = "password_reset_code:"
ATTEMPTS_PREFIX = "password_reset_attempts:"
RESEND_COOLDOWN_PREFIX = "password_reset_resend:"
TOKEN_PREFIX = "password_reset_token:"

RESET_TOKEN_COOKIE = "password_reset_token"
# Scoped to this router only — the browser won't attach this cookie to any
# other request, unlike access_token/refresh_token which need to go
# everywhere under /api/v1.
COOKIE_PATH = "/api/v1/auth/password-reset"

GENERIC_MESSAGE = "If an account exists for this email, a reset code has been sent."


@router.post("/request", response_model=MessageResponse)
async def request_password_reset(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Deliberately vague response regardless of outcome — confirming or
    # denying an email's existence here would let an attacker enumerate
    # registered accounts.
    if not user:
        return {"message": GENERIC_MESSAGE}

    if await redis_client.get(f"{RESEND_COOLDOWN_PREFIX}{payload.email}"):
        return {"message": GENERIC_MESSAGE}

    code = generate_otp()
    await redis_client.set(
        f"{CODE_PREFIX}{payload.email}",
        code,
        ex=timedelta(minutes=settings.EMAIL_CODE_EXPIRE_MINUTES),
    )
    await redis_client.delete(f"{ATTEMPTS_PREFIX}{payload.email}")
    await redis_client.set(
        f"{RESEND_COOLDOWN_PREFIX}{payload.email}",
        "1",
        ex=settings.EMAIL_RESEND_COOLDOWN_SECONDS,
    )

    background_tasks.add_task(
        send_email,
        payload.email,
        "Reset your ClickPic password",
        password_reset_code_email(code),
    )

    return {"message": GENERIC_MESSAGE}


@router.post("/verify-code", response_model=MessageResponse)
async def verify_reset_code(
    payload: VerifyResetCodeRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code"
    )

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user:
        raise invalid

    attempts_key = f"{ATTEMPTS_PREFIX}{payload.email}"
    code_key = f"{CODE_PREFIX}{payload.email}"

    attempts = int(await redis_client.get(attempts_key) or 0)
    if attempts >= settings.EMAIL_CODE_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect attempts. Please request a new code.",
        )

    stored_code = await redis_client.get(code_key)
    if not stored_code or stored_code != payload.code:
        await redis_client.incr(attempts_key)
        await redis_client.expire(
            attempts_key,
            int(timedelta(minutes=settings.EMAIL_CODE_EXPIRE_MINUTES).total_seconds()),
        )
        raise invalid

    await redis_client.delete(code_key)
    await redis_client.delete(attempts_key)

    # Same treatment as access/refresh tokens: httpOnly cookie, never in the
    # response body, so JavaScript — and therefore any XSS payload — can't
    # read it during the window between "code verified" and "password
    # actually changed". Path-scoped so it's only ever sent to these two
    # password-reset endpoints, nowhere else.
    reset_token = secrets.token_urlsafe(32)
    await redis_client.set(
        f"{TOKEN_PREFIX}{reset_token}",
        str(user.id),
        ex=timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )
    response.set_cookie(
        key=RESET_TOKEN_COOKIE,
        value=reset_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES * 60,
        path=COOKIE_PATH,
    )

    return {"message": "Code verified"}


@router.post("/reset", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    password_reset_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link"
    )

    if not password_reset_token:
        raise invalid

    token_key = f"{TOKEN_PREFIX}{password_reset_token}"
    user_id = await redis_client.get(token_key)
    if not user_id:
        raise invalid

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise invalid

    user.hashed_password = hash_password(payload.password)
    db.add(user)
    await db.commit()

    await redis_client.delete(token_key)
    response.delete_cookie(RESET_TOKEN_COOKIE, path=COOKIE_PATH)

    # Resetting the password kills every existing session — otherwise a
    # still-valid refresh token from before the reset (another device, or
    # one an attacker had captured) would keep working after this.
    await revoke_all_sessions(str(user.id))

    return {"message": "Password reset successfully"}
