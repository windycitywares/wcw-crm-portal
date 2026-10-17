"""Segments: a target list whose members come from rules instead of from a member table.

A segment is the same `target_lists` row with `kind="segment"` and `rules`: a small, closed rule set that is
evaluated as a query whenever the audience is counted, listed or (next batch) sent to — so it is always
current and nothing has to be synced. A static list leaves `rules` NULL.

Revision ID: 0019_segments
Revises: 0018_target_lists
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019_segments"
down_revision = "0018_target_lists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("target_lists", sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("target_lists", "rules")
