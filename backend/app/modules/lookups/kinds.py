"""The kinds of type list the CRM has, and their starter values (SPEC §9).

Modules add their own kinds here (one entry each) — nothing else changes. Admins then edit the values
in Settings → Types; the seed only inserts values that don't exist yet, so edits are never undone.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Kind:
    key: str
    label: str
    description: str
    seed: tuple[str, ...] = field(default_factory=tuple)


KINDS: dict[str, Kind] = {k.key: k for k in (
    Kind("customer_type", "Customer types", "How you group customers.",
         ("Retail", "Repeat", "VIP", "Wholesale", "Marketplace (Etsy/Amazon)")),
    Kind("supplier_type", "Supplier types", "What a supplier provides.",
         ("Manufacturer", "Raw materials", "Packaging", "Printing & labels", "Shipping & logistics", "Services")),
    Kind("ticket_type", "Ticket types", "What a support ticket is about.",
         ("Order question", "Shipping & delivery", "Return / exchange", "Damaged / defective", "Custom request",
          "Product question", "Complaint", "Other")),
    Kind("ticket_priority", "Ticket priorities", "How urgent a ticket is (response targets use these).",
         ("Low", "Normal", "High", "Urgent")),
    Kind("task_type", "Task types", "Kinds of to-do.", ("Call", "Email", "Follow-up", "Meeting", "To-do")),
    Kind("lead_source", "Lead sources", "Where a lead or customer came from.",
         ("Website", "Shop", "Etsy", "Amazon", "Referral", "Social media", "Trade show", "Other")),
    Kind("lost_reason", "Lost reasons", "Why a deal was lost.",
         ("Price", "Timing", "Chose competitor", "No response", "Not a fit", "Other")),
)}
