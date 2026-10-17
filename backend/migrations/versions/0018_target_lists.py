"""Target lists: the audiences a campaign goes to, and the customers on them.

Revision ID: 0018_target_lists
Revises: 0017_campaigns
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_target_lists"
down_revision = "0017_campaigns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "target_lists",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("kind", sa.String(length=10), server_default="static", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_target_lists_created_by_users",
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_target_lists_updated_by_users",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_target_lists"),
    )
    op.create_index("ix_target_lists_deleted_at", "target_lists", ["deleted_at"])

    op.create_table(
        "target_list_members",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("list_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["list_id"], ["target_lists.id"], name="fk_target_list_members_list_id_target_lists",
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"],
                                name="fk_target_list_members_customer_id_customers", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"],
                                name="fk_target_list_members_created_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_target_list_members"),
        sa.UniqueConstraint("list_id", "customer_id", name="uq_target_list_members_list_customer"),
    )
    op.create_index("ix_target_list_members_customer", "target_list_members", ["customer_id"])


def downgrade() -> None:
    op.drop_table("target_list_members")
    op.drop_table("target_lists")
