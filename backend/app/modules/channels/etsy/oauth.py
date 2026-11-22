"""Pieces of Etsy's OAuth 2.0 + PKCE flow that need no network (see https://developers.etsy.com/documentation/essentials/authentication)."""

import base64
import hashlib
import secrets
from urllib.parse import urlencode

AUTHORIZE_URL = "https://www.etsy.com/oauth/connect"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
API_BASE = "https://api.etsy.com/v3/application"

# Read listings and orders; write tracking (transactions_w). email_r asks for the buyer's email where Etsy allows it.
SCOPES = ("listings_r", "transactions_r", "transactions_w", "shops_r", "email_r")


def new_verifier() -> str:
    return secrets.token_urlsafe(48)  # 64 chars, within PKCE's 43–128


def challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def new_state() -> str:
    return secrets.token_urlsafe(24)


def authorize_url(*, client_id: str, redirect_uri: str, state: str, verifier: str) -> str:
    return AUTHORIZE_URL + "?" + urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri, "scope": " ".join(SCOPES),
        "state": state, "code_challenge": challenge(verifier), "code_challenge_method": "S256",
    })


def user_id_from_token(access_token: str) -> int | None:
    """Etsy access tokens look like `<etsy user id>.<random>`."""
    head = access_token.split(".", 1)[0]
    return int(head) if head.isdigit() else None
