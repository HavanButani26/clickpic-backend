from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://clickpic:clickpic@postgres:5432/clickpic"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "change-this-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # CORS — must be an explicit origin (not "*") since cookies require
    # allow_credentials=True, and browsers reject wildcard origins with that.
    FRONTEND_URL: str = "http://localhost:4200"

    # Email (SMTP)
    EMAIL_HOST: str = ""
    EMAIL_PORT: int = 587
    EMAIL_HOST_USER: str = ""
    EMAIL_HOST_PASSWORD: str = ""
    EMAIL_FROM_NAME: str = "ClickPic"
    EMAIL_FROM_ADDRESS: str = ""  # falls back to EMAIL_HOST_USER if left blank

    # Logo shown in emails. Left blank by default so it derives from
    # FRONTEND_URL — meaning it automatically resolves correctly once
    # FRONTEND_URL is a real deployed domain, no code changes needed. Set
    # this explicitly only if the logo ends up hosted somewhere separate
    # from the frontend itself (e.g. a CDN).
    LOGO_URL: str = ""

    # Email verification / password reset codes
    EMAIL_CODE_EXPIRE_MINUTES: int = 15
    EMAIL_RESEND_COOLDOWN_SECONDS: int = 30
    EMAIL_CODE_MAX_ATTEMPTS: int = 5
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 10

    @property
    def cookie_secure(self) -> bool:
        # Secure cookies require HTTPS. Off in local dev, on in production.
        return self.ENVIRONMENT == "production"

    @property
    def logo_url(self) -> str:
        return self.LOGO_URL or f"{self.FRONTEND_URL}/logos/email-logo.png"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()