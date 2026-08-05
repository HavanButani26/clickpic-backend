import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.slugify import make_unique_suffix, slugify
from app.models.event import Event, EventStatus
from app.models.studio import Studio
from app.models.user import User
from app.schemas.event import EventCreate, EventListResponse, EventOut, EventUpdate

router = APIRouter(prefix="/api/v1/events", tags=["events"])


async def _generate_unique_slug(db: AsyncSession, name: str) -> str:
    base = slugify(name)
    slug = base
    # Collisions are unlikely (exact same event name) but not impossible
    # across different owners, so fall back to a short random suffix.
    for _ in range(5):
        result = await db.execute(select(Event.id).where(Event.slug == slug))
        if result.scalar_one_or_none() is None:
            return slug
        slug = f"{base}-{make_unique_suffix()}"
    # Extremely unlikely fallback path: a longer random suffix all but
    # guarantees uniqueness if the short ones kept colliding.
    return f"{base}-{make_unique_suffix(10)}"


async def _get_owned_studio_id(
    db: AsyncSession, user_id: uuid.UUID
) -> uuid.UUID | None:
    result = await db.execute(select(Studio.id).where(Studio.owner_id == user_id))
    return result.scalar_one_or_none()


async def _get_owned_event(
    db: AsyncSession, event_id: uuid.UUID, user_id: uuid.UUID
) -> Event:
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.owner_id == user_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return event


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Event:
    slug = await _generate_unique_slug(db, payload.name)
    studio_id = await _get_owned_studio_id(db, current_user.id)

    event = Event(
        id=uuid.uuid4(),
        owner_id=current_user.id,
        studio_id=studio_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        location=payload.location,
        event_date=payload.event_date,
        cover_image_url=payload.cover_image_url,
        status=EventStatus(payload.status),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.get("", response_model=EventListResponse)
async def list_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
    status_filter: Literal["draft", "published", "archived"] | None = Query(
        default=None, alias="status"
    ),
    q: str | None = Query(default=None, max_length=255),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventListResponse:
    filters = [Event.owner_id == current_user.id]
    if status_filter:
        filters.append(Event.status == EventStatus(status_filter))
    if q:
        filters.append(Event.name.ilike(f"%{q}%"))

    count_result = await db.execute(
        select(func.count()).select_from(Event).where(*filters)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Event)
        .where(*filters)
        .order_by(Event.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()

    return EventListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Event:
    return await _get_owned_event(db, event_id, current_user.id)


@router.patch("/{event_id}", response_model=EventOut)
async def update_event(
    event_id: uuid.UUID,
    payload: EventUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Event:
    event = await _get_owned_event(db, event_id, current_user.id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value is not None:
            value = EventStatus(value)
        setattr(event, field, value)

    # Slug is intentionally left untouched even when the name changes —
    # guest-facing links (QR codes, shared URLs) point at the slug and
    # shouldn't silently break because someone renamed their event.
    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    event = await _get_owned_event(db, event_id, current_user.id)
    await db.delete(event)
    await db.commit()
