# Shop → CRM events

How shop.windycitywares.com tells the CRM about customers, orders and newsletter sign-ups.
CRM side: `backend/app/integrations/shop/`. Shop side: M2 batch 4 (PR in `wcw-shop-portal`).

## Connection

| | |
|---|---|
| URL | `POST https://crm-api.windycitywares.com/api/v1/integrations/shop/webhook` (shown in CRM → Administration → Integrations) |
| Secret | Generated in CRM → Integrations; set in the shop's `backend/.env` as `CRM_WEBHOOK_SECRET` (with `CRM_WEBHOOK_URL`) |
| Body | JSON, UTF-8, at most 256 KB |
| Headers | `Content-Type: application/json` · `X-WCW-Timestamp: <unix seconds>` · `X-WCW-Signature: sha256=<hex>` |

**Signature:** `hex(HMAC-SHA256(secret, f"{timestamp}." + raw_body))`. The CRM refuses requests whose
timestamp is more than 5 minutes off and limits repeated bad signatures per IP.

```python
import hashlib, hmac, json, time
body = json.dumps(event, separators=(",", ":")).encode()
ts = int(time.time())
sig = "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
```

## Envelope

```json
{"id": "8f0c…", "type": "order.updated", "occurred_at": "2026-10-16T12:00:00Z", "data": {…}}
```

- `id` — unique per event (8–64 chars, e.g. a UUID hex). **Re-sending the same id is safe**: the CRM answers
  `{"status": "duplicate"}` and changes nothing, so the shop can retry freely.
- Unknown `type`s are stored and marked *ignored* (the shop can ship new types first).
- Unknown fields inside `data` are ignored.

## Responses

| Code | Meaning | Shop should |
|---|---|---|
| 200 `{"status":"accepted"}` / `{"status":"duplicate"}` | stored (and applied, or queued for retry) | mark sent |
| 400 | not a valid event | log, don't retry |
| 401 | bad/missing signature or clock off | check the secret / server clock; retry later |
| 413 | too large | log, don't retry |
| 429 | too many bad signatures | retry later |
| 503 | connection switched off in the CRM | retry later |

A 200 means the CRM has the event. If applying it fails (e.g. a database hiccup), the CRM retries on its own
every minute, up to 5 times; failures show in CRM → Integrations with a *Retry now* button.

## Event types

### `customer.upserted` — a shop account was created or changed
```json
{"id": 123, "email": "jane@example.com", "full_name": "Jane Doe", "phone": "312-555-0100"}
```
Customer found by shop account id, else by email, else created (source *Shop*). Names, phone and address are
only filled in when blank in the CRM (staff edits win). A changed account email becomes the primary email; the
old one is kept under *Other emails*. Send for customer accounts only, not staff.

### `order.updated` — an order was placed or changed (send on every status/payment/refund change)
```json
{"id": 987, "number": "WCW-1042", "user_id": 123, "email": "jane@example.com", "customer_name": "Jane Doe",
 "phone": null, "status": "paid", "payment_status": "paid", "currency": "USD", "grand_total": "54.00",
 "refunded_total": "0.00", "placed_at": "2026-10-16T11:58:00Z", "updated_at": "2026-10-16T12:00:00Z",
 "marketing_opt_in": true,
 "billing_address": {"line1": "1 Main St", "line2": null, "city": "Chicago", "region": "IL", "postal_code": "60601", "country": "US"}}
```
- `updated_at` is required for ordering: a copy older than the one the CRM has is ignored.
- Totals: orders in `paid / processing / shipped / delivered / refunded` count; spent = `grand_total − refunded_total`.
- The customer's timeline gets a line when the status changes (not for `pending`).
- `marketing_opt_in: true` records consent ("shop checkout"); `false` never removes it.

### `newsletter.subscribed`
```json
{"email": "jane@example.com", "source": "site"}
```
Creates the customer if needed and records consent ("shop newsletter, site").

### `newsletter.unsubscribed`
```json
{"email": "jane@example.com"}
```
Withdraws consent for an existing customer; unknown addresses are ignored.
