"""FastAPI application factory. Routers come from the module registry (app/modules/__init__.py)."""

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.modules import CrmModule, load_modules

__version__ = "0.1.0"

log = logging.getLogger("wcw.crm")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


def create_app(modules: list[CrmModule] | None = None) -> FastAPI:
    settings = get_settings()
    modules = load_modules() if modules is None else modules
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def unexpected_errors(request, call_next):
        """An unhandled error still has to be an HTTP answer.

        Starlette keeps the handler for a bare `Exception` in the outermost middleware, above CORS, so a
        crash answers *without* CORS headers — and a browser, unable to read the reply it did get, reports
        a 500 the same way it reports an unreachable server: "can't reach the CRM server. Check your
        connection." That is the least useful thing it could say, and it hides real bugs (a broken page
        looks like a dead server). Catching here — inside CORS, outside the routes — keeps the status and
        the headers, so the browser shows what actually happened; the traceback still goes to the log.
        """
        try:
            return await call_next(request)
        except Exception:
            log.exception("unhandled error on %s %s", request.method, request.url.path)
            return JSONResponse({"detail": "Internal server error"}, status_code=500)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        h.setdefault("Cross-Origin-Resource-Policy", "same-site")
        h.setdefault("Cache-Control", "no-store")  # CRM data is private: never cache API responses
        if settings.is_production:
            h.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    api = APIRouter()
    for mod in modules:
        for hook in mod.on_startup:
            hook()
    # Public routers first: a route like `/campaigns/unsubscribe` must not be swallowed by an authenticated
    # `/campaigns/{campaign_id}` (the first path that matches wins, and the id is validated afterwards).
    for mod in modules:
        if mod.public_router is not None:  # no session: only for links a customer clicks (see CrmModule)
            api.include_router(mod.public_router)
    for mod in modules:
        if mod.router is not None:
            api.include_router(mod.router)
    app.include_router(api, prefix=settings.api_prefix)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
