from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi import Response
from app.api.routes.auth import _issue_session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.email import send_email
from app.core.email_templates import verification_code_email
from app.core.otp import generate_otp
from app.core.redis_client import redis_client
from app.models.user import User
from app.schemas.auth import MessageResponse, UserOut
from app.schemas.verification import ResendCodeRequest, VerifyEmailRequest

router = APIRouter(prefix="/api/v1/auth/verify-email", tags=["verification"])

CODE_PREFIX = "verify_email_code:"
ATTEMPTS_PREFIX = "verify_email_attempts:"
RESEND_COOLDOWN_PREFIX = "verify_email_resend:"


async def prepare_verification_code(email: str) -> str:
    """Fast part only: generate the code and write it (+ cooldown) to
    Redis. Kept synchronous/awaited by callers so the cooldown is actually
    in place before the response returns — only the slow SMTP send gets
    backgrounded, never this.
    """
    code = generate_otp()

    await redis_client.set(
        f"{CODE_PREFIX}{email}",
        code,
        ex=timedelta(minutes=settings.EMAIL_CODE_EXPIRE_MINUTES),
    )
    await redis_client.delete(f"{ATTEMPTS_PREFIX}{email}")
    await redis_client.set(
        f"{RESEND_COOLDOWN_PREFIX}{email}",
        "1",
        ex=settings.EMAIL_RESEND_COOLDOWN_SECONDS,
    )

    return code


async def send_verification_code(email: str) -> None:
    """Convenience wrapper used by register(), which backgrounds this
    entire call — a brand-new signup has no prior cooldown to race against.
    """
    code = await prepare_verification_code(email)
    await send_email(
        email, "Verify your ClickPic account", verification_code_email(code)
    )


@router.post("/resend", response_model=MessageResponse)
async def resend_verification_code(
    payload: ResendCodeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    generic_message = "If an account needs verification, a new code has been sent."

    # Same email-enumeration guard as password reset: respond the same way
    # whether or not the account exists or is already verified.
    if not user or user.is_verified:
        return {"message": generic_message}

    if await redis_client.get(f"{RESEND_COOLDOWN_PREFIX}{payload.email}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting another code.",
        )

    code = await prepare_verification_code(payload.email)
    background_tasks.add_task(
        send_email,
        payload.email,
        "Verify your ClickPic account",
        verification_code_email(code),
    )

    return {"message": generic_message}


@router.post("", response_model=UserOut)
async def verify_email(
    payload: VerifyEmailRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code"
    )

    if not user:
        raise invalid

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already verified"
        )

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

    user.is_verified = True
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await redis_client.delete(code_key)
    await redis_client.delete(attempts_key)

    # Verifying the code is itself proof of identity — establish a session
    # immediately so the frontend can redirect straight in, same as login.
    await _issue_session(response, user)

    return user
