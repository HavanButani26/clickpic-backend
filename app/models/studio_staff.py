import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.studio import Studio
    from app.models.user import User


class StaffStatus(str, enum.Enum):
    INVITED = "invited"
    ACTIVE = "active"
    REVOKED = "revoked"


class StudioStaff(Base):
    __tablename__ = "studio_staff"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    studio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studios.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    # Nullable: an invite record can exist before the invited person has an
    # account at all. Gets linked once they accept and either sign up or
    # log in with a matching email.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    invited_email: Mapped[str] = mapped_column(String(255), nullable=False)
    invite_token: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    status: Mapped[StaffStatus] = mapped_column(
        Enum(StaffStatus, name="staff_status"),
        default=StaffStatus.INVITED,
        nullable=False,
    )

    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    studio: Mapped["Studio"] = relationship("Studio", back_populates="staff")
    role: Mapped["Role | None"] = relationship("Role", back_populates="staff_members")
    user: Mapped["User | None"] = relationship("User", foreign_keys=[user_id])
