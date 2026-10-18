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
| 2 | Tasks web | Tasks page (my/team, overdue/today/week tabs, quick add, complete checkbox, edit dialog), Tasks panel on the customer page, Your tasks on the dashboard | #28 merged |
| 3 | Tickets API | `tickets` + `ticket_messages` + `sla_policies` (seeded §9): numbering, New→Open→Pending→Resolved→Closed, assign, internal notes vs email replies (outbox), SLA due times in business hours + breach job, timeline on the customer | #29 merged |
| 4 | Tickets web | queue (filters, SLA badges), ticket page (conversation, reply / internal note, status, assign), Tickets panel on the customer page, Settings → SLA policies | #30 merged |
| 4b | Canned responses | `canned_responses` table + CRUD (admins), picker in the reply box | #31 merged |
| 5 | Tickets from the shop | shop contact-form messages → tickets (shop event + CRM handler) | #32 merged |
| 5b | Shop side: contact form | the shop emits `contact_message.created` from its outbox when the contact form is submitted (PR in `wcw-shop-portal`) | — |

## M4 Sales (started 2026-10-17)

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Sales API | `sales` module (migration 0014): `pipelines` + `pipeline_stages` (boards + stage order, probability, won/lost column, colour; admin via `lookups:manage`) and `deals` (title, customer, stage, value/currency, probability, expected close, owner, source/lost_reason lookups, custom fields); own-vs-any + assign; **the stage decides the outcome** (dropping a card on the won/lost column wins or loses it) and sets the deal's default probability; `GET /sales/board` (kanban) + `GET /sales/summary` (open value, weighted forecast, won/lost this month); customer timeline; starter "Sales" board seeded once; delete guards (no orphaning open deals); registered `deal` record type; tests | #33 merged |
| 2 | Sales web | `/sales`: board view (kanban, one column per stage, drag a card to another column — landing on the won/lost column wins or loses the deal) and list view (whose/status/pipeline filters, search, paged, soonest to close first), new/edit deal dialog (stage picker that follows the pipeline, customer picker, value + currency, close date, owner, source, lost reason), Sales panel on the customer page, pipeline value + weighted forecast on the dashboard, Settings → Pipelines (add/rename/delete boards and stages, reorder, probability, won/lost, colour) | #34 merged |
| 3 | Leads API | `leads` module (migration 0015): contact (name/company/email/phone), `source` lookup, status new→contacted→qualified→unqualified, owner, notes, custom fields, soft delete; own-vs-any + handover; list (view/status/source/search) + summary counts; **`POST /leads/{id}/convert`** makes the customer (or reuses the one with that email, or the `customer_id` given) and, unless `create_deal=false`, opens its first deal — one transaction, links `converted_customer_id`/`converted_deal_id`, refuses a second conversion and a hand-set `converted` status; registered `lead` record type (notes/tags/timeline); tests | #35 merged |
| 3b | Leads web | `/leads`: status tabs with counts (all / new / contacted / qualified / unqualified / converted), whose-are-they + source filters, search, paged list; add/edit dialog (name, company, email, phone, source, status, owner, notes; delete); **the status is a picker right in the row**; convert dialog — pick the customer or let it match by email / make one from the lead, deal title, stage, value + close date, "open a deal" toggle (off when there is no pipeline yet); converted rows link to the customer and the deal; Leads card on the dashboard, sidebar entry | #36 merged |
| 4 | Deal items API | `deal_items` (migration 0016): the products on a deal — name, SKU, `shop_product_id`, quantity (may be fractional), unit price, position; `total` = quantity × unit price; soft delete, audited, a timeline line on the deal and its customer. `GET/POST /sales/deals/{id}/items`, `PATCH/DELETE /sales/deals/{id}/items/{item}`. The lines total is returned next to the deal's own value and never overwrites it; the lines follow the deal's own-vs-any rule; a null field in a patch means "not changing it". Lines typed in by hand (the shop catalog picker is 4c); tests | #37 merged |
| 4b | Deal items web | the products panel in the deal dialog (which is what the board, the list and the customer page all open): add a line (product, SKU, quantity, unit price), edit it where it sits (Enter saves), remove it, the lines total next to the deal value, "use $X as the deal value" when the two differ, and read-only for a deal you can't change; a new deal says to save it first | #38 merged |
| 4c | Shop catalog picker | search the shop catalog when adding a line (`shop_product_id` + SKU come across); **blocked on the shop repo** adding a `products` resource to its read API (`/integrations/crm/products`, shop docs/CRM_SYNC.md) — the CRM side is a small picker once that lands | — |

## M5 Campaigns (started 2026-10-17)

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Campaigns API: templates + suppression | `campaigns` module (migration 0017): `email_templates` (name, subject, preheader, HTML + text body; `version` goes up on every save and the audit log keeps what changed) written with merge fields (`{{ customer.first_name }}`, `{{ unsubscribe_url }}`, …) and rendered through a **sandboxed** Jinja2 environment (`StrictUndefined`: a misspelled field is an error, not a blank). A template is rendered with sample data when it is saved, so a typo comes back as 422 at the desk; an empty text body is derived from the HTML. `GET /campaigns/templates/{id}/preview` (a real customer or the sample) and `.../test` (sent through the outbox, so the SMTP limits and retries apply). Every rendered message gets the compliance footer: the `footer_address` from Admin → Settings → Email and the customer's own **signed** unsubscribe link (`tokens.py`, HMAC with the app secret — works without a login). `suppressions` (unsubscribed / bounced / complained / manual; soft-deleted, so re-adding an address restores its row and its history) with `GET/POST /campaigns/suppressions` and `DELETE` to release, plus the `suppressed()` lookup the sender will use. `GET /campaigns/merge-fields` for the editor. `campaigns:view` / `campaigns:edit` / `campaigns:send`; tests | merged in #40 (chained) |
| 2 | Campaigns API: target lists | `target_lists` + `target_list_members` (migration 0018): the audiences a campaign goes to. A list is a name, a description and a kind (`static` in this batch — the column is there because a segment is the same thing to a campaign and to the UI, and it arrives as batch 2b). Members are customers, unique per list, added in bulk (`POST /campaigns/lists/{id}/members` takes up to 500 ids and reports `added` / `already` / `missing` / `total`), removed one at a time (audited one row per customer, so "who put them on this list?" is answerable), searched by name/company/email, and paged. Every list row carries two numbers: `members` (live customers on it) and `reachable` — the ones a campaign could actually email: an address, consent, no unsubscribe and not on the suppression list — so a list tells you what it is worth before it is used. Removing a customer from the CRM takes their memberships with them; merging two customers moves them to the one that stayed (`merge.py`, on M2's merge event). CSV import comes with the web batch | #40 merged |
| 2b | Segments | dynamic audiences (migration 0019): the same `target_lists` row with `kind="segment"` and `rules` in JSON — a small, **closed** query builder (`segments.py`) over customer type, source, status, tags, owner, orders placed, total spent, last/created date and marketing consent, each with its own ops ("has any of", "is at least", "in the last … days", "never", …) and `match: all|any`. Closed on purpose: a field maps to a column, an op to a comparison, and no part of a rule ever reaches SQL as text; a rule set is validated when it is saved (422 in the API) *and* when it is read, so a rule a later release no longer understands fails loudly instead of becoming a wild query. A segment has no member rows — it is counted, listed and (batch 3) sent to by running the query, so it is always current: a customer who stops matching falls out of it by themselves and nobody has to be added. `GET /campaigns/lists/{id}` reports `members`/`reachable` for a segment exactly as for a static list, `GET .../members` is the "who matches right now" preview (`added_at: null`), and `GET /campaigns/segment-fields` describes the vocabulary for the rule builder. `POST`/`DELETE .../members` are refused for a segment (rewriting the rules is how it changes) and a static list refuses rules. The consent/reachability rule moved to `consent.py`, so the static counts, a segment's query and batch 3's sender share one definition | #41 merged |
| 3 | Campaigns + sending | `campaigns` + `campaign_recipients` (migration 0020): a campaign is a name, a template, an audience and a time, and its status runs draft → scheduled → sending → paused → sent. **Starting it copies the audience into recipient rows there and then** (`INSERT … SELECT … ON CONFLICT DO NOTHING`, so a segment is evaluated once at that moment and a rerun adds only what is new), and from then on the `campaigns` job (every minute) queues **one personalized message per recipient** into the existing `email_outbox` — never more than the outbox has room for (`MailService.room`), so no message ever waits long enough for the outbox to give up on it — and copies back what happened (`UPDATE … FROM email_outbox`: queued → sent with the time, or failed with the reason). Who is skipped is decided at send time by the same rule the audience counts use (`_why_not_reachable` in `service.py`: customer deleted / no address / unsubscribed / suppressed / no marketing consent) and the reason is kept on the recipient's row; while email is off the job queues nothing and says so in its log line. `POST /campaigns` writes a draft (`campaigns:edit`), while `…/schedule` (a future time), `…/unschedule`, `…/send` (refused when the audience is empty), `…/pause`, `…/resume` and the unsubscribe write need `campaigns:send`; the template and audience of a campaign that has started are part of what went out, so they are frozen. The **public** side lives in `public.py`: `GET /campaigns/unsubscribe?token=…` answers who the link is for and changes nothing (a mail scanner following links cannot unsubscribe anyone), `POST /campaigns/unsubscribe` turns consent off, suppresses the address and writes down which campaign it came from — no session (the signed token is the proof) but rate-limited per IP; the first `public_router` in `CrmModule`, mounted by `main.py` under the same prefix without the module's permission guard. `GET /campaigns/{id}/recipients` (status filter, search, counts) is the report batch 4 builds on; tests | #42 merged |
| 4 | Tracking + report | delivered / opened (pixel) / clicked (redirect) / unsubscribed per campaign (`campaign_events`), a per-campaign report, campaign stats on the dashboard, sends on the customer timeline | #43–#45 merged — but the sender did not actually put the links in the mail until post-v1 follow-up 1 below |
| 5 | Campaigns web | `/campaigns`: list + report, campaign builder (template, audience, schedule), template editor with the merge-field picker, live preview and test send, Settings → Templates and a suppression-list screen, a list builder (customer search + bulk add; a CSV is parsed in the browser and posted as the customer ids it resolves, so no import endpoint is needed; a segment gets a rule builder from `GET /campaigns/segment-fields`), sidebar entry | #46–#48, #50 merged; 5d built (`feat/m5-5d-template-workflow`) |

## M6 Suppliers (started 2026-10-17)

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Suppliers API | migration 0022: supplier records and normalized contacts; supplier type lookup validation, address/payment/lead-time/currency/rating, custom fields, shared tags/notes/timeline, audit, permissions and tests | #51 merged |
| 2 | Supplied products API | `supplier_products`: supplier + shop SKU + supplier SKU, unit cost/currency and MOQ; CRUD, audit and tests | #52 open (carries batch 3) |
| 3 | Suppliers web | searchable supplier directory, supplier details, contacts and supplied products, record timeline/tags/custom fields, permission-aware editing | #53 merged into #52 |

## M7 Reports (started 2026-10-17)

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Reports API | overview composed from sales/ticket/campaign summaries; customer type/source/status breakdowns; ticket type/status/priority and SLA counts; supplier type/status/rating summary; permissions and tests | #54 merged |
| 2 | Reports web | reports page for sales forecast, ticket/SLA, campaign performance, customer mix and supplier summary; CSV export for tabular views | #55 merged |

## Plan — M8 Communication channels (unified inbox) (started 2026-10-17)

v1 ends at M7. SPEC §3.9 puts the unified inbox first after it, and §9 decision 3 makes "the inbox phase" the
last thing the shop's own inbox and campaigns wait on. The design follows the CRM's existing habit: **a
conversation is a ticket** (the shop's contact form already opens one, M3 batch 5), so the inbox is channels
arriving into tickets — one place to work with SLA, assignment and permissions already in it — not a second
conversation store next to the first one.

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Ticket channels | a ticket says how the conversation reached the CRM: `tickets.channel` (migration 0024; everything already in the table is `manual`) as a `ticket_channel` lookup (Email, Shop form, Phone, Live chat, Etsy, Manual), set when the ticket is opened — the shop handler passes `shop_form`, staff-typed tickets are `manual` — validated like the other lookups, filterable (`GET /tickets?channel=`), audited, and staff can re-file one. Web: a Channel column in the queue + filter, a picker in the dialog and a tag on the ticket page | 1 built (`feat/m8-1-ticket-channels`) |
| 2 | Mailboxes the CRM reads | new `inbox` module (migration 0025): `email_accounts` — the mailbox's address and display name, IMAP host/port/security (`ssl`/`starttls`/`none`), username (empty = its own address), folder and `is_active`, with the password stored encrypted (`imap_password_enc`, `DATA_ENCRYPTION_KEY`) and never returned by the API; a blank password in a patch keeps the stored one. CRUD for admins (`inbox:manage`, new — manager and admin, so support works the queue but not the credentials) and `POST /inbox/accounts/{id}/test`, which opens the mailbox now and answers `{ok, folder, messages, unseen}` or the server's own error. Reading is a small `InboundMailbox` interface with one stdlib `imaplib` implementation (`check()` in a thread, `readonly` so a test marks nothing read) and a factory tests can stand in for. A mailbox is deleted for real, so a password doesn't outlive the setup | 2 built (`feat/m8-2-inbox-mailboxes`, on top of batch 1) |
| 3 | Email in | the `inbox` job (once a minute) polls enabled mailboxes, takes the unread mail oldest-first (up to 50 a run), parses it and **opens or continues a ticket**: deduplicated by `Message-ID` (`ticket_messages.external_id`, unique, migration 0026) so a re-poll — or a crash between storing a message and marking it read — can't double a message; threaded by `In-Reply-To`/`References` and, if the client lost the headers, by the `[T-000123]` token in the subject. The sender is matched to a customer on any of their addresses (`by_any_email`: main or alt) and created if unknown, like the shop does. A new ticket is channel `email`, type "Other", unassigned, `status=new`, with `created_at`/`opened_at` from the mail's own `Date` (so the SLA clock starts when it arrived, not when we polled). A customer writing again reopens a resolved ticket and never touches the SLA clock. Our replies get their own `Message-ID` + `In-Reply-To`/`References` so the answer comes back to the same ticket. `Auto-Submitted` mail (out-of-office, robot-to-robot) and duplicates are skipped but marked read; spam is left for a later decision. The mailbox's health (`last_polled_at`, `last_error`, cleared by a good poll) is written on the account. Attachments are a later batch (storage decision) | 3 built (`feat/m8-3-email-in`, on top of batches 1–2) |
| 4 | Web: inbox + mailboxes | the unified inbox, plus the one API question it needed: `GET /tickets?needs_reply=` — is the customer's message the newest thing said, nobody having replied since? — asked of the newest `ticket_messages` direction (`true`, `false`, or not asked at all), and when it *is* asked the list comes back **oldest wait first**, which is the order a shared inbox is worked in. Web: `/inbox` with channel tabs (built from the `ticket_channel` lookup), Waiting-on-us / Everything-open, search, paging, and the thread in a pane beside the list — notes, canned replies and email replies all through the existing `Conversation`, a deep link (`?ticket=`, `?channel=`), and a way through to the full ticket (assigning, status, SLA). Settings → Email accounts (`inbox:manage`): the mailboxes with their last-read health (`last_polled_at`, `last_error`), add/edit (test connection on a saved mailbox), pause/read-again and remove. `Segmented` moved out of the queue into `components/ui` and is now the one filter control (queue, inbox, note-or-reply). No migration | 4 built (`feat/m8-4-inbox-web`, on top of batches 1–3) |
| 5 | Attachments | a new shared block beside notes and the timeline: `attachments` (migration 0027) is polymorphic on `(entity_type, entity_id)`, so a file hangs on any registered record and the existing `check_entity_access` decides who may see it — **no new permission**: reading a record's files asks for its *view* right, dropping one asks for its *edit* right. Inbound only: the `inbox` job keeps what the customer sent, up to `MAX_FILES` files of `MAX_BYTES` each per message, and everything left behind is **counted and said in the message body** rather than silently dropped. The bytes live behind a `FileStore` seam (`app/integrations/files/`: a protocol, one `LocalFileStore`, `file_store()`/`set_store_factory`, exactly like `mailbox_for`), keyed by the sha256 of their own content — so the same file sent twice is stored once, rows share it, and the stored bytes go with the last row that pointed at them. `filename` is display text only: flattened to one line, never a path (keys are validated against `^[0-9a-f]{64}$`). API: `GET /entities/{type}/{id}/attachments`, `GET /attachments/{id}` (always a download, `filename*=` for non-ASCII names, `nosniff`) and `DELETE /attachments/{id}` (soft, audited `attachment.delete`, one timeline line). Web: an `Attachments` list under the ticket conversation. Storage is local disk because the deployment is self-hosted: `attachments_dir` defaults to `~/apps/crm/wcw-crm-files`, **outside the checkout** so a deploy can't take a customer's photo with it. Documented follow-ups: staff uploads, outbound attachments (the SMTP sender would need them), virus scanning, and a "which message brought this?" link | 5 built (`feat/m8-5-attachments`, on top of batches 1–4) |
| later | Chat, Etsy, SMS, and retiring the shop's own inbox | each a channel that plugs into the same table; the shop side is a `wcw-shop-portal` batch | — |

Two notes for whoever picks this up:

- The four M8 branches were cut one from the next on top of the campaign follow-up branches, so the
  stack is `main` → `fix/campaign-tracking-links` → `feat/m5-6-one-click-unsubscribe` → batch 1 → batch 2
  → batch 3 → batch 4 → batch 5. Merge order follows from that: the campaign fix first, then one-click
  unsubscribe, then M8 1 → 2 → 3 → 4 → 5 (each PR states its dependency). Rebasing M8 onto `main` to make
  the PRs independent is possible but needs a force-push, so it is the owner's call.
- Batch 1's migration is `0024` off `0022_suppliers`, batch 2's is `0025` off `0024`, batch 3's is `0026`
  off `0025` and batch 5's is `0027` off `0026` (batch 4 has none), so each says "depends on" the one
  before and they merge in order. The unmerged
  `feat/m6-2-supplier-products` carries `0023`; whichever of *those* merges second must repoint its
  `down_revision` — the usual branch refresh does it (merge `origin/main` in, keep both sides).
- One SMTP identity still sends: replies go out through Admin → Settings → Email as they do today, even for a
  message that arrived on a mailbox. Sending *from* the mailbox it arrived on needs per-account SMTP
  credentials and is a follow-up, not a silent assumption. Outbound attachments ride along with that
  follow-up: today the CRM keeps what the customer sends and the reply is plain text through that one
  identity, so a file attached to a reply would not leave the building.

## Post-v1 follow-ups (started 2026-10-17)

v1 (M0–M7) is built; these are the campaign-mail items it left behind, worst first.

| # | Batch | Contents | PR |
|---|-------|----------|----|
| 1 | Campaign tracking fix | real sends were rendered without a `recipient_id`, so no open pixel and no wrapped links ever left the building and `campaign_events` stayed empty: every tracking endpoint worked, so the tests (which minted their own tokens) never noticed. `_queue` now passes the recipient, and a regression test follows the links out of the message that was actually sent | `fix/campaign-tracking-links` |
| 2 | One-click unsubscribe | the `List-Unsubscribe` header and `List-Unsubscribe-Post: List-Unsubscribe=One-Click` on campaign mail, plus the body-less POST a mail client makes when a reader presses its own Unsubscribe button (the token in the URL is the proof). Gmail and Yahoo expect this of bulk senders | `feat/m5-6-one-click-unsubscribe` |
| 3 | What a test send carries | **decided (2026-10-17): nothing more.** A test send is a preview of the words, so it carries neither the tracking links (there is no recipient to hang an open or a click on, and a made-up one would land in that campaign's own report) nor the `List-Unsubscribe` header. To eyeball the header, send a real campaign to a list that contains your own address | decided |

## Next milestones
M4 sales (6 of 7 batches built: Sales API + web, Leads API + web, Deal items API + web; 4c waits on the shop's `products` read resource) → M5 campaigns (complete and merged, #40–#48 and #50, except the template-workflow polish on `feat/m5-5d-template-workflow`) → M6 suppliers (batch 1 merged, #51; batches 2–3 built on `feat/m6-2-supplier-products` / `feat/m6-3-suppliers-web`) → M7 reports (batch 1 merged, #54; batch 2 in #55) → **post-v1 campaign-mail follow-ups (1 built on `fix/campaign-tracking-links`, 2 on `feat/m5-6-one-click-unsubscribe`; 3 is a decision, no work)** → **M8 communication channels / unified inbox (batch 1 ticket channels on `feat/m8-1-ticket-channels`, batch 2 the mailboxes the CRM reads on `feat/m8-2-inbox-mailboxes`, batch 3 email in on `feat/m8-3-email-in`, batch 4 the inbox web on `feat/m8-4-inbox-web`, batch 5 attachments on `feat/m8-5-attachments`; then chat, Etsy, SMS)**.
