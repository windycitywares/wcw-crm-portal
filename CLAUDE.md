# CLAUDE.md — Windy City Wares CRM Portal

Context file for AI-assisted work on this repo. Read this first in every session.

## Where things live

| What | Location |
|---|---|
| Live URL (target) | https://crm.windycitywares.com |
| GitHub repo | https://github.com/windycitywares/wcw-crm-portal (private, branch `main`) |
| Local folder (Windows) | `C:\Users\Maaz4\Documents\WindyCityWares\wcw-crm-portal` |
| Sister project (reference spec) | `windycitywares/wcw-shop-portal` → https://shop.windycitywares.com |
| Other org repos | `wcw-main-site` (windycitywares.com, public), `wcw-backups` |
| claude.ai Project | "www-crm-portal" |
| Business | Windy City Wares LLC — Etsy shop `WindyCityWaresUS` |

**Rule:** the CRM uses the **same tech stack and conventions as the shop portal**, but organises code
**module-per-feature** (see Layout). When in doubt, open `wcw-shop-portal` and copy its pattern
(auth, RBAC, email outbox, deployment).

**Full spec:** `docs/SPEC.md` — read it before building any module.

## Scope (agreed 2026-10-16)

Internal CRM for the owner + team. v1 modules: **Customers** (+ customer types), **Sales** (leads,
deals, pipelines), **Tasks**, **Support tickets** (+ types, SLA), **Campaigns** (email templates,
target lists/segments, sending, tracking, suppression), **Suppliers** (+ supplier types), Reports.
Fed by the shop via signed webhooks + read API. **Later:** B2B accounts UI, communication channels
(unified inbox, live chat, Etsy, SMS), automation, AI.
Roles: Admin, Manager, Sales, Support, Marketing, Read-only.
Build order: M0 scaffold/auth → M1 shared blocks → M2 customers+shop sync → M3 tasks+tickets →
M4 sales → M5 campaigns → M6 suppliers → M7 reports.

## Tech stack (inherited from shop.windycitywares.com)

- **Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS v4
  - Headless accessible components (Radix UI / shadcn/ui) styled with Tailwind
  - Template layout: `src/app/layout.tsx` = Header / `<main>` / Footer (or Sidebar for CRM); tokens in `src/app/globals.css`
  - Primitives in `src/components/ui/`
  - `src/lib/api.ts` server-side fetches · `src/lib/client-api.ts` browser fetches with JWT
- **Backend:** Python 3.11+, FastAPI (async, strictly typed, REST JSON API)
  - SQLAlchemy 2 async + asyncpg, Alembic migrations
  - Layers: `app/core/` (config, db, enums, permissions, security) · `app/models/` · `app/schemas/` ·
    `app/repositories/` (DB queries only) · `app/services/` (business rules) · `app/api/v1/` (thin routers)
- **Database:** PostgreSQL (`JSONB` for dynamic/custom fields, `ltree` where hierarchy is needed)
- **Auth:** JWT + bcrypt, permission-based RBAC (roles: Admin, Manager, Sales, Support, Marketing, Read-only)
- **Hosting:** cPanel shared hosting
  - Backend via Passenger (ASGI/WSGI) on cPanel
  - Frontend via Next.js `output: 'standalone'` Node server (or `output: 'export'` if static only)
  - Standard PostgreSQL connection string
- **Quality bar:** OOP / SOLID, easy to maintain & upgrade, WCAG 2.1 AA (labels on every control, `focus-visible` styles)

## Layout (module-per-feature, SOLID)

```
backend/app/
  core/          config, db, security, permissions, exceptions, event bus, pagination
  shared/        base mixins/repository/service, lookups, tags, notes, attachments,
                 custom fields, audit, timeline, import/export
  modules/<name>/  models.py schemas.py repository.py service.py router.py permissions.py events.py
                 (customers, sales, tasks, tickets, campaigns, suppliers, reports, users)
  integrations/  shop/ (webhooks in, read API out) · email/ (SMTP sender, template renderer)
  workers/       cron jobs: outbox, campaign dispatch, SLA checks, shop sync
frontend/src/
  app/(auth)/ · app/(crm)/<module>/   (sidebar shell layout)
  modules/<module>/  components, hooks, api, types
  components/ui/     shared primitives: DataTable, EntityForm, Kanban, Timeline, …
docs/          SPEC.md, DEPLOYMENT.md
```

## Commands (same as shop)

```bash
# backend (from backend/, venv active)
uvicorn app.main:app --reload
alembic upgrade head
alembic revision --autogenerate -m "..."   # after model changes; review the file
python -m app.seed
python -m unittest discover tests

# frontend (from frontend/)
npm run dev
npm run build
npm run typecheck
```

## Conventions (carried over from the shop)

- Routes depend on **permissions**, never role names: `Depends(require(Permission.X))`.
- Routes stay thin; business rules go in `app/services/`, queries in `app/repositories/`.
- Custom / variable data goes in `custom_fields JSONB`, not new columns.
- "Types" (customer, supplier, ticket, task, lead source, …) are rows in `lookup_values(kind, …)` —
  adding a type never needs a migration. Pipelines/stages have their own tables.
- A module never imports another module's repository; call its **service** or publish a domain event.
- New module = new `modules/<name>/` package + register its router in `main.py`; nothing else edited.
- Every business table: timestamps, created_by/updated_by, soft delete (`deleted_at`), `owner_id` where relevant, audited.
- External services sit behind small interfaces (`EmailSender`, `ShopClient`, `TemplateRenderer`).
- Campaign templates render in a sandboxed Jinja2 env; unsubscribe link + suppression list are mandatory.
- Async ORM relationships are `lazy="raise"`; load explicitly with `selectinload(...)`.
- Schema changes: edit model → autogenerate Alembic revision → review.
- Frontend: data pages are Server Components using `src/lib/api.ts`; interactive/admin pages are
  client components using `apiFetch`.

## Status

- 2026-10-16: repo created; scope agreed and written to `docs/SPEC.md`. No code yet — next is **M0**
  (scaffold, auth, roles/permissions, app shell). Open questions listed in SPEC §9.
