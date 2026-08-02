from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings


async def send_email(to_email: str, subject: str, html_body: str) -> None:
    message = EmailMessage()
    from_address = settings.EMAIL_FROM_ADDRESS or settings.EMAIL_HOST_USER
    message["From"] = f"{settings.EMAIL_FROM_NAME} <{from_address}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content("This email requires an HTML-capable client to view.")
    message.add_alternative(html_body, subtype="html")

    if not settings.EMAIL_HOST or not settings.EMAIL_HOST_USER:
        print(f"[email] SMTP not configured — skipped sending to {to_email}")
        return

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            username=settings.EMAIL_HOST_USER,
            password=settings.EMAIL_HOST_PASSWORD,
            start_tls=True,
        )
    except (
        Exception
    ) as exc:  # noqa: BLE001 — delivery failures must never break the request
        print(f"[email] Failed to send email to {to_email}: {exc}")
