# Working in batches (small PRs)

Owner's rule, same as the shop: **work in batches and open small PRs** — never the whole milestone in one shot.

1. One batch = one focused PR (one layer or feature area, ideally < ~1,500 changed lines).
2. Every PR is green in CI and safe to deploy on its own.
3. Commit and push early; open the PR as soon as the batch is done.
4. Base on `main` when possible; if a batch needs the previous one, say "Depends on #N" and merge in order.
5. After each PR: a short status to the owner, then the next batch.
6. Keep the plan below current so a new session can pick up the next batch.

Branch `feat/<area>-<n>-<short-name>` · PR title `<Area> <n>/<total>: <what it does>`.

## Plan — M0 Foundation

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Backend core | config, db, security (JWT, bcrypt, encrypted secrets), permissions map (6 roles), exceptions, event bus, pagination, base model mixins, generic repository, module registry, wsgi adapter, Alembic, CI | #1 merged |
| 2 | Users & auth | users module: model + migration, login, me, password reset, users admin API, seed admin, audit log | #2 merged |
| 3 | Frontend shell | Next.js app, login, sidebar shell (menu by permission), users admin page, CI build + bundle branch | #3 merged |
| 4 | Deploy | deploy scripts (auto-deploy cron, update API/web), DEPLOYMENT.md incl. clean-up of the old crm subdomain | #4 merged (+ #5–#7 setup fixes) |

## Plan — M1 Shared building blocks (started 2026-10-16)

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Lookups | `lookups` module: admin-editable type lists (`lookup_values`), kind registry, seed from SPEC §9, module seed hook, API + tests | #8 merged |
| 2 | Tags, notes, timeline | `tags` + `taggings`, `notes`, `activities` (polymorphic `entity_type/entity_id`), shared services other modules call; `core/entities.py` registry; API + tests | #9 merged |
| 3 | Custom fields | `custom_field_defs` per entity (text, number, date, select, checkbox), validation service for `custom_fields JSONB`; API + tests | #10 merged |
| 4a | Settings | `settings` module: typed groups (Email: SMTP + encrypted password, sender, daily limit, per-minute throttle, footer address; Business hours), test-send endpoint; API + tests | #11 merged |
| 4b | Email outbox + jobs | `email_outbox` table, `OutboxEmailSender` (queue + send now when possible, SMTP from Settings, limits), `app/workers/run_jobs.py` (retries, advisory lock) + `deploy/run-jobs.sh` called by auto-deploy; password reset goes through it | #12 merged |
| 5a | Web: types, tags, custom fields | Settings → Types (per list: add, rename, colour, activate, reorder), Tags (search, edit, delete), Custom fields (per record type) | #13 merged |
| 5b | Web: email + business hours | Settings → Email (SMTP, password kept when blank, limits, test send), Business hours | #14 merged |
| 6 | Web: record components | `modules/records`: `NotesPanel`, `Timeline`, `TagEditor`, `CustomFieldsEditor`/`CustomFieldsView`, `useDirectory`; API `GET /users/directory` (names for everyone) | #15 merged (all of M1 reached main via #16) |

Also shipped: Admin → Deployments (#18: deploy now, pause, schedule, log) and web-deploy fixes (#17, #19).

## Plan — M2 Customers + shop sync (started 2026-10-16, done 2026-10-16)

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Customers API | `customers` module: model (name, company, email/phones, type, status, source, owner, consent, address, shop link + order stats, custom fields), registered record type, list/search/filter/sort, create (duplicate-email check), edit (own vs any), soft delete/restore, timeline + audit; tests | #20 merged |
| 2 | Customers web | list page (search, filters, columns, tags), customer page (details, tags, custom fields, notes, timeline), create/edit form | #21 merged |
| 3 | Shop → CRM events | `integrations/shop`: signed webhook endpoint, `shop_events` (idempotent) + `shop_orders` copies, handlers for customer/order/newsletter events → upsert customer, order stats, timeline; Settings → Integrations (shared secret, shop API URL/token) | #22 merged |
| 4 | Shop side (wcw-shop-portal) | shop emits signed events to the CRM from its outbox + read-only API token for the CRM — PR in the shop repo, following its batch rules | shop #67 merged (events), #68 (read API) |
| 5 | Backfill + order history | job that imports existing shop customers/orders via the shop API; customer page shows order history (from `shop_orders`); Integrations → Test connection + Import (chunked `shop-backfill` job, migration 0010) | #23 merged |
| 6a | Import/export | CSV/Excel export (list filters, formula-safe) and import (column matching, dry run, skip/update, row errors, tags) for `data:export` | #24 merged |
| 6b | Merge duplicates | merge two customers (keep one, move notes/tags/timeline/orders, audit); generic `RecordsMerged` event that shared modules subscribe to | #25 merged |

## M3 Tasks + support tickets (started 2026-10-16)

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Tasks API | `tasks` module (migration 0011): type/priority/status/due/assignee, about any record (timeline lines), own/any/assign rules, views mine/team/created + due filters, recurring (next made on completion), email reminders job, summary counts; `EntityType.labels` for record names | #27 merged |
| 2 | Tasks web | Tasks page (my/team, overdue/today/week tabs, quick add, complete checkbox, edit dialog), Tasks panel on the customer page, Your tasks on the dashboard | open |
| 3 | Tickets API | `tickets` + `ticket_messages` + `sla_policies` (seeded §9): numbering, New→Open→Pending→Resolved→Closed, assign, internal notes vs email replies (outbox), SLA due times in business hours + breach job, timeline on the customer | — |
| 4 | Tickets web | queue (filters, SLA badges), ticket page (conversation, reply / internal note, status, assign), Settings → SLA policies, canned responses | — |
| 5 | Tickets from the shop | shop contact-form messages → tickets (shop event + CRM handler) | — |

## Next milestones
M3 tasks + tickets → M4 sales → M5 campaigns → M6 suppliers → M7 reports.
