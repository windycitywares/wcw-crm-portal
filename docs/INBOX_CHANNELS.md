# Channels → the CRM inbox

How anything that isn't a mailbox — live chat, an Etsy poller, an SMS gateway — hands the CRM one message at
a time, so it lands in a ticket exactly like mail does.

CRM side: `backend/app/modules/inbox/` (`public.py` the route, `intake.py` the door, `filing.py` the rules
both mail and channels are filed by). Connector side: the shop's chat widget, an Etsy poller, a gateway —
anything that can make an HTTP request.

## Connection

| | |
|---|---|
| URL | `POST https://crm-api.windycitywares.com/api/v1/inbox/messages` (shown in CRM → Settings → Integrations → *Messages from other channels*) |
| Secret | Generated there (at least 32 characters) and copied into the connector; it never crosses the wire |
| Body | JSON, UTF-8, at most 24 MB with its files |
| Headers | `Content-Type: application/json` · `X-WCW-Timestamp: <unix seconds>` · `X-WCW-Signature: sha256=<hex>` |

**Signature:** `hex(HMAC-SHA256(secret, f"{timestamp}." + raw_body))` — the same scheme the shop's events use
(`backend/app/integrations/signing.py`). The CRM refuses a request whose timestamp is more than 5 minutes off,
so a captured request can't be replayed, and it limits repeated bad signatures per IP.

```python
import hashlib, hmac, json, time
body = json.dumps(message, separators=(",", ":")).encode()
ts = int(time.time())
sig = "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
```

## One message

```json
{
  "id": "chat-9f0c8b71",
  "channel": "live_chat",
  "at": "2026-10-18T14:02:11Z",
  "subject": null,
  "body": "Do you ship to Canada?",
  "from": {"email": "jane@example.com", "name": "Jane Doe"},
  "thread": "chat-9f0c8b70",
  "files": [{"filename": "cart.png", "content_type": "image/png", "data": "<base64>"}]
}
```

| Field | |
|---|---|
| `id` | required. The channel's own id for the message (1–200 chars). **Posting the same id again is safe** — the CRM answers `{"status":"duplicate"}` and files nothing more, so a connector may retry freely. |
| `channel` | required. The ticket channel it arrived on: `live_chat`, `etsy`, `phone`, … — a value in Admin → Settings → Types → *Ticket channels*. One the CRM doesn't have is refused rather than filed as a ticket nobody can find. |
| `body` | the message text, at most 20,000 characters. A message that is nothing but a file may leave it out. |
| `subject` | optional. Without one the ticket is named "Live chat: <its first words>". |
| `at` | when the customer sent it (ISO 8601). The ticket and its first message are dated then, not when the CRM heard about it. |
| `from` | who wrote in: `email` finds or creates that customer (an existing name is never overwritten); `name` fills in a blank one. A chat from nobody the CRM can name is still filed — staff link it by hand. |
| `thread` | the `id` of the message this one answers. The answer joins that ticket and reopens it instead of opening a second one. |
| `files` | up to 10 files, each at most 15 MB once decoded, base64 in `data`. A file the CRM won't keep is left out and *counted* in the message ("1 file came with this message and couldn't be kept"). |

Anything the CRM doesn't recognise in the payload is ignored, so a connector may send more than this.

## What the CRM does with it

- files it as a ticket — unassigned, priority *Normal*, type *Other* — carrying the `channel` it came in on;
  or joins the ticket `thread` names, reopening it;
- finds or creates the customer from `from.email`, exactly as a shop event or a mailbox does;
- keeps `files` against that ticket, where the conversation shows them (`app/modules/attachments`).

Staff see it in **CRM → Inbox** and **CRM → Tickets** like any other conversation. A reply goes out by email
through the single SMTP identity in Admin → Settings → Email.

## Responses

| Code | Meaning | Connector should |
|---|---|---|
| 201 `{"status":"filed","ticket_id":12,"files":1}` | filed, or joined a conversation | mark sent |
| 200 `{"status":"duplicate","ticket_id":12}` | this id is already in | mark sent |
| 400 | not a valid message: bad JSON, unknown channel, a file that isn't base64 | log, don't retry |
| 401 | bad or missing signature, or the clock is off | check the secret and the server clock; retry later |
| 413 | too large | log, don't retry |
| 429 | too many bad signatures from this address | retry later |
| 503 | channels are switched off in the CRM | retry later |

A 5xx means the CRM failed to file a message it had agreed to read: post it again. The `id` is stored with
the message, so a re-post is a duplicate, never a second ticket.

## What is *not* this

- **Mail** arrives on the mailboxes the CRM reads (Admin → Settings → Email accounts, the `inbox` job).
- **The shop's contact form** arrives as a `contact_message.created` event (docs/SHOP_EVENTS.md).
- **A conversation staff start** picks its channel from the same list when they open the ticket.
