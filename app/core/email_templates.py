from app.core.config import settings

_BASE_STYLE = "font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; background-color: #0a1428; padding: 40px 20px;"


def _wrap(title: str, body_html: str) -> str:
    return f"""
    <html>
      <body style="{_BASE_STYLE}">
        <div style="max-width: 480px; margin: 0 auto; background: #0f1f3d; border-radius: 16px; overflow: hidden; border: 1px solid #16274a;">
          <div style="background: linear-gradient(135deg, #007aff 0%, #8c52ff 100%); padding: 28px 32px;">
            <span style="color: #ffffff; font-size: 22px; font-weight: 800;">ClickPic</span>
          </div>
          <div style="padding: 32px;">
            <h1 style="color: #f7f9fc; font-size: 20px; margin: 0 0 12px;">{title}</h1>
            {body_html}
            <p style="color: #a6b3d1; font-size: 12px; margin-top: 32px;">
              If you didn't request this, you can safely ignore this email.
            </p>
          </div>
        </div>
      </body>
    </html>
    """


def _code_block(code: str, description: str) -> str:
    return f"""
      <p style="color: #a6b3d1; font-size: 14px; line-height: 1.6;">
        {description} This code expires in {settings.EMAIL_CODE_EXPIRE_MINUTES} minutes.
      </p>
      <div style="text-align: center; margin: 28px 0;">
        <span style="display: inline-block; background: #0a1428; border: 1px solid #16274a; border-radius: 12px;
          padding: 16px 28px; font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #ffffff;">
          {code}
        </span>
      </div>
    """


def verification_code_email(code: str) -> str:
    body = _code_block(code, "Use the code below to verify your ClickPic account.")
    return _wrap("Verify your email", body)


def password_reset_code_email(code: str) -> str:
    body = _code_block(code, "Use the code below to reset your ClickPic password.")
    return _wrap("Reset your password", body)
