"""Initial MVP schema: tickets/messages with VARCHAR status, role, category."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from ticketing import constants

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        constants.TABLE_TICKETS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(320), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        f"ix_{constants.TABLE_TICKETS}_user_id",
        constants.TABLE_TICKETS,
        ["user_id"],
    )
    op.create_index(
        f"ix_{constants.TABLE_TICKETS}_status",
        constants.TABLE_TICKETS,
        ["status"],
    )

    op.create_table(
        constants.TABLE_MESSAGES,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.String(36),
            sa.ForeignKey(f"{constants.TABLE_TICKETS}.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        f"ix_{constants.TABLE_MESSAGES}_ticket_id",
        constants.TABLE_MESSAGES,
        ["ticket_id"],
    )


def downgrade() -> None:
    op.drop_table(constants.TABLE_MESSAGES)
    op.drop_table(constants.TABLE_TICKETS)
