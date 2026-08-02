import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    account_type: Literal["individual", "studio"] = "individual"
    studio_name: str | None = None

    @model_validator(mode="after")
    def studio_name_required_for_studio(self) -> "RegisterRequest":
        if self.account_type == "studio" and not self.studio_name:
            raise ValueError("studio_name is required when account_type is 'studio'")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    account_type: str
    studio_name: str | None
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str