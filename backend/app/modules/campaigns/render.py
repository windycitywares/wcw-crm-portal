"""Merge fields and the sandboxed renderer (SPEC §3.6).

Campaign email is written by staff and then rendered once per customer, so the template language is Jinja2
in a `SandboxedEnvironment`: no reaching into objects, no imports, and an unknown or misspelled merge field
is an **error** (`StrictUndefined`) rather than a blank in somebody's inbox. A template is rendered with
sample data when it is saved, so a typo is caught at the desk and not by a customer.

Every rendered message ends with the compliance footer — the postal address from Admin → Settings → Email
and the customer's own unsubscribe link — whether the template remembered to include one or not, and carries
the `List-Unsubscribe` headers that let a mail client offer its own Unsubscribe button.

Tracking (SPEC §3.6) happens here too, on the way out: `track_links` wraps the links in a message so a click
is recorded and redirected, and `tracking_pixel` is the one-pixel image an open is recorded by. Both belong to
a rendered message rather than to a template, so a preview and a test send show the words as written.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from html import unescape
from typing import Any

from jinja2 import StrictUndefined, TemplateError
from jinja2.exceptions import SecurityError
from jinja2.sandbox import SandboxedEnvironment

from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError

_TAG_BLOCK = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_BLOCK_END = re.compile(r"</?(p|div|h[1-6]|li|ul|ol|table|tr|blockquote)\b[^>]*>", re.I)
_BREAK = re.compile(r"<br\s*/?>", re.I)
_ANY_TAG = re.compile(r"<[^>]+>")
_HREF = re.compile(r'(<a\b[^>]*?\bhref\s*=\s*)(["\'])(.*?)\2', re.I | re.S)

# What a template may say. Anything else is a typo and stops the render (SPEC §3.6 merge fields).
MERGE_FIELDS: tuple[tuple[str, str], ...] = (
    ("customer.first_name", "First name, e.g. Dana"),
    ("customer.last_name", "Last name, e.g. Reed"),
    ("customer.full_name", "First and last name together"),
    ("customer.company", "Company, blank when they are not a business"),
    ("customer.email", "Their email address"),
    ("customer.customer_type", "Retail, Wholesale … the label from Admin → Settings → Types"),
    ("customer.owner_name", "The staff member who looks after them"),
    ("sender_name", "The sender name from Admin → Settings → Email"),
    ("unsubscribe_url", "This customer's unsubscribe link (added to every email anyway)"),
)

# A made-up customer so a preview always has something to show.
SAMPLE_CUSTOMER: dict[str, str] = {
    "first_name": "Dana",
    "last_name": "Reed",
    "full_name": "Dana Reed",
    "company": "Reed & Co",
    "email": "dana@example.com",
    "customer_type": "Retail",
    "owner_name": "Sam Patel",
}


def _environment(*, autoescape: bool) -> SandboxedEnvironment:
    return SandboxedEnvironment(undefined=StrictUndefined, autoescape=autoescape)


_TEXT_ENV = _environment(autoescape=False)  # a subject or text body: "&" stays "&"
_HTML_ENV = _environment(autoescape=True)  # a customer's name is escaped before it goes in the markup


def merge_fields() -> list[dict[str, str]]:
    """The list the template editor shows: what may be written, and what it turns into."""
    return [{"name": name, "description": description} for name, description in MERGE_FIELDS]


def sample_context() -> dict[str, Any]:
    """The merge fields for a preview with nobody in mind."""
    base = get_settings().site_url.rstrip("/")
    return {"customer": dict(SAMPLE_CUSTOMER), "sender_name": "Windy City Wares",
            "unsubscribe_url": f"{base}/unsubscribe?token=sample"}


def render(source: str, context: dict[str, Any], *, html: bool = False) -> str:
    """Render one body. Raises `ValidationFailedError` for a bad merge field or the sandbox saying no."""
    env = _HTML_ENV if html else _TEXT_ENV
    try:
        return env.from_string(source or "").render(**context)
    except (TemplateError, SecurityError) as exc:
        raise ValidationFailedError(f"Could not render the email: {exc}") from exc


def plain_text(html: str) -> str:
    """A rough text version of an HTML body, for when the author leaves the text body empty.

    Turns breaks and block ends into newlines, drops the tags and collapses the whitespace. It is not a
    renderer — the author can always write the text body themselves.
    """
    text = _TAG_BLOCK.sub(" ", html or "")
    text = _BREAK.sub("\n", text)
    text = _BLOCK_END.sub("\n", text)
    text = unescape(_ANY_TAG.sub("", text))
    lines: list[str] = []
    for line in text.splitlines():
        line = " ".join(line.split())
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")
    return "\n".join(lines).strip()


def with_footer(html: str, text: str, *, sender_name: str, footer_address: str,
                unsubscribe_url: str) -> tuple[str, str]:
    """Append the compliance footer (SPEC §3.6): who is writing, from where, and how to stop it."""
    address = f"<br>{footer_address}" if footer_address else ""
    html = (f"{html.rstrip()}\n"
            '<hr style="border:none;border-top:1px solid #e2e2e2;margin:24px 0 12px">\n'
            '<p style="color:#6b7280;font-size:12px;line-height:1.6;margin:0">'
            f"{sender_name}{address}<br>"
            f'<a href="{unsubscribe_url}" style="color:#6b7280">Unsubscribe</a> from emails like this one.'
            "</p>\n")
    text_address = f"{footer_address}\n" if footer_address else ""
    text = f"{text.rstrip()}\n\n--\n{sender_name}\n{text_address}Unsubscribe: {unsubscribe_url}\n"
    return html, text


def track_links(html: str, wrap: Callable[[str], str]) -> str:
    """Rewrite the links in a message so a click comes back to us (SPEC §3.6).

    Only web links are wrapped: a `mailto:`, a `tel:` or a jump to an anchor inside the message is not an HTTP
    request, and wrapping one would only break it. This runs **before** the footer is added, so the unsubscribe
    link stays a plain link — it is a compliance link, not something to measure.
    """
    def swap(match: re.Match[str]) -> str:
        start, quote, url = match.group(1), match.group(2), unescape(match.group(3)).strip()
        if not url.lower().startswith(("http://", "https://")):
            return match.group(0)
        return f"{start}{quote}{wrap(url)}{quote}"

    return _HREF.sub(swap, html)


def tracking_pixel(url: str) -> str:
    """The 1×1 image at the end of a message that an open is recorded by (SPEC §3.6).

    It is an image, so a customer who reads their email with images turned off is simply not counted as having
    opened it — which is why this is a signal to learn from, not a number to believe.
    """
    return f'<img src="{url}" alt="" width="1" height="1" style="border:0;height:1px;width:1px" />'


def unsubscribe_headers(one_click_url: str) -> dict[str, str]:
    """The headers a mail client offers its own Unsubscribe button from (RFC 8058 "one click").

    Gmail and Yahoo ask this of bulk senders: the reader presses Unsubscribe in their mail client, the client
    posts to the address in the header without asking them anything, and it is told nothing back. So the URL
    has to carry the customer's signed token itself, exactly as the footer's link does.
    """
    return {"List-Unsubscribe": f"<{one_click_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
