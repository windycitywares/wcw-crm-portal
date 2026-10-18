"""Files kept against a record: what a customer sends with their message (SPEC §4.2).

One table, polymorphic the way `notes` and `activities` are (0003): `(entity_type, entity_id)` says what
a file hangs on — a ticket whose customer photographed the damage, and any other record type later, with
no change to this table. `sha256` is the file's own name on the disk (`app/integrations/files`, kept
outside the checkout so a deploy can't take a customer's photo with it), so the same file sent twice is
stored once, two rows may point at one stored file, and the stored bytes go with the last row that
pointed at them. `filename` is what the sender called it: shown and handed back, never used to find
anything. `source` says how the file got here — email today, an upload or a chat attachment later.

Revision ID: 0027_attachments
Revises: 0026_email_in
Create Date: 2026-10-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0027_attachments"
down_revision = "0026_email_in"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_attachments_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_attachments_updated_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_attachments"),
    )
    op.create_index("ix_attachments_entity", "attachments", ["entity_type", "entity_id"], unique=False)
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"], unique=False)
    op.create_index("ix_attachments_deleted_at", "attachments", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_table("attachments")
