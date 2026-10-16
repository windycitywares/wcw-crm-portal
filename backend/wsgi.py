"""WSGI entry point for cPanel "Setup Python App" (CloudLinux + LiteSpeed/Passenger).

cPanel generates its own passenger_wsgi.py that loads this file; configure the app with
Startup file = wsgi.py and Entry point = application.

Passenger/LiteSpeed only speak WSGI, and FastAPI is ASGI, so this module adapts one to the
other. It runs each request to completion on its own event loop and returns the buffered
response. That is deliberately simple:
  * the request body is read only up to CONTENT_LENGTH (LiteSpeed's input stream blocks if
    read past the end, e.g. on a GET);
  * once the body has been delivered, further `receive()` calls wait until the response is
    finished and then report a disconnect — so middleware that watches for disconnects
    can't deadlock the request;
  * responses are buffered (fine for JSON APIs and the Excel export; no streaming/websockets).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app  # noqa: E402

MAX_BODY_BYTES = 25 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 60


def _read_body(environ) -> bytes:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length <= 0:
        return b""
    length = min(length, MAX_BODY_BYTES + 1)
    stream, chunks, remaining = environ["wsgi.input"], [], length
    while remaining > 0:
        chunk = stream.read(min(remaining, 64 * 1024))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _scope(environ) -> dict:
    headers = []
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            headers.append((key[5:].replace("_", "-").lower().encode("latin-1"), value.encode("latin-1")))
    for key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
        if environ.get(key):
            headers.append((key.replace("_", "-").lower().encode("latin-1"), environ[key].encode("latin-1")))
    path = environ.get("PATH_INFO", "") or "/"
    server_port = int(environ.get("SERVER_PORT") or 0) or None
    client_port = int(environ.get("REMOTE_PORT") or 0)
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": environ.get("SERVER_PROTOCOL", "HTTP/1.1").split("/")[-1],
        "method": environ.get("REQUEST_METHOD", "GET").upper(),
        "scheme": environ.get("wsgi.url_scheme", "http"),
        "path": path,
        "raw_path": path.encode("latin-1", "replace"),
        "query_string": environ.get("QUERY_STRING", "").encode("latin-1"),
        "root_path": environ.get("SCRIPT_NAME", ""),
        "headers": headers,
        "client": (environ.get("REMOTE_ADDR", ""), client_port),
        "server": (environ.get("SERVER_NAME", ""), server_port),
    }


async def _run(scope: dict, body: bytes):
    response_done = asyncio.Event()
    body_sent = False
    status = 500
    headers: list[tuple[bytes, bytes]] = []
    chunks: list[bytes] = []

    async def receive():
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await response_done.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal status, headers
        if message["type"] == "http.response.start":
            status = message["status"]
            headers = list(message.get("headers", []))
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                response_done.set()

    try:
        await asyncio.wait_for(app(scope, receive, send), REQUEST_TIMEOUT_SECONDS)
    finally:
        response_done.set()
    return status, headers, b"".join(chunks)


_REASONS = {
    200: "OK", 201: "Created", 202: "Accepted", 204: "No Content", 301: "Moved Permanently",
    302: "Found", 304: "Not Modified", 307: "Temporary Redirect", 400: "Bad Request",
    401: "Unauthorized", 403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
    409: "Conflict", 413: "Payload Too Large", 422: "Unprocessable Entity",
    429: "Too Many Requests", 500: "Internal Server Error", 503: "Service Unavailable",
}


def application(environ, start_response):
    body = _read_body(environ)
    if len(body) > MAX_BODY_BYTES:
        start_response("413 Payload Too Large", [("Content-Type", "text/plain")])
        return [b"Request body too large"]
    try:
        status, headers, content = asyncio.run(_run(_scope(environ), body))
    except Exception as exc:  # noqa: BLE001 - never leave the worker hanging
        print(f"wsgi adapter error: {type(exc).__name__}: {exc}", file=sys.stderr)
        start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
        return [b"Internal Server Error"]
    start_response(
        f"{status} {_REASONS.get(status, 'Status')}",
        [(k.decode("latin-1"), v.decode("latin-1")) for k, v in headers],
    )
    return [content]
