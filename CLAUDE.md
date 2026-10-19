# CLAUDE.md — Windy City Wares CRM Portal

Context file for AI-assisted work on this repo. Read this first in every session.

## Where things live

| What | Location |
|---|---|
| Live URL (target) | https://crm.windycitywares.com (web) · https://crm-api.windycitywares.com (API) |
| GitHub repo | https://github.com/windycitywares/wcw-crm-portal (private, branch `main`) |
| Local folder (Windows) | `C:\Users\Maaz4\Documents\WindyCityWares\wcw-crm-portal` |
| Sister project (reference spec) | `windycitywares/wcw-shop-portal` → https://shop.windycitywares.com |
| Other org repos | `wcw-main-site` (windycitywares.com, public), `wcw-backups` |
| claude.ai Project | "www-crm-portal" |
| Business | Windy City Wares LLC — Etsy shop `WindyCityWaresUS` |

**Rule:** the CRM uses the **same tech stack and conventions as the shop portal**, but organises code
**module-per-feature** (see Layout). When in doubt, open `wcw-shop-portal` and copy its pattern
(auth, RBAC, email outbox, deployment).

**Full spec:** `docs/SPEC.md` — read it before building any module (decisions + seed types in §9).

## How to work (owner's rule, same as shop)

**Work in batches and open small PRs** — one layer or feature per PR, each green and safe to deploy
alone, pushed as soon as it's done. Never do a whole milestone in one shot (it exhausts the session).
See the shop's `docs/WORKING_IN_BATCHES.md` for the pattern.

## Scope (agreed 2026-10-16)

Internal CRM for the owner + team. v1 modules: **Customers** (+ customer types), **Sales** (leads,
deals, pipelines), **Tasks**, **Support tickets** (+ types, SLA), **Campaigns** (email templates,
target lists/segments, sending, tracking, suppression), **Suppliers** (+ supplier types), Reports.
Fed by the shop via signed webhooks + read API. **M8 (from 2026-10-17):** communication channels — the unified
inbox, arriving as tickets; live chat, Etsy and SMS are later channels on the same footing. **Later:** B2B
accounts UI, automation, AI.
Roles: Admin, Manager, Sales, Support, Marketing, Read-only (confirmed).
Campaign sender/SMTP/daily limits are **configurable in Admin → Settings**, not env-only.
Shop's inbox + campaigns move into the CRM **later** (after M5); until then the shop keeps them.
Types/pipelines/SLA seeded from SPEC §9, all editable in Admin.
Build order: M0 scaffold/auth → M1 shared blocks → M2 customers+shop sync → M3 tasks+tickets →
M4 sales → M5 campaigns → M6 suppliers → M7 reports → M8 communication channels (unified inbox).

## Tech stack (inherited from shop.windycitywares.com)

- **Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS v4
  - Headless accessible components (Radix UI / shadcn/ui) styled with Tailwind
  - Template layout: `src/app/layout.tsx` = Header / `<main>` / Footer (or Sidebar for CRM); tokens in `src/app/globals.css`
  - Primitives in `src/components/ui/`
  - `src/lib/api.ts` server-side fetches · `src/lib/client-api.ts` browser fetches with JWT
- **Backend:** Python 3.11+, FastAPI (async, strictly typed, REST JSON API)
  - SQLAlchemy 2 async + asyncpg, Alembic migrations
  - Layers inside each module: models · schemas · repository (DB queries only) · service (business rules) · router (thin)
- **Database:** PostgreSQL 13 on the shop's HostItBro server — **no extensions** (no `ltree`/`pg_trgm`/`citext`);
  `JSONB` for custom fields, plain-text id paths ("1.4.9") for any hierarchy, like the shop
- **Auth:** JWT + bcrypt, permission-based RBAC (roles: Admin, Manager, Sales, Support, Marketing, Read-only)
- **Hosting:** HostItBro cPanel shared hosting (Python 3.11, Node 20/22)
  - Backend via Passenger; entry point `backend/wsgi.py` (never commit `passenger_wsgi.py`)
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
  integrations/  signing.py (the signature every signed caller shares) · shop/ (webhooks in, read API out) ·
                 email/ (SMTP sender, the mailbox reader) · files/ (the bytes customers send, on the server's
                 own disk)
  workers/       cron jobs: outbox, campaign dispatch, SLA checks, shop sync
frontend/src/
  app/(auth)/ · app/(crm)/<module>/   (sidebar shell layout)
  modules/<module>/  components, hooks, api, types
  components/ui/     shared primitives: DataTable, EntityForm, Kanban, Timeline, …
docs/          SPEC.md, DEPLOYMENT.md, SHOP_EVENTS.md (shop → CRM webhook contract), INBOX_CHANNELS.md
               (the same contract for channels that aren't mailboxes)
```

## Deploy

Same server as the shop. Web → `~/apps/crm/wcw-crm-web` (Node 20, bundle from the `web-build` branch built by
Actions); API → `~/repos/wcw-crm-portal/backend` (Python app, `wsgi.py`) on `crm-api.windycitywares.com`;
DB `windycit_crm`. Cron runs `deploy/auto-deploy.sh` every 10 min: **merge to `main` → live in ~10 min**.
Full steps incl. the one-time clean-up of the old crm subdomain: `docs/DEPLOYMENT.md`.

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
- Routes stay thin; business rules go in the module's `service.py`, queries in its `repository.py`.
- Custom / variable data goes in `custom_fields JSONB`, not new columns.
- "Types" (customer, supplier, ticket, task, lead source, …) are rows in `lookup_values(kind, …)` —
  adding a type never needs a migration. Pipelines/stages have their own tables.
- A module never imports another module's repository; call its **service** or publish a domain event.
  Exception: every module may import `app.modules.users.deps` (`SessionDep`, `CurrentUser`, `require`).
- Record types that notes/tags/timeline/custom fields attach to are registered once with
  `register_entity(EntityType(...))` (`app/core/entities.py`); modules write timeline lines with
  `TimelineService(session).record(...)`.
- Record security-relevant and data changes with `AuditService(session).record(...)` in the same transaction.
- New module = new `modules/<name>/` package (`module = CrmModule(...)`) + one line in `INSTALLED_MODULES`
  (`app/modules/__init__.py`); nothing else edited.
- Every business table: timestamps, created_by/updated_by, soft delete (`deleted_at`), `owner_id` where relevant, audited.
- External services sit behind small interfaces (`EmailSender`, `ShopClient`, `TemplateRenderer`).
- Campaign templates render in a sandboxed Jinja2 env; unsubscribe link + suppression list are mandatory.
- Async ORM relationships are `lazy="raise"`; load explicitly with `selectinload(...)`.
- Schema changes: edit model → autogenerate Alembic revision → review.
- Frontend: data pages are Server Components using `src/lib/api.ts`; interactive/admin pages are
  client components using `apiFetch`.

## Status

- 2026-10-16: M0 live — https://crm.windycitywares.com (web) + https://crm-api.windycitywares.com (API), auto-deploy cron
  on the server. M1 and M2 done (customers, shop sync, import/export, merge); **M3 in progress — tasks done; tickets API, web, canned responses and
  tickets from the shop built (`feat/m3-3-tickets-api`, `feat/m3-4-tickets-web`, `feat/m3-4b-canned-responses`, `feat/m3-5-shop-contacts`); left: the shop
  emitting `contact_message.created` (shop repo). **M4 sales started — batches 1 (sales API) and 2 (sales web: deals board + list, Settings →
  Pipelines, deals panel on the customer, pipeline card on the dashboard) built (`feat/m4-1-sales-api`, `feat/m4-2-sales-web`); batch 3 (leads API:
  list/filters/summary, own-vs-any + handover, notes/timeline on a lead, convert to customer + deal in one transaction) built
  (`feat/m4-3-leads-api`); batch 3b (leads web: `/leads` with status tabs and counts, the status as a picker in each row, add/edit + convert
  dialogs, a Leads card on the dashboard and a sidebar entry) built (`feat/m4-3b-leads-web`); batch 4 (deal items API: `deal_items`, lines with quantity × price, the
  lines total beside the deal's own value, timeline + audit, own-vs-any) built (`feat/m4-4-deal-items-api`); batch 4b (deal items web: the products panel in the
  deal dialog — add/edit/remove a line, the lines total next to the deal value with a one-click "use it") built (`feat/m4-4b-deal-items-web`). **M5 campaigns started —
  batch 1 (campaigns API foundation: `email_templates` with merge fields rendered in a sandboxed Jinja2 environment, a save-time render check, preview and test send
  through the outbox, `version` + audit; `suppressions` (soft-deleted, re-adding restores the row) and signed unsubscribe links) built (`feat/m5-1-campaigns-api`);
  batch 2 (campaigns API: target lists — the audiences a campaign goes to; members added in bulk, searched and paged, `members` and `reachable` counts, and
  memberships following a customer delete or merge) built (`feat/m5-2-target-lists`); batch 2b (segments: a dynamic audience as the same `target_lists` row with
  `kind="segment"` and `rules` — a closed rule vocabulary over customer type, source, status, tags, owner, orders, spend, last/created date and consent, validated on
  save and on read, compiled to a customer query so the audience is always current; the "who matches" view is `GET .../members` and `GET /campaigns/segment-fields`
  describes the vocabulary for the rule builder) built (`feat/m5-2b-segments`); batch 3 (campaigns + the sender: `campaigns` + `campaign_recipients` (migration
  0020); starting one copies its audience into recipient rows once — a segment evaluated at that moment — and the `campaigns` job queues one personalized message
  per recipient into the outbox, only as many at a time as its SMTP limits have room for, copying back sent/failed; who is skipped is decided at send time
  (`_why_not_reachable`) with the reason kept on their row; draft → scheduled → sending → paused → sent, with schedule/send/pause/resume behind `campaigns:send`;
  the public unsubscribe link as the first `public_router` — a GET that changes nothing and a POST that acts, both rate-limited) built
  (`feat/m5-3-campaigns-sender`); next: tracking + the per-campaign report, then the campaigns web.
  Still open from M4: the shop catalog picker (4c — needs a `products` resource on
  the shop's read API). Shop connection needs `CRM_WEBHOOK_URL`/`CRM_WEBHOOK_SECRET`/`CRM_API_TOKEN` on the shop server (shop docs/CRM_SYNC.md) — batch plan and PR status in `docs/WORKING_IN_BATCHES.md`.
- 2026-10-17: **M5 campaigns complete** — batch 4 (tracking + report: `campaign_events` with one row per recipient/kind/URL so counts are people, not
  requests; an open pixel, a click redirect whose destination is signed inside the token, a per-campaign report, campaign stats on the dashboard, and sends on
  the customer timeline) merged (#43–#45); batch 5 (campaigns web: `/campaigns` list + builder, template editor with merge fields, live preview and test send,
  list and segment builders, CSV audience import, Settings → Templates and the suppression screen, sidebar entry) merged (#46–#48 and #50), with the
  template-workflow polish still on `feat/m5-5d-template-workflow`. **M6 suppliers started** — batch 1 (supplier directory + contacts API, migration 0022)
  merged (#51); batch 2 (supplied products API) and batch 3 (supplier directory web) built on `feat/m6-2-supplier-products` / `feat/m6-3-suppliers-web`.
  **M7 reports** — batch 1 (cross-module reports API: `/reports/overview`, `/reports/customers`, `/reports/tickets`, `/reports/suppliers`) merged (#54);
  batch 2 (reports web: sales forecast, ticket/SLA, campaign performance, customer mix, supplier summary and CSV export) merged (#55) — the last batch in the plan.
- 2026-10-17: **post-v1 campaign-mail follow-ups started** (v1 is done; `docs/SPEC.md` §3.9 keeps everything else out of scope for now). Follow-up 1 fixes a
  shipped bug found while starting follow-up 2: the campaign sender rendered every real message **without a `recipient_id`**, so no open pixel and no wrapped
  links ever went out and `campaign_events` stayed empty — the tracking endpoints all worked, and the tests minted their own tokens, so nothing caught it. The
  fix is one argument in `_queue`, plus a regression test that follows the open and click links **out of the message that was actually sent** and then reads
  the report. Built on `fix/campaign-tracking-links`. Follow-up 2 adds the `List-Unsubscribe` and
  `List-Unsubscribe-Post: …=One-Click` headers to campaign mail, and the body-less `POST /campaigns/unsubscribe/one-click` a mail client posts to on the reader's
  behalf (a `GET` on the same address sends a human on to the web app's page instead, changing nothing); built on `feat/m5-6-one-click-unsubscribe`. Follow-up 3
  turned out to be a decision rather than work and is settled: a test send stays a preview of the words, with neither the tracking links (there is no recipient
  to attribute an open or a click to, and a made-up one would land in that campaign's own report) nor the header.
- 2026-10-17: **M8 communication channels (unified inbox) started** — SPEC §3.9's first item after v1, and §9 decision 3 makes "the inbox phase" the last thing
  the shop's own inbox and campaigns wait on. The design keeps the CRM's habit that **a conversation is a ticket** (the shop's contact form already opens one), so
  the inbox is channels arriving into tickets — one place to work with SLA, assignment and permissions already in it — not a second conversation store. Batch 1
  (migration 0024) gives a ticket a `channel`: a `ticket_channel` lookup (Email, Shop form, Phone, Live chat, Etsy, Manual), `manual` for everything already in
  the table, `shop_form` from the shop handler, validated like the other type lists, filterable in `GET /tickets?channel=`, audited, re-fileable by staff, and
  shown in the web queue (column + filter), the ticket dialog and the ticket page. Built on `feat/m8-1-ticket-channels`. Batch 2 (migration 0025) adds the
  mailboxes the CRM reads: a new `inbox` module whose `email_accounts` row holds the host, port, security, folder and username (empty = the mailbox's own
  address) plus a password encrypted with `DATA_ENCRYPTION_KEY` and never returned by the API (a blank password in a patch keeps the stored one), CRUD behind a new
  `inbox:manage` permission (manager and admin — support works the queue, not the credentials), and `POST /inbox/accounts/{id}/test`, which opens the mailbox now
  and answers with the folder, message count and unread count or the server's own error. Reading sits behind one `InboundMailbox` interface — a stdlib `imaplib`
  implementation (in a thread, `readonly`, so testing marks nothing read) and a factory tests stand in for. A mailbox is deleted for real, so a password never
  outlives the setup. Built on `feat/m8-2-inbox-mailboxes`, which sits on batch 1. Batch 3 (migration 0026) is **email in**: the `inbox` job (once a minute,
  registered in the module) polls each enabled mailbox, takes its unread mail oldest-first (50 a run), parses it and opens or continues a ticket — deduplicated by
  the email's own `Message-ID` on `ticket_messages.external_id` (unique, so a re-poll or a crash between storing and marking read can't double a message), threaded
  by `In-Reply-To`/`References` (newest first) and, if the client lost the headers, by the `[T-000123]` token in the subject. The sender matches a customer on any of
  their addresses (`by_any_email`: main or alt) and is created if unknown, the way the shop does it; a message with no usable `From` is still filed so staff can link
  it later. A new ticket is channel `email`, type "Other", unassigned, `new`, and `created_at`/`opened_at` come from the mail's own `Date` so the SLA clock starts
  when the message arrived and not when we polled. A customer writing again reopens a ticket that was waiting or done with, and deliberately never touches the SLA
  clock. Our replies carry their own `Message-ID` plus `In-Reply-To`/`References`, so a customer's answer lands back in the same ticket (the SMTP sender honours a
  header-provided id, so a retry keeps it). `Auto-Submitted` mail and duplicates are skipped but marked read (a robot must not come back); spam is left for a later
  decision. One message that can't be filed doesn't stop the others (it stays unread to retry), one unreachable mailbox doesn't stop the others either, and both are
  written on the account as `last_polled_at`/`last_error` (cleared by a good poll). Built on `feat/m8-3-email-in`, which sits on batches 1–2. Batch 4 (no migration)
  is **the web half**: `GET /tickets?needs_reply=` answers the inbox's own question — the customer's message is the newest thing said, nobody having replied since —
  by looking at the newest `ticket_messages` direction, and when it is asked the list comes back oldest wait first (the order a shared inbox is worked in). The new
  `/inbox` page puts channel tabs (from the `ticket_channel` lookup), Waiting-on-us / Everything-open, search and paging beside the thread itself — notes, canned
  replies and email replies through the existing `Conversation`, with `?ticket=`/`?channel=` deep links and a way through to the full ticket for assigning and
  status. Settings → Email accounts (`inbox:manage`) lists the mailboxes with their last-read health and lets an admin add, test, pause and remove one. `Segmented`
  moved into `components/ui` and is now the single filter control (queue, inbox, note-or-reply). Built on `feat/m8-4-inbox-web`, which sits on batches 1–3. Batch 5
  (migration 0027) keeps **the files a customer sends**: `attachments` is polymorphic on `(entity_type, entity_id)` exactly as `notes` and `activities` are, so a
  file hangs on any registered record and the existing `check_entity_access` decides who may reach it — reading takes the record's *view* right, dropping one takes
  its *edit* right, and **no new permission** was added. It is inbound only: the `inbox` job keeps what arrived on the mailbox (up to 10 files of 15 MB each per
  message) against the ticket the message belongs to, and whatever it leaves behind is counted and said in the message body, because a ticket that quietly lost a
  customer's photos is worse than one that admits it. The bytes sit behind a `FileStore` seam in `app/integrations/files/` (a protocol, one `LocalFileStore`,
  `file_store()`/`set_store_factory` — the same shape as `mailbox_for`), named after the sha256 of their own content: the same file sent twice is stored once, two
  rows may share it, and the stored bytes are dropped with the last row that pointed at them (soft delete first, then a count). A filename that arrived with mail is
  display text only — flattened to one line, never a path, and the keys the store accepts are `^[0-9a-f]{64}$`. API: `GET /entities/{type}/{id}/attachments` (a
  plain list, oldest first), `GET /attachments/{id}` (always a download, ASCII `filename=` plus RFC 5987 `filename*=` so an accented name survives, `nosniff`), and
  `DELETE /attachments/{id}` (soft, audited `attachment.delete`, one timeline line). Web: an `Attachments` list under the ticket conversation on `/tickets/[id]`
  (and the inbox pane, which shows the same `Conversation`), with a confirm before removing and nothing rendered when there are no files. Storage is the server's
  own disk because the deployment is self-hosted: `attachments_dir` defaults to `~/apps/crm/wcw-crm-files`, **outside the checkout** so a deploy can't take a
  customer's photo with it, and created on first use. Deliberately deferred, and written down: staff uploads, outbound attachments (the reply is plain text through
  the one SMTP identity, so an attached file would not leave the building), virus scanning, and a "which message brought this?" link. Built on
  `feat/m8-5-attachments`, which sits on batches 1–4. Batch 6 is **the channels that aren't mailboxes** — chat, Etsy and SMS, whose CRM half is a door and a set of
  rules: `POST /inbox/messages` (the inbox module's `public.py`, no session — the HMAC signature is the authentication, and the scheme moved out of the shop's
  namespace into `app/integrations/signing.py` once two callers shared it) takes one signed message and files it through `filing.py`, the rules extracted out of the
  poller so that a chat and a letter cannot be filed differently: the sender found or created by address, threading by the ids the sender carried (or the `[T-000123]`
  in a subject), a new ticket or an answer joined to an existing one, the channel it arrived on written on the ticket, and its files kept against that ticket tagged
  with that channel. `InboxSettings` — a settings group whose secret is encrypted like the others — holds the switch and the `ingest_secret`, generated and copied in
  Admin → Settings → Integrations → *Messages from other channels*; a message that isn't signed, isn't JSON, names a channel the CRM doesn't have (checked against
  the `ticket_channel` lookup) or carries a file that isn't base64 is refused with a status the connector can read (400/401/413/429/503), and re-posting an id
  already stored answers `duplicate` instead of opening a second ticket. Extracting one set of rules also fixed what mail had been missing: the message that opens
  a ticket is now stored *in* the ticket and not only written on it as its description, which is what makes a ticket count as waiting on us and gives our reply
  something to answer, so the customer's next message finds its way back. No migration. The contract is `docs/INBOX_CHANNELS.md`. Built on `feat/m8-6-other-channels`,
  which sits on batches 1–5. Next: the connectors themselves (the shop's chat widget, an Etsy poller, an SMS gateway — the last needs a provider and credentials) and
  retiring the shop's inbox; matching a sender known only by phone is the other half of SMS. Plan of record: `docs/WORKING_IN_BATCHES.md`.

- 2026-10-18: **M8 batch 7 (phone-only sender matching)** — an SMS or a chat with no address still tells staff who wrote
  in: the message carries `from.phone`; the CRM matches it to an existing customer by digits (punctuation and NANP country
  code ignored) but **never creates a customer from a number alone** — a phone is shared and recycled, and a wrong record is
  harder to undo than an unlinked ticket. The number is stored on the message (`ticket_messages.from_phone`, migration 0028)
  so staff can see it and link the ticket by hand; an email always outranks a phone when both are present. Staff can also
  find the customer by pasting the whole number into the search box (digits ≥ 7) — the merge keeps only the kept record's
  phone (only live rows match). Pure tests (`test_text.py`) + intake/customers DB tests. Merged as #67 (M8 batches 1–6
  already in `main`). Next: the connectors themselves and retiring the shop's inbox.
- 2026-10-18: **code-quality pass** on the code M8 touched, on top of #67, on branch `chore/code-quality`, opened as **#68** (no
  behaviour is meant to change, but two real bugs turned up and were fixed). The custom-field validators in
  `customfields/types.py` are typed (`JsonValue`, a `FieldDef` protocol, a `Validator` TypedDict) rather than `Any`, and the
  11 per-module `_snapshot()` copies are now one `app/shared/snapshot.py`. **Bug 1:** `CustomFieldService.field_types()` still
  unpacked the old `(label, check)` tuple, so every custom-field type advertised the label `"label"` in the admin's picker.
  **Bug 2:** the shared `snapshot()` returned `Decimal`/`date`/`datetime` unchanged, but audit `changes` go into a JSONB column
  serialised with plain `json.dumps` (which cannot encode them) — sales/tasks used to stringify those fields locally, so the
  helper now makes every value JSON-safe, with a pure unit test. Also: `decode_access_token()` returns an `AccessTokenPayload`
  TypedDict; the inbound-mail parser debug-logs the parts/messages it skips instead of swallowing them silently; imports left
  unused by the earlier `utcnow()`/snapshot refactors are removed. 264 tests green (175 DB-gated).
- 2026-10-18: **CI green again** — `backend.yml`'s DB suite had not passed since M3 batch 1 (#27), so everything
  merged since was never executed. **#69** removed the one compile-time break (PEP 695 `def get_model[T]`: CI and
  the **server run Python 3.11**, which cannot parse it — local was newer). **#70** then repaired what the first
  run exposed. Real bugs: post-commit `updated_at` lazy-load (`MissingGreenlet` 500) on deal-item / SLA-policy /
  canned-response / supplier-contact / supplier-product updates (they now `refresh()` after commit, the pattern
  tags/lookups/notes already used); a customer created with `marketing_consent=false` wrongly stamped
  `unsubscribed_at` (only true → false is an unsubscribe); lead convert lost the default pipeline's first stage;
  an attachment download gained `; charset=utf-8` on `text/*`; audit `changes` for a campaign's `scheduled_at`
  (a datetime) and a product's money columns (Decimals) were not JSON, so scheduling and product edits 500'd;
  **and `record_event` never committed, so every open pixel and every click was rolled back and the tracking
  report read 0 in production.** Stale tests: the inbox patch target, campaign helpers tag customers as an
  **admin** (marketing may only *view* them, SPEC §2), a per-class name counter, the unsubscribe-token regex
  kept the `:`, `<p>`-derived text keeps its blank line, the first *active* supplier type, the shop suite's SLA
  setup, `follow_redirects` (httpx spelling), passing a token not a URL, a `tags` rule takes ids, "spent ≤ 20"
  includes a never-ordered customer (spend defaults to 0), dashboard stats count the whole window, and `setUp`
  ends campaigns a test left mid-flight (the dispatcher works over the whole database). **264 tests, OK
  (2 skipped)** — the first green DB run since #27. CI runs 3.11; a syntax the local interpreter accepts can
  still fail there.
- 2026-10-18: **M8 batch 8 (staff uploads)** — the other half of attachments: a member of staff can now put a file on a record
  (`POST /entities/{type}/{id}/attachments`, multipart, one file). It takes the record's own *edit* right, exactly as dropping
  one does — **no new permission** — and runs the same rules as the inbox (`safe_name`, `clean_type`, `MAX_BYTES`, the same
  bytes kept once). An upload has no message to explain it, so it is written to the audit log (`attachment.upload`) and the
  record's timeline (`attachment.added`). Web: an **Add file** button in the `Attachments` panel, shown to whoever may change
  the record even when it holds no files yet; a reader with nothing to look at still sees nothing. No migration. Built on
  `feat/m8-8-staff-uploads`. Next: the connectors themselves and retiring the shop's inbox.
- 2026-10-19: **the web build is green again** — `web.yml` had been red since at least 2026-10-17, and not because of any
  code: `frontend/package-lock.json` had been regenerated on Windows and listed only the win32 optional binaries
  (`@next/swc-win32-x64-msvc`, `@tailwindcss/oxide-win32-x64-msvc`, `lightningcss-win32-x64-msvc`), so `npm install` on
  the Linux runner never fetched `lightningcss-linux-x64-gnu` and `next build` died evaluating `globals.css`
  (`Cannot find module '../lightningcss.linux-x64-gnu.node'`). **#73** regenerates the lockfile with `node_modules` out
  of the way (npm otherwise prunes it to the installed tree, which is how the other platforms were lost) so every
  platform's package is listed — only postcss moved (8.5.30 → 8.5.31). Both workflows are green on `main` after #72/#73.
- 2026-10-19: **M8 batch 9 (which message brought a file)** — a file the inbox filed now says which message carried
  it: `attachments.message_id` (migration 0030, nullable, a plain id — no cross-module foreign key) is set by
  `MessageFiler` from the id `TicketService.add_inbound` returns, so a file on an *answer* points at the answer, not at
  the message that opened the ticket; a file a member of staff added (batch 8) has none. The id rides along on the
  attachments API, and the `Attachments` panel names the moment and links to the message in the thread (`#message-<id>`;
  the conversation now renders each message with that id). No new permission, no new endpoint. Built on
  `feat/m8-9-which-message`. Next: the connectors themselves and retiring the shop's inbox.
- Claude merges green PRs (owner's standing OK) but can't create server secrets/cron; ask the owner.
