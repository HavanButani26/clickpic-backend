"""create events table

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type explicitly first (checkfirst=True is safe on
    # rerun), then reference it with create_type=False in the table
    # definition below — otherwise create_table() tries to auto-create the
    # same enum a second time and collides with this explicit call.
    postgresql.ENUM("draft", "published", "archived", name="event_status").create(
        op.get_bind(), checkfirst=True
    )
    event_status = postgresql.ENUM(
        "draft", "published", "archived", name="event_status", create_type=False
    )

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "studio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=280), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("cover_image_url", sa.String(length=500), nullable=True),
        sa.Column("status", event_status, nullable=False, server_default="draft"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_events_owner_id", "events", ["owner_id"])
    op.create_index("ix_events_slug", "events", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_events_slug", table_name="events")
    op.drop_index("ix_events_owner_id", table_name="events")
    op.drop_table("events")
    postgresql.ENUM(name="event_status").drop(op.get_bind(), checkfirst=True)
