"""Which address a request really came from, for the per-visitor rate limits.

`X-Forwarded-For` is just a header: any caller can send one. On this host the web server hands the app the
connecting address itself and adds nothing to that header, so trusting the header let a caller pick a new
rate-limit key for every request (found in the Nov 2026 QA pass). The rule now:

* a request that connects from anywhere else is counted under the address it connected from;
* only a request that connects from our own machine (a local reverse proxy, or another of our own servers) may say who it is acting for, and then the right-most address that isn't ours is used.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from urllib.parse import urlparse

from app.core.config import get_settings

_OWN: tuple[float, frozenset[str]] | None = None
_OWN_TTL = 600.0
# Spelled out, not `ip.is_private`: that also covers the documentation ranges, which the tests use as "visitors".
_INTERNAL = tuple(ipaddress.ip_network(n) for n in (
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "::1/128", "fc00::/7", "fe80::/10",
))


def is_internal(address: str) -> bool:
    """Loopback, private-network and link-local addresses: never a visitor on the public internet."""
    try:
        ip = ipaddress.ip_address(address.strip().strip("[]"))
    except ValueError:
        return False
    return any(ip.version == net.version and ip in net for net in _INTERNAL)


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip().strip("[]"))
    except ValueError:
        return False
    return True


def pick_ip(peer: str | None, forwarded_for: str | None, own: frozenset[str] = frozenset()) -> str:
    """Pure rule (unit-tested): the address to count this request under."""
    peer = (peer or "").strip()
    trusted = lambda a: a in own or is_internal(a)  # noqa: E731
    # A peer that isn't an IP address at all (a unix socket, the test client) is a local transport, not a visitor.
    if _is_ip(peer) and not trusted(peer):
        return peer[:64]
    for candidate in reversed([part.strip() for part in (forwarded_for or "").split(",")]):
        if _is_ip(candidate) and not trusted(candidate):
            return candidate[:64]
    return (peer or "unknown")[:64]


def _resolve(host: str) -> set[str]:
    try:
        return {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        return set()


def own_addresses() -> frozenset[str]:
    """This machine's public addresses: what its own sites resolve to, plus its host name. Cached for ten minutes."""
    global _OWN
    if _OWN is not None and time.monotonic() - _OWN[0] < _OWN_TTL:
        return _OWN[1]  # an empty answer (DNS down) is kept too, so a request never waits on DNS twice
    settings = get_settings()
    hosts = {socket.gethostname()}
    for url in [settings.site_url, *settings.cors_origins]:
        host = urlparse(url).hostname
        if host:
            hosts.add(host)
    addresses: set[str] = set()
    for host in hosts:
        addresses |= _resolve(host)
    addresses |= {part.strip() for part in settings.trusted_proxies.split(",") if part.strip()}
    _OWN = (time.monotonic(), frozenset(addresses))
    return _OWN[1]


def real_client_ip(request) -> str:
    peer = request.client.host if request.client else ""
    return pick_ip(peer, request.headers.get("x-forwarded-for"), own_addresses())
