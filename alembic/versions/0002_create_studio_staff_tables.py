"""create studio, role, studio_staff tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "studios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "studio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "permissions", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    # create_type=False here is the fix: without it, op.create_table() below
    # ALSO tries to auto-create this same enum as part of its own DDL
    # (since the Column embeds the raw type object), colliding with the
    # explicit .create() call right after this — even though that call
    # itself has checkfirst=True, the table-creation-triggered one doesn't
    # inherit that setting.
    staff_status = postgresql.ENUM(
        "invited", "active", "revoked", name="staff_status", create_type=False
    )
    staff_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "studio_staff",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "studio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("invited_email", sa.String(length=255), nullable=False),
        sa.Column("invite_token", sa.String(length=255), nullable=True, unique=True),
        sa.Column("status", staff_status, nullable=False, server_default="invited"),
        sa.Column(
            "invited_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_studio_staff_invite_token", "studio_staff", ["invite_token"], unique=True
    )
    op.create_index("ix_studio_staff_invited_email", "studio_staff", ["invited_email"])


def downgrade() -> None:
    op.drop_index("ix_studio_staff_invited_email", table_name="studio_staff")
    op.drop_index("ix_studio_staff_invite_token", table_name="studio_staff")
    op.drop_table("studio_staff")
    op.drop_table("roles")
    op.drop_table("studios")

    staff_status = postgresql.ENUM(
        "invited", "active", "revoked", name="staff_status", create_type=False
    )
    staff_status.drop(op.get_bind(), checkfirst=True)
