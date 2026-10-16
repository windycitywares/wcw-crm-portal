"""Tags, notes and the activity timeline (shared by every record type).

Revision ID: 0003_tags_notes_activities
Revises: 0002_lookups
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_tags_notes_activities"
down_revision = "0002_lookups"
branch_labels = None
depends_on = None


def _audit_cols(table: str) -> list:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=f"fk_{table}_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name=f"fk_{table}_updated_by_users", ondelete="SET NULL"),
    ]


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("name_key", sa.String(length=60), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        *_audit_cols("tags"),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        sa.UniqueConstraint("name_key", name="uq_tags_name_key"),
    )
    op.create_table(
        "taggings",
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name="fk_taggings_tag_id_tags", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_taggings_created_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("tag_id", "entity_type", "entity_id", name="pk_taggings"),
    )
    op.create_index("ix_taggings_entity", "taggings", ["entity_type", "entity_id"], unique=False)

    op.create_table(
        "notes",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_cols("notes"),
        sa.PrimaryKeyConstraint("id", name="pk_notes"),
    )
    op.create_index("ix_notes_entity", "notes", ["entity_type", "entity_id"], unique=False)
    op.create_index("ix_notes_deleted_at", "notes", ["deleted_at"], unique=False)

    op.create_table(
        "activities",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_activities_actor_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_activities"),
    )
    op.create_index("ix_activities_entity_at", "activities", ["entity_type", "entity_id", "at"], unique=False)


def downgrade() -> None:
    op.drop_table("activities")
    op.drop_table("notes")
    op.drop_table("taggings")
    op.drop_table("tags")
