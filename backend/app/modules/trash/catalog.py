"""Every record type that goes to the Trash, and what keeps a parent from being deleted.

One place to read the whole rule: a parent with live children can't be deleted (the error names them); a child can
always be deleted on its own. Line items, notes, files and messages are part of their record, not children of it.
Finished history (closed tickets, done tasks) doesn't block, so a customer you served once can still be deleted.
"""

from __future__ import annotations

from app.core.trash import TrashType, count_in, open_tasks, register_trash

OPEN_TICKET = "status NOT IN ('resolved', 'closed')"
PEOPLE_AT = ("SELECT count(*) FROM contacts c WHERE c.deleted_at IS NULL AND (c.account_id = :id OR c.id IN "
             "(SELECT contact_id FROM account_contacts WHERE account_id = :id AND ended_on IS NULL))")


def _people():
    from sqlalchemy import text

    stmt = text(PEOPLE_AT)

    async def check(session, obj) -> int:
        return int((await session.execute(stmt, {"id": obj.id})).scalar_one())

    return check


def _lead_title(x) -> str:
    return " ".join(p for p in (x.first_name, x.last_name) if p) or x.company or f"Lead #{x.id}"


async def _restore_customer(session, item_id: int, actor) -> None:
    from app.modules.customers.service import CustomerService

    await CustomerService(session).restore(item_id, actor)


def register() -> None:
    from app.modules.accounts.models import Account
    from app.modules.activity.models import Note
    from app.modules.campaigns.models import Campaign, EmailTemplate, TargetList
    from app.modules.contacts.models import Contact
    from app.modules.customers.models import Customer
    from app.modules.leads.models import Lead
    from app.modules.sales.models import Deal, Pipeline
    from app.modules.suppliers.models import Supplier, SupplierProduct
    from app.modules.tasks.models import Task
    from app.modules.tickets.models import Ticket
    from app.modules.urns.models import Urn

    for t in (
        TrashType("customer", "Customer", Customer, lambda x: x.display_name, order=200, restore=_restore_customer,
                  children=(("deal", "deals", count_in("deals", "customer_id")),
                            ("open ticket", "open tickets", count_in("tickets", "customer_id", where=OPEN_TICKET)),
                            ("open task", "open tasks", open_tasks("customer")))),
        TrashType("account", "Account", Account, lambda x: x.name, order=300,
                  children=(("sub-account", "sub-accounts", count_in("accounts", "parent_id")),
                            ("person", "people", _people()),
                            ("deal", "deals", count_in("deals", "account_id")),
                            ("supplier record", "supplier records", count_in("suppliers", "account_id")),
                            ("supplier login", "supplier logins", count_in("supplier_logins", "account_id", live=False)),
                            ("open task", "open tasks", open_tasks("account")))),
        TrashType("contact", "Contact", Contact, lambda x: x.display_name, order=100),
        TrashType("lead", "Lead", Lead, _lead_title, children=(("open task", "open tasks", open_tasks("lead")),)),
        TrashType("deal", "Deal", Deal, lambda x: x.title, order=50,
                  children=(("open task", "open tasks", open_tasks("deal")),)),
        # A pipeline keeps its own rule (no open deals); closed deals just lose their stage if it is purged.
        TrashType("pipeline", "Pipeline", Pipeline, lambda x: x.name, order=250),
        TrashType("task", "Task", Task, lambda x: x.title, order=10),
        TrashType("ticket", "Ticket", Ticket, lambda x: f"{x.number or ''} {x.subject}".strip(), order=50,
                  children=(("open task", "open tasks", open_tasks("ticket")),)),
        TrashType("supplier", "Supplier", Supplier, lambda x: x.name, order=250,
                  children=(("supplied product", "supplied products", count_in("supplier_products", "supplier_id")),)),
        TrashType("supplier_product", "Supplied product", SupplierProduct,
                  lambda x: x.description or x.shop_sku, order=40),
        TrashType("email_template", "Email template", EmailTemplate, lambda x: x.name, order=250,
                  children=(("campaign", "campaigns", count_in("campaigns", "template_id")),)),
        TrashType("target_list", "Audience", TargetList, lambda x: x.name, order=250,
                  children=(("campaign", "campaigns", count_in("campaigns", "target_list_id")),)),
        TrashType("campaign", "Campaign", Campaign, lambda x: x.name, order=60),
        TrashType("urn", "Urn", Urn, lambda x: f"#{x.id} {x.name}", order=60),
        TrashType("note", "Note", Note, lambda x: (x.body or "")[:80], order=10),
    ):
        register_trash(t)
