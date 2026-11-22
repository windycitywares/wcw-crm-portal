"""channel_connections: one row per marketplace (Etsy now) — app credentials and the granted access, sealed.

Revision ID: 0039_channel_connections
Revises: 0038_account_deals
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0039_channel_connections"
down_revision = "0038_account_deals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_connections",
        sa.Column("channel", sa.String(20), primary_key=True),
        sa.Column("client_id", sa.String(100)),
        sa.Column("client_secret_enc", sa.Text()),
        sa.Column("external_shop_id", sa.BigInteger()),
        sa.Column("shop_name", sa.String(200)),
        sa.Column("access_token_enc", sa.Text()),
        sa.Column("refresh_token_enc", sa.Text()),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("scopes", sa.String(500)),
        sa.Column("connected_at", sa.DateTime(timezone=True)),
        sa.Column("connected_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("oauth_state", sa.String(200)),
        sa.Column("oauth_verifier_enc", sa.Text()),
        sa.Column("listings_synced_at", sa.DateTime(timezone=True)),
        sa.Column("orders_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(500)),
        sa.Column("last_error_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("channel_connections")
