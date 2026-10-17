"""Support tickets, their messages and SLA policies.

Revision ID: 0012_tickets
Revises: 0011_tasks
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_tickets"
down_revision = "0011_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sla_policies",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("ticket_type", sa.String(length=60), nullable=True),
        sa.Column("priority", sa.String(length=60), nullable=True),
        sa.Column("first_response_minutes", sa.Integer(), nullable=False),
        sa.Column("resolve_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_sla_policies_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_sla_policies_updated_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_sla_policies"),
    )
    op.create_index("ix_sla_policies_match", "sla_policies", ["priority", "ticket_type"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.String(length=16), nullable=True),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ticket_type", sa.String(length=60), nullable=True),
        sa.Column("priority", sa.String(length=60), server_default="normal", nullable=False),
        sa.Column("status", sa.String(length=10), server_default="new", nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("shop_order_id", sa.BigInteger(), nullable=True),
        sa.Column("assignee_id", sa.BigInteger(), nullable=True),
        sa.Column("sla_policy_id", sa.BigInteger(), nullable=True),
        sa.Column("first_response_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolve_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_response_breached", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("resolve_breached", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("custom_fields", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_tickets_customer_id_customers", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], name="fk_tickets_assignee_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sla_policy_id"], ["sla_policies.id"], name="fk_tickets_sla_policy_id_sla_policies", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_tickets_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_tickets_updated_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_tickets"),
        sa.UniqueConstraint("number", name="uq_tickets_number"),
    )
    op.create_index("ix_tickets_status_priority", "tickets", ["status", "priority"])
    op.create_index("ix_tickets_customer", "tickets", ["customer_id"])
    op.create_index("ix_tickets_assignee_open", "tickets", ["assignee_id"],
                    postgresql_where=sa.text("deleted_at IS NULL AND status IN ('new','open','pending')"))
    op.create_index("ix_tickets_resolve_due", "tickets", ["resolve_due_at"],
                    postgresql_where=sa.text("deleted_at IS NULL AND status IN ('new','open','pending')"))
    op.create_index("ix_tickets_deleted_at", "tickets", ["deleted_at"])

    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("direction", sa.String(length=10), server_default="internal", nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("from_email", sa.String(length=320), nullable=True),
        sa.Column("to_email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name="fk_ticket_messages_ticket_id_tickets", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_ticket_messages_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_ticket_messages_updated_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_ticket_messages"),
    )
    op.create_index("ix_ticket_messages_ticket", "ticket_messages", ["ticket_id", "id"])


def downgrade() -> None:
    op.drop_table("ticket_messages")
    op.drop_table("tickets")
    op.drop_table("sla_policies")
