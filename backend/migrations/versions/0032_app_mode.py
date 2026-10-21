"""app_mode: live / test switch (one row, id = 1).

The test copy lives in the `wcw_test` schema of the same database. Migrations always run on the live
schema (`public`), so this table is created there and read by every connection via the pool checkout hook.

Revision ID: 0032_app_mode
Revises: 0031_contacts
Create Date: 2026-10-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0032_app_mode"
down_revision = "0031_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_mode",
        sa.Column("id", sa.SmallInteger(), primary_key=True, server_default=sa.text("1")),
        sa.Column("mode", sa.String(8), nullable=False, server_default="live"),
        sa.Column("test_mail_to", sa.String(320)),
        sa.Column("test_synced_at", sa.DateTime(timezone=True)),
        sa.Column("test_login_emails", sa.Text()),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("changed_by_email", sa.String(320)),
    )
    op.create_check_constraint("ck_app_mode_single", "app_mode", "id = 1")
    op.create_check_constraint("ck_app_mode_mode", "app_mode", "mode IN ('live', 'test')")
    op.execute("INSERT INTO app_mode (id, mode) VALUES (1, 'live')")


def downgrade() -> None:
    op.drop_table("app_mode")
