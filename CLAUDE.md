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

**Rule:** the CRM uses the **same tech stack, architecture and conventions as the shop portal**.
When in doubt, open `wcw-shop-portal` and copy its pattern (folder layout, auth, RBAC, deployment).

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
- **Auth:** JWT + bcrypt, permission-based RBAC (Admin / Publisher / Author / User in the shop — CRM roles TBD)
- **Hosting:** cPanel shared hosting
  - Backend via Passenger (ASGI/WSGI) on cPanel
  - Frontend via Next.js `output: 'standalone'` Node server (or `output: 'export'` if static only)
  - Standard PostgreSQL connection string
- **Quality bar:** OOP / SOLID, easy to maintain & upgrade, WCAG 2.1 AA (labels on every control, `focus-visible` styles)

## Planned layout (mirror the shop)

```
backend/    FastAPI app (app/core, models, schemas, repositories, services, api/v1), migrations/, tests/
frontend/   Next.js app (src/app, src/components/{ui,layout,...}, src/lib)
docs/       SPEC.md (CRM spec), DEPLOYMENT.md (cPanel steps)
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
- Custom / variable data goes in `JSONB` columns, not new columns.
- Async ORM relationships are `lazy="raise"`; load explicitly with `selectinload(...)`.
- Schema changes: edit model → autogenerate Alembic revision → review.
- Frontend: data pages are Server Components using `src/lib/api.ts`; interactive/admin pages are
  client components using `apiFetch`.

## Status

- 2026-10-16: repo created and pushed (`main` is default). Contains only `README.md` + `CLAUDE.md`.
  CRM-specific spec (`docs/SPEC.md`: modules, roles, data model) not written yet — define it before scaffolding.
