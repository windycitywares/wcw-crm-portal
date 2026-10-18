"""The channels that aren't mailboxes (SPEC §3.9): Admin → Settings → Integrations → Inbox channels.

A connector — the shop's chat widget, an Etsy poller, an SMS gateway — hands the CRM one message at a
time over HTTP, signed with a secret both sides know (docs/INBOX_CHANNELS.md). This is that secret, and
the switch that opens the door. One secret is enough for a small team; a per-connector secret can be
added later without changing the contract.
"""

from pydantic import BaseModel, Field, model_validator


class InboxSettings(BaseModel):
    """Admin → Settings → Integrations → Inbox channels."""

    enabled: bool = False
    ingest_secret: str = Field(default="", max_length=200)  # secret, shared with every connector

    @model_validator(mode="after")
    def _check(self) -> "InboxSettings":
        if self.ingest_secret and len(self.ingest_secret) < 32:
            raise ValueError("The channel secret must be at least 32 characters (use Generate)")
        if self.enabled and not self.ingest_secret:
            raise ValueError("A secret is needed before a channel can hand the CRM a message")
        return self


SECRETS = ("ingest_secret",)
