import type { Flow, FlowId } from "./types";

/** The big pictures: the order things are done in, one box per page. Every box opens its page. */
export const FLOWS: Record<FlowId, Flow> = {
  etsy: {
    id: "etsy",
    title: "From Etsy listing to supplier payment",
    intro: "Set things up once (the first four boxes), then orders flow through on their own.",
    nodes: [
      { id: "connect", label: "Connect Etsy", href: "/settings/channels", note: "Link your shop once, so listings and orders arrive here." },
      { id: "types", label: "Product types & SKUs", href: "/settings/product-types", note: "Say what you sell, its sizes and how its SKU is written." },
      { id: "listings", label: "Listings", href: "/channels/etsy/listings", note: "Your Etsy listings, copied in. You only read them here." },
      { id: "products", label: "Products", href: "/channels/etsy/products", note: "Give each listing a type, a supplier and what one piece costs." },
      { id: "variations", label: "Check variations", href: "/channels/etsy/products/review", note: "Confirm what each Etsy variation means (how many pieces, which size)." },
      { id: "extras", label: "Extra costs", href: "/settings/extra-costs", note: "Add things like packaging or a discount, per piece or per order." },
      { id: "skus", label: "SKUs vs Etsy", href: "/channels/etsy/skus", note: "Compare the SKU each variation should have with what Etsy has." },
      { id: "orders", label: "Orders", href: "/channels/etsy/orders", note: "Paid orders arrive on their own. Enter what you paid and shipped." },
      { id: "payments", label: "Supplier payments", href: "/channels/etsy/payments", note: "See what you owe each supplier and mark what you have paid." },
    ],
  },
  sales: {
    id: "sales",
    title: "From a possible customer to a won deal",
    intro: "A person starts as a lead, becomes a customer, and any sale to them is tracked as a deal on a pipeline.",
    nodes: [
      { id: "pipelines", label: "Pipelines", href: "/settings/pipelines", note: "Set up the stages a deal moves through. Done once." },
      { id: "leads", label: "Leads", href: "/leads", note: "People who might buy. Contact them and mark how it went." },
      { id: "customers", label: "Customers", href: "/customers", note: "A lead who is serious becomes a customer, with all their history in one place." },
      { id: "deals", label: "Deals", href: "/sales", note: "Each possible sale, moved along its stages until it is won or lost." },
      { id: "tasks", label: "Tasks", href: "/tasks", note: "Follow-ups so nobody is forgotten: calls, emails, reminders." },
      { id: "reports", label: "Reports", href: "/reports", note: "See the forecast and what was won." },
    ],
  },
  support: {
    id: "support",
    title: "From a customer's message to a solved ticket",
    intro: "Every conversation is a ticket. Messages arrive by email or from the shop's contact form, and the clock starts when they arrive.",
    nodes: [
      { id: "mailbox", label: "Email accounts", href: "/settings/email-accounts", note: "Connect the mailbox the CRM reads. Done once." },
      { id: "sla", label: "SLA policies", href: "/settings/sla-policies", note: "Set how fast you promise to reply and to solve." },
      { id: "inbox", label: "Inbox", href: "/inbox", note: "New messages wait here for a reply." },
      { id: "tickets", label: "Tickets", href: "/tickets", note: "Assign it, reply, change the status until it is solved." },
      { id: "customers", label: "Customers", href: "/customers", note: "The customer's page shows all their tickets and orders." },
      { id: "reports", label: "Reports", href: "/reports", note: "See response times and how many tickets were late." },
    ],
  },
  campaigns: {
    id: "campaigns",
    title: "From an idea to a sent campaign",
    intro: "A campaign is a template sent to an audience. The first two boxes are set up once; people who opt out are never emailed again.",
    nodes: [
      { id: "email", label: "Outgoing email", href: "/settings/email", note: "The sender address and sending limits. Done once." },
      { id: "templates", label: "Templates", href: "/campaigns/templates", note: "Write the email once, with merge fields like the customer's name." },
      { id: "audiences", label: "Audiences", href: "/campaigns/lists", note: "Choose who gets it: a fixed list or a live segment." },
      { id: "campaign", label: "Create campaign", href: "/campaigns/new", note: "Pick the template and audience, then schedule or send." },
      { id: "report", label: "Campaigns", href: "/campaigns", note: "See opens, clicks and unsubscribes for each campaign." },
      { id: "suppressions", label: "Suppressions", href: "/campaigns/suppressions", note: "Addresses that must never be emailed: unsubscribed, bounced or reported." },
    ],
  },
  suppliers: {
    id: "suppliers",
    title: "From a supplier to being paid",
    intro: "Suppliers make what you sell. Their costs flow into Etsy orders and the payments you owe them.",
    nodes: [
      { id: "suppliers", label: "Suppliers", href: "/suppliers", note: "Add each supplier with their contacts and purchasing details." },
      { id: "logins", label: "Supplier logins", href: "/settings/supplier-logins", note: "Optional: let a supplier sign in and see only their own orders." },
      { id: "products", label: "Products", href: "/channels/etsy/products", note: "Choose the supplier for each product and enter the cost." },
      { id: "orders", label: "Etsy orders", href: "/channels/etsy/orders", note: "Orders pick up the supplier and cost automatically." },
      { id: "payments", label: "Supplier payments", href: "/channels/etsy/payments", note: "See what you owe each supplier and record what you pay." },
    ],
  },
  setup: {
    id: "setup",
    title: "Setting up the CRM, in a sensible order",
    intro: "Most of this is done once. Go down the list and the CRM will be ready for your team.",
    nodes: [
      { id: "users", label: "Users", href: "/settings/users", note: "Add your team and give each person a role." },
      { id: "types", label: "Types, tags and fields", href: "/settings/types", note: "Make the choice lists match how you talk about your business." },
      { id: "pipelines", label: "Pipelines", href: "/settings/pipelines", note: "Set the stages your deals go through." },
      { id: "hours", label: "Business hours", href: "/settings/business-hours", note: "Opening hours and holidays, so reply deadlines are fair." },
      { id: "sla", label: "SLA policies", href: "/settings/sla-policies", note: "How fast you promise to reply to and solve tickets." },
      { id: "email", label: "Email", href: "/settings/email", note: "The address the CRM sends from, and its limits." },
      { id: "mailboxes", label: "Email accounts", href: "/settings/email-accounts", note: "The mailboxes the inbox reads." },
      { id: "integrations", label: "Integrations", href: "/settings/integrations", note: "Connect the shop and other channels." },
    ],
  },
};
