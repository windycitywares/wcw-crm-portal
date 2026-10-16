"""backend/wsgi.py adapter: no hangs on LiteSpeed-style input streams; works with BaseHTTPMiddleware."""

import importlib.util
import io
import sys
import threading
import types
import unittest
from pathlib import Path

try:
    from starlette.applications import Starlette
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.middleware.gzip import GZipMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Route
except ImportError:  # pragma: no cover
    Starlette = None


class BlockingStream(io.BytesIO):
    """Like LiteSpeed: reading past the end of the body blocks (here: raises)."""

    def read(self, n=-1):
        if self.tell() >= len(self.getvalue()):
            raise RuntimeError("read past end of body would block")
        return super().read(n)


@unittest.skipIf(Starlette is None, "starlette not installed")
class WsgiAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        async def health(request):
            return JSONResponse({"status": "ok"})

        async def echo(request):
            form = await request.form()
            return JSONResponse(
                {"got": dict(form), "q": request.query_params.get("q"), "auth": request.headers.get("authorization")}
            )

        class Headers(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                response = await call_next(request)
                response.headers["X-Frame-Options"] = "DENY"
                return response

        app = Starlette(routes=[Route("/health", health), Route("/echo", echo, methods=["POST"])])
        app.add_middleware(Headers)
        app.add_middleware(GZipMiddleware, minimum_size=1024)

        saved = {k: sys.modules.get(k) for k in ("app", "app.main")}
        fake_main = types.ModuleType("app.main")
        fake_main.app = app
        sys.modules.update({"app": types.ModuleType("app"), "app.main": fake_main})
        try:
            path = Path(__file__).resolve().parents[1] / "wsgi.py"
            spec = importlib.util.spec_from_file_location("wcw_wsgi_under_test", path)
            cls.wsgi = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.wsgi)
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

    def call(self, method, path, body=b"", ctype=None, extra=None):
        p, _, q = path.partition("?")
        env = {
            "REQUEST_METHOD": method, "PATH_INFO": p, "QUERY_STRING": q, "SERVER_NAME": "api",
            "SERVER_PORT": "443", "SERVER_PROTOCOL": "HTTP/1.1", "wsgi.url_scheme": "https",
            "wsgi.input": BlockingStream(body), "REMOTE_ADDR": "1.2.3.4", "HTTP_HOST": "api", **(extra or {}),
        }
        if body:
            env["CONTENT_LENGTH"] = str(len(body))
        if ctype:
            env["CONTENT_TYPE"] = ctype
        out, result = {}, {}

        def start_response(status, headers):
            out["status"], out["headers"] = status, dict(headers)

        t = threading.Thread(target=lambda: result.update(body=b"".join(self.wsgi.application(env, start_response))))
        t.daemon = True
        t.start()
        t.join(5)
        self.assertFalse(t.is_alive(), f"{method} {path} hung")
        return out["status"], out["headers"], result["body"]

    def test_get_without_body_does_not_hang(self):
        for _ in range(3):
            status, headers, body = self.call("GET", "/health")
            self.assertEqual(status, "200 OK")
            self.assertEqual(headers["x-frame-options"], "DENY")
            self.assertEqual(body, b'{"status":"ok"}')

    def test_form_post_query_and_headers(self):
        status, _, body = self.call(
            "POST", "/echo?q=hi", b"username=a%40b.com&password=x",
            "application/x-www-form-urlencoded", {"HTTP_AUTHORIZATION": "Bearer t"},
        )
        self.assertEqual(status, "200 OK")
        for part in (b'"username":"a@b.com"', b'"q":"hi"', b'"auth":"Bearer t"'):
            self.assertIn(part, body)

    def test_not_found(self):
        self.assertTrue(self.call("GET", "/missing")[0].startswith("404"))


if __name__ == "__main__":
    unittest.main()
