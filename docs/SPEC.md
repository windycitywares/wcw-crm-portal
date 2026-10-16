# WCW CRM — Specification

crm.windycitywares.com · Windy City Wares LLC · status: **agreed scope v1 (2026-10-16), decisions recorded §9**

## 1. Purpose

An enterprise-grade, internal CRM for the Windy City Wares team to manage **customers, sales,
tasks, support tickets, campaigns and suppliers** in one place, fed by the shop
(shop.windycitywares.com). B2B is a planned future extension. Communication channels
(unified inbox, live chat, SMS, Etsy messages) come **after** v1 and are designed for, not built.

## 2. Users & roles

Internal staff only (owner + team). No customer-facing login in v1.

| Role | Can do |
|---|---|
| **Admin** | Everything: users, roles, settings, lookup types, integrations, audit, data export/delete |
| **Manager** | All business data (customers, sales, tickets, campaigns, suppliers), reports, assign work; no system settings |
| **Sales** | Customers, leads/deals, tasks, suppliers (view); own records by default, team view if granted |
| **Support** | Customers (view/edit), tickets, tasks |
| **Marketing** | Customers (view), segments/target lists, templates, campaigns, reports |
| **Read-only** | View everything they are granted; change nothing |

Routes depend on **permissions** (`customers:edit`, `tickets:assign`, `campaigns:send`, …), never role
names. Roles → permission sets live in one map (`app/core/permissions.py`), exactly like the shop.
Record-level rule: "own vs any" (owner_id on records) for Sales/Support.

## 3. Modules (v1)

Every module is a self-contained package (see §5). "Types" are admin-editable lookups (§4.1).

### 3.1 Core (platform)
- Auth: JWT + bcrypt, login, forgot/reset password, session timeout, optional 2FA (TOTP) later.
- Users & roles, team assignment, user activation.
- **Lookups** — admin-managed type lists (customer type, supplier type, ticket type/priority, task type, lead source, …).
- **Custom fields** — admin-defined extra fields per entity, stored in `custom_fields JSONB`.
- Tags (shared across entities), notes, file attachments, activity timeline.
- Audit log (who changed what, before/after), soft delete + restore.
- Global search; saved list views (filters, columns, sort) per user.
- Import/export CSV/Excel for every list.
- Notifications (in-app; email digest).

### 3.2 Customers
- Customer (person): name, emails[], phones[], addresses, **customer type** (e.g. Retail, Repeat,
  VIP, Wholesale, Etsy buyer), status, source, owner, tags, custom fields, marketing consent
  (opt-in date, source, unsubscribed).
- Shop link: `shop_user_id` / matched by email; read-only order history and lifetime stats
  (orders, revenue, AOV, first/last order) synced from the shop.
- Duplicate detection & merge.
- Timeline: notes, tasks, tickets, deals, campaign sends/opens/clicks, shop orders.
- **B2B-ready:** `Account` (company) entity designed now, UI enabled later; a customer may belong to an account.

### 3.3 Sales
- Leads (unqualified) → convert to Customer + Deal.
- Deals: title, customer/account, value, currency, expected close, probability, owner, stage.
- **Pipelines & stages** configurable (e.g. Custom Order, Wholesale), kanban drag-and-drop.
- Products/line items on a deal, pulled from the shop catalog (read API).
- Won/lost reason; forecast by stage × probability.
- Later: quotes (PDF), convert quote → shop order.

### 3.4 Tasks
- Task: title, description, **task type** (Call, Email, Follow-up, Meeting, To-do), due date/time,
  priority, status, assignee, related record (customer / deal / ticket / supplier / campaign).
- My tasks, team tasks, overdue view, calendar view; reminders (in-app + email).
- Recurring tasks.

### 3.5 Support tickets
- Ticket: number, subject, description, **ticket type** (Return, Damage, Custom request, Question,
  Complaint, …), priority, status (New → Open → Pending → Resolved → Closed), customer, related
  shop order, assignee, team/queue.
- Internal notes vs customer replies (customer replies by email via SMTP in v1).
- SLA policies per type/priority (first response, resolution) with breach flags.
- Canned responses; CSAT survey after resolve (later).
- Shop contact-form messages can create tickets (integration §6).

### 3.6 Campaigns (email marketing)
- **Email templates**: name, subject, preheader, HTML + text body, merge fields
  (`{{ customer.first_name }}`, `{{ unsubscribe_url }}`), versioned, preview, test send.
  Rendered with a **sandboxed** Jinja2 environment.
- **Target lists / segments**:
  - Static lists (manual or imported CSV).
  - Dynamic segments (rule builder: customer type, tags, order count, last order date, spend, consent…),
    re-evaluated at send time.
- Campaign: template + audience + schedule; statuses draft → scheduled → sending → sent.
- Sending through the email outbox + cron with throttling (cPanel SMTP limits), retries.
- Compliance: consent required, unsubscribe link mandatory, **suppression list**
  (unsubscribed, bounced, complained), physical address footer (CAN-SPAM).
- Tracking: delivered, opened (pixel), clicked (redirect links), unsubscribed; per-campaign report.

### 3.7 Suppliers
- Supplier: name, **supplier type** (Manufacturer, Raw material, Packaging, Printing, Shipping, Service…),
  status, contacts (people), addresses, website, payment terms, lead time, currency, rating, tags,
  custom fields, documents (contracts, price lists).
- Supplied products (link to shop SKU + supplier SKU, cost, MOQ).
- Later: purchase orders, supplier performance.

### 3.8 Reports & dashboard
- Home dashboard: my tasks, open tickets, pipeline value, recent customers, campaign stats.
- Reports: sales pipeline/forecast, won/lost, tickets by type/SLA, campaign performance,
  customers by type/source, supplier list. Export CSV.

### 3.9 Later (designed for, not in v1)
Unified inbox (IMAP email, shop contact form, live chat, Etsy messages, SMS/WhatsApp) ·
B2B accounts UI, price lists, quotes · workflow automation builder · AI assists
(reply drafts, summaries, sentiment) · customer self-service portal · SSO with shop admin.

## 4. Data model (core tables)

All business tables: `id BIGINT`, `created_at`, `updated_at`, `created_by`, `updated_by`,
`deleted_at` (soft delete), `owner_id` where ownership applies, `custom_fields JSONB`, `tags` via join table.

### 4.1 Lookups
`lookup_values(id, kind, key, label, color, sort_order, is_active, is_system)` —
`kind` ∈ customer_type, supplier_type, ticket_type, ticket_priority, task_type, lead_source,
lost_reason, … Adding a new type = a row, never a migration.
Pipelines are their own tables (`pipelines`, `pipeline_stages(order, probability, is_won, is_lost)`).

### 4.2 Main entities
`users, roles, user_roles` · `customers, customer_emails, customer_phones, addresses` ·
`accounts` (B2B, later) · `leads, deals, deal_items, pipelines, pipeline_stages` · `tasks` ·
`tickets, ticket_messages, sla_policies` · `email_templates, template_versions, target_lists,
target_list_members, segments, campaigns, campaign_recipients, campaign_events, suppressions,
email_outbox` · `suppliers, supplier_contacts, supplier_products` · `notes, attachments, tags,
taggings, activities (timeline), audit_log, custom_field_defs, saved_views, notifications` ·
`integration_events` (inbound shop events, idempotency keys).

Polymorphic links (notes, tasks, attachments, activities) use `(entity_type, entity_id)`.

## 5. Architecture — SOLID & modular

### 5.1 Backend (FastAPI) — module-per-feature
```
backend/app/
  core/            config, db, security, permissions, exceptions, events (in-process bus), pagination
  shared/          base model mixins, base repository, base service, lookups, tags, notes,
                   attachments, custom fields, audit, timeline, import/export
  modules/
    customers/     models.py schemas.py repository.py service.py router.py permissions.py events.py
    sales/  tasks/  tickets/  campaigns/  suppliers/  reports/  users/
  integrations/
    shop/          client (read API), webhook receiver, event handlers, mappers
    email/         SMTP sender (interface + impl), template renderer
  workers/         cron entrypoints: outbox sender, campaign dispatcher, SLA checker, shop sync
  main.py          builds the app by registering each module's router
```
Rules:
- **S** — router = HTTP only; service = business rules; repository = queries only; schemas = I/O.
- **O** — new module/type/channel added by registering, not editing others (module registry,
  `@register` handlers, lookup rows, channel interface for future inbox).
- **L** — repositories share a generic `BaseRepository[Model]`; channel/senders implement one interface.
- **I** — small interfaces (`EmailSender`, `TemplateRenderer`, `ShopClient`, `Notifier`).
- **D** — services receive dependencies via FastAPI `Depends`/constructors; no module imports another
  module's repository — cross-module calls go through the other module's **service** or **domain events**
  (e.g. `TicketResolved` → timeline + CSAT).

### 5.2 Frontend (Next.js)
```
frontend/src/
  app/(auth)/login …   app/(crm)/layout.tsx  (sidebar + topbar shell)
  app/(crm)/customers|sales|tasks|tickets|campaigns|suppliers|reports|settings/
  modules/<module>/    components, hooks, api client, types (mirrors backend modules)
  components/ui/       primitives (shadcn/Radix): DataTable, Form, Dialog, Kanban, Timeline, …
  lib/                 api client (JWT), auth, permissions helper (hide UI the user can't use)
```
Generic `DataTable` (server-side paging/filter/sort/saved views/export) and `EntityForm`
(incl. custom fields) are built once and reused by every module.

## 6. Shop integration (v1)

- **Shop → CRM events** (signed HMAC webhooks, retried from the shop's outbox):
  `customer.created/updated`, `order.created/updated`, `contact_message.created`,
  `review.created`, `cart.abandoned`, `newsletter.subscribed/unsubscribed`.
  CRM stores each in `integration_events` (idempotent by event id) and handlers update customers,
  timeline, tickets.
- **CRM → Shop read API** (service token): customer orders, order detail, product catalog search,
  coupon creation (for campaigns/support).
- Initial backfill: one-time import of existing shop customers & orders.
- Consent/unsubscribe synced both ways.

## 7. Non-functional

- Security: OWASP basics, rate limits on auth, secrets in env only, HMAC on webhooks, audit everything.
- Privacy: consent records, export/delete a customer (GDPR/CCPA), PII access by permission.
- Accessibility: WCAG 2.1 AA, keyboard-first tables and kanban.
- Performance: server-side pagination everywhere, indexed filters, JSONB GIN indexes for custom fields.
- Hosting: HostItBro cPanel (same server as the shop) — Python 3.11, Node 20/22, **PostgreSQL 13 with
  no extensions** (no `ltree`, `pg_trgm`, `citext`…; hierarchies use plain-text id paths like the shop);
  backend via Passenger (`backend/wsgi.py`), frontend Next.js standalone;
  background work via cron hitting `workers/` scripts. No WebSockets assumed (polling/SSE).
- Tests: unit tests per service, API tests per router, Playwright e2e for key flows.

## 8. Build order

| Milestone | Scope |
|---|---|
| **M0** | Scaffold backend/frontend, CI, DB, auth, users/roles/permissions, app shell, audit |
| **M1** | Shared building blocks: lookups, tags, notes, attachments, custom fields, timeline, DataTable, import/export |
| **M2** | Customers + customer types + shop integration (webhooks, backfill, order history) |
| **M3** | Tasks + Support tickets (types, SLA, email replies) |
| **M4** | Sales: leads, deals, pipelines kanban |
| **M5** | Campaigns: templates, target lists/segments, sending, tracking, suppression |
| **M6** | Suppliers + types + supplied products |
| **M7** | Dashboard & reports |
| Later | Communication channels (unified inbox), B2B accounts, automation, AI |

## 9. Decisions (2026-10-16)

1. **Roles:** Admin, Manager, Sales, Support, Marketing, Read-only — as in §2. Role → permission map is
   code-defined in v1; assigning roles to users is done in Admin → Users.
2. **Campaign email is configurable in Admin → Settings → Email** (no hard-coded sender):
   from name, from address, reply-to, SMTP host/port/security/user/password (password stored encrypted),
   **daily send limit** and **per-minute throttle**, footer postal address, test-send button.
   The campaign dispatcher never exceeds the configured limits and carries the remainder to the next day.
   Multiple sender identities can be added later (same settings table, `is_default`).
3. **Shop inbox & campaigns move to the CRM — later.** The shop keeps its contact inbox and campaigns
   until CRM M5 (campaigns) and the inbox phase are live; then they are retired in the shop and the shop
   only emits events. Until then the CRM receives `contact_message.*` events read-only on the timeline.
4. **Starter lookups** (seeded as `lookup_values`, all editable/deactivatable in Admin → Settings → Types):

| Kind | Seed values |
|---|---|
| customer_type | Retail, Repeat, VIP, Wholesale, Marketplace (Etsy/Amazon) |
| supplier_type | Manufacturer, Raw materials, Packaging, Printing & labels, Shipping & logistics, Services |
| ticket_type | Order question, Shipping & delivery, Return / exchange, Damaged / defective, Custom request, Product question, Complaint, Other |
| ticket_priority | Low, Normal, High, Urgent |
| task_type | Call, Email, Follow-up, Meeting, To-do |
| lead_source | Website, Shop, Etsy, Amazon, Referral, Social media, Trade show, Other |
| lost_reason | Price, Timing, Chose competitor, No response, Not a fit, Other |

**Seed pipelines** (stages editable in Admin → Settings → Pipelines):
- *Custom orders:* New inquiry (10%) → Quoted (30%) → Design approved (60%) → In production (90%) → Won / Lost
- *Wholesale* (inactive until B2B): Lead (10%) → Qualified (25%) → Sample sent (40%) → Proposal (60%) → Negotiation (80%) → Won / Lost

**Seed SLA policy** (business hours, editable): first response / resolution —
Urgent 2h / 1 day · High 4h / 2 days · Normal 1 business day / 3 days · Low 2 business days / 5 days.

### Still open (not blocking)
- Team members and their roles (entered in Admin → Users after M0).
- Business hours / holidays for SLA timers (default Mon–Fri 9:00–17:00 America/Chicago).
