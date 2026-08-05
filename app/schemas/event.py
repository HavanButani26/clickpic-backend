import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

EventStatusLiteral = Literal["draft", "published", "archived"]


class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    location: str | None = Field(default=None, max_length=255)
    event_date: date | None = None
    cover_image_url: str | None = None
    status: EventStatusLiteral = "draft"


class EventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    location: str | None = Field(default=None, max_length=255)
    event_date: date | None = None
    cover_image_url: str | None = None
    status: EventStatusLiteral | None = None


class EventOut(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    studio_id: uuid.UUID | None
    name: str
    slug: str
    description: str | None
    location: str | None
    event_date: date | None
    cover_image_url: str | None
    status: EventStatusLiteral
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    items: list[EventOut]
    total: int
    page: int
    page_size: int
