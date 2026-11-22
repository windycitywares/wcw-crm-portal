"""suppliers become accounts: every supplier gets an Account (type "supplier") and its people become Contacts.

* `lookup_values` gets the account_type list (the seed would skip a list that already had one value).
* `accounts.primary_contact_id` — who to talk to first (what the shop shows as the supplier's contact).
* `suppliers.account_id` — one account per supplier; archived suppliers get an archived account.
* every live `supplier_contacts` row becomes a contact typed "vendor" at that account (an existing contact with
  the same email is linked instead, so one person stays one row). `supplier_contacts` is left as it was.

Revision ID: 0037_supplier_accounts
Revises: 0036_accounts
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0037_supplier_accounts"
down_revision = "0036_accounts"
branch_labels = None
depends_on = None

ACCOUNT_TYPES = (("customer", "Customer"), ("supplier", "Supplier"), ("partner", "Partner"),
                 ("prospect", "Prospect"), ("marketplace", "Marketplace"), ("other", "Other"))


def upgrade() -> None:
    bind = op.get_bind()
    for position, (key, label) in enumerate(ACCOUNT_TYPES):
        bind.execute(sa.text(
            "INSERT INTO lookup_values (kind, key, label, sort_order) VALUES ('account_type', :k, :l, :p) "
            "ON CONFLICT (kind, key) DO NOTHING"), {"k": key, "l": label, "p": position})
    # contacts' "vendor" type is what a supplier's people carry
    bind.execute(sa.text(
        "INSERT INTO lookup_values (kind, key, label, sort_order) VALUES ('contact_type', 'vendor', 'Vendor', 3) "
        "ON CONFLICT (kind, key) DO NOTHING"))

    op.add_column("accounts", sa.Column("primary_contact_id", sa.BigInteger(),
                                        sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True))
    op.add_column("suppliers", sa.Column("account_id", sa.BigInteger(),
                                         sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True))
    op.create_index("uq_suppliers_account_id", "suppliers", ["account_id"], unique=True,
                    postgresql_where=sa.text("account_id IS NOT NULL"))

    suppliers = bind.execute(sa.text(
        "SELECT id, name, status, website, address, created_by, created_at, deleted_at FROM suppliers ORDER BY id"
    )).mappings().all()
    for sup in suppliers:
        account_id = bind.execute(sa.text(
            "INSERT INTO accounts (name, account_type, status, website, address, owner_id, created_by, updated_by, "
            "created_at, deleted_at) VALUES (:name, 'supplier', :status, :website, "
            "CAST(:address AS JSONB), :by, :by, :by, :created_at, :deleted_at) RETURNING id"), {
                "name": sup["name"], "status": sup["status"] if sup["status"] in ("active", "inactive") else "active",
                "website": sup["website"],
                "address": None if sup["address"] is None else __import__("json").dumps(sup["address"]),
                "by": sup["created_by"], "created_at": sup["created_at"], "deleted_at": sup["deleted_at"],
            }).scalar_one()
        bind.execute(sa.text("UPDATE suppliers SET account_id = :a WHERE id = :s"), {"a": account_id, "s": sup["id"]})

        people = bind.execute(sa.text(
            "SELECT id, name, title, email, phone, is_primary, created_by, created_at FROM supplier_contacts "
            "WHERE supplier_id = :s AND deleted_at IS NULL ORDER BY is_primary DESC, id"), {"s": sup["id"]}).mappings().all()
        primary = None
        for person in people:
            email = (person["email"] or "").strip().lower() or None
            contact_id = None
            if email:
                contact_id = bind.execute(sa.text(
                    "SELECT id FROM contacts WHERE email = :e AND deleted_at IS NULL"), {"e": email}).scalar()
            if contact_id is not None:
                bind.execute(sa.text(
                    "UPDATE contacts SET account_id = COALESCE(account_id, :a), "
                    "types = CASE WHEN types @> '[\"vendor\"]'::jsonb THEN types ELSE types || '[\"vendor\"]'::jsonb END, "
                    "title = COALESCE(title, :title), phone = COALESCE(phone, :phone), "
                    "company = COALESCE(company, :company) WHERE id = :c"),
                    {"a": account_id, "title": person["title"], "phone": person["phone"], "company": sup["name"],
                     "c": contact_id})
            else:
                first, _, last = " ".join((person["name"] or "").split()).partition(" ")
                contact_id = bind.execute(sa.text(
                    "INSERT INTO contacts (first_name, last_name, company, title, email, phone, types, status, source, "
                    "account_id, owner_id, created_by, updated_by, created_at) VALUES (:f, :l, :company, :title, :e, "
                    ":phone, '[\"vendor\"]'::jsonb, 'active', 'supplier', :a, :by, :by, :by, :at) RETURNING id"), {
                        "f": first[:80], "l": last.strip()[:80], "company": sup["name"], "title": person["title"],
                        "e": email, "phone": person["phone"], "a": account_id, "by": person["created_by"],
                        "at": person["created_at"]}).scalar_one()
            if primary is None and person["is_primary"]:
                primary = contact_id
        if primary is None and people:
            primary = bind.execute(sa.text(
                "SELECT id FROM contacts WHERE account_id = :a AND deleted_at IS NULL ORDER BY id LIMIT 1"),
                {"a": account_id}).scalar()
        if primary is not None:
            bind.execute(sa.text("UPDATE accounts SET primary_contact_id = :c WHERE id = :a"),
                         {"c": primary, "a": account_id})


def downgrade() -> None:
    op.drop_index("uq_suppliers_account_id", table_name="suppliers")
    op.drop_column("suppliers", "account_id")
    op.drop_column("accounts", "primary_contact_id")
