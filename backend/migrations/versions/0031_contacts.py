"""contacts: one directory for every person the business deals with.

A contact links to the staff user (`user_id`) and/or the customer (`customer_id`) it mirrors. Existing
customers and staff users are backfilled here, deduped by email, so one person who is both gets a single
row with both types and both links.

Revision ID: 0031_contacts
Revises: 0030_attachment_message
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0031_contacts"
down_revision = "0030_attachment_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("first_name", sa.String(80), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(80), nullable=False, server_default=""),
        sa.Column("company", sa.String(160)),
        sa.Column("title", sa.String(120)),
        sa.Column("email", sa.String(320)),
        sa.Column("alt_emails", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("phone", sa.String(40)),
        sa.Column("address", postgresql.JSONB()),
        sa.Column("types", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("source", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("customer_id", sa.BigInteger(), sa.ForeignKey("customers.id", ondelete="SET NULL")),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("uq_contacts_email_active", "contacts", ["email"], unique=True,
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_contacts_types", "contacts", ["types"], postgresql_using="gin")
    op.create_index("uq_contacts_user_id", "contacts", ["user_id"], unique=True,
                    postgresql_where=sa.text("user_id IS NOT NULL"))
    op.create_index("uq_contacts_customer_id", "contacts", ["customer_id"], unique=True,
                    postgresql_where=sa.text("customer_id IS NOT NULL"))
    op.create_index("ix_contacts_status", "contacts", ["status"])
    op.create_index("ix_contacts_owner_id", "contacts", ["owner_id"])
    op.create_index("ix_contacts_deleted_at", "contacts", ["deleted_at"])

    # 1. Every live customer becomes a contact (email or not).
    op.execute("""
        INSERT INTO contacts (first_name, last_name, company, email, phone, address, types, status, source,
                              customer_id, created_at, updated_at)
        SELECT c.first_name, c.last_name, c.company, lower(c.email), c.phone, c.address,
               '["customer"]'::jsonb, 'active', 'customer', c.id, c.created_at, c.updated_at
        FROM customers c
        WHERE c.deleted_at IS NULL
          AND (c.email IS NULL OR NOT EXISTS (
              SELECT 1 FROM contacts co
              WHERE co.deleted_at IS NULL AND lower(co.email) = lower(c.email)))
    """)

    # 2. Every staff user becomes a contact, unless the email is already a contact.
    op.execute("""
        INSERT INTO contacts (first_name, last_name, email, phone, title, types, status, source, user_id,
                              created_at, updated_at)
        SELECT split_part(u.full_name, ' ', 1),
               CASE WHEN position(' ' in u.full_name) > 0
                    THEN substr(u.full_name, position(' ' in u.full_name) + 1) ELSE '' END,
               lower(u.email), u.phone, u.title, '["user"]'::jsonb, 'active', 'user', u.id,
               u.created_at, u.updated_at
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM contacts co
            WHERE co.deleted_at IS NULL AND lower(co.email) = lower(u.email))
    """)

    # 3. A user whose email is already a contact (e.g. staff who also bought) gets linked, not duplicated.
    op.execute("""
        UPDATE contacts c
        SET types = (SELECT jsonb_agg(DISTINCT t ORDER BY t)
                     FROM jsonb_array_elements_text(c.types || '["user"]'::jsonb) AS t),
            user_id = u.id
        FROM users u
        WHERE c.deleted_at IS NULL AND c.user_id IS NULL AND lower(c.email) = lower(u.email)
    """)


def downgrade() -> None:
    op.drop_table("contacts")
