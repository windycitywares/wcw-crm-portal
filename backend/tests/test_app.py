"""App factory: health endpoint, security headers, module registry."""

import unittest

try:
    from fastapi import APIRouter
    from fastapi.testclient import TestClient
except (ImportError, RuntimeError):  # pragma: no cover - httpx (TestClient) is only installed in CI
    APIRouter = None


@unittest.skipIf(APIRouter is None, "fastapi not installed")
class AppTests(unittest.TestCase):
    def test_health_and_headers(self):
        from app.main import create_app

        client = TestClient(create_app(modules=[]))
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")
        self.assertEqual(res.headers["x-frame-options"], "DENY")
        self.assertEqual(res.headers["cache-control"], "no-store")

    def test_module_routers_are_mounted_under_api_prefix(self):
        from app.main import create_app
        from app.modules import CrmModule

        router = APIRouter(prefix="/ping")

        @router.get("")
        async def ping():
            return {"pong": True}

        started = []
        mod = CrmModule(name="ping", router=router, on_startup=(lambda: started.append(1),))
        client = TestClient(create_app(modules=[mod]))
        self.assertEqual(client.get("/api/v1/ping").json(), {"pong": True})
        self.assertEqual(started, [1])

    def test_domain_errors_map_to_status_codes(self):
        from app.core.exceptions import NotFoundError
        from app.main import create_app
        from app.modules import CrmModule

        router = APIRouter()

        @router.get("/missing")
        async def missing():
            raise NotFoundError("Customer not found")

        client = TestClient(create_app(modules=[CrmModule(name="t", router=router)]))
        res = client.get("/api/v1/missing")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json(), {"detail": "Customer not found"})

    def test_public_routers_come_before_a_module_wildcard(self):
        """A public route has to win over an authenticated `/{id}` that would otherwise match it, and it has
        to work with no session at all."""
        from app.main import create_app
        from app.modules import CrmModule

        router = APIRouter(prefix="/things")

        @router.get("/{thing_id}")
        async def thing(thing_id: int):
            raise AssertionError("the public route should have matched")

        public = APIRouter(prefix="/things")

        @public.get("/unsubscribe")
        async def unsubscribe():
            return {"public": True}

        mod = CrmModule(name="t", router=router, public_router=public)
        client = TestClient(create_app(modules=[mod]))
        res = client.get("/api/v1/things/unsubscribe")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json(), {"public": True})

    def test_load_modules_rejects_bad_packages(self):
        from app.modules import load_modules

        with self.assertRaises(TypeError):
            load_modules(("app.core.events",))  # has no `module = CrmModule(...)`


class SecretBoxTests(unittest.TestCase):
    def test_round_trip_and_wrong_key(self):
        from cryptography.fernet import Fernet

        from app.core.security import SecretBox

        box = SecretBox(Fernet.generate_key().decode())
        token = box.encrypt("smtp-pass")
        self.assertNotIn("smtp-pass", token)
        self.assertEqual(box.decrypt(token), "smtp-pass")
        with self.assertRaises(ValueError):
            SecretBox(Fernet.generate_key().decode()).decrypt(token)


if __name__ == "__main__":
    unittest.main()
