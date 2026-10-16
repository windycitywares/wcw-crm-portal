"""Module registry — how feature modules plug into the app (open/closed principle).

Each feature package (`app/modules/<name>/`) exposes a `module` object:

    # app/modules/customers/__init__.py
    from app.modules import CrmModule
    from .router import router

    module = CrmModule(name="customers", router=router, models="app.modules.customers.models")

and is listed once in `INSTALLED_MODULES`. `app.main` mounts every router; Alembic imports every
`models` path so autogenerate sees all tables; `on_startup` hooks subscribe event handlers.
Nothing else needs editing to add a module.
"""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter

# Order matters only for menus and seed data; dependencies between modules go through services/events.
INSTALLED_MODULES: tuple[str, ...] = (
    "app.modules.users",
    "app.modules.audit",
    "app.modules.lookups",
    "app.modules.tags",
    "app.modules.activity",
    "app.modules.customfields",
    "app.modules.settings",
    "app.modules.mail",
    "app.modules.deploy",
    # "app.modules.customers",   # M2
)


@dataclass(frozen=True)
class CrmModule:
    name: str
    router: APIRouter | None = None
    models: str | None = None  # dotted path of the models module, imported for metadata
    on_startup: tuple[Callable[[], None], ...] = field(default_factory=tuple)
    # Default data, run by `python -m app.seed` (and every deploy). Must never change existing rows.
    # Receives an AsyncSession; returns a short line for the log. The seed script commits.
    seed: Callable[[Any], Awaitable[str]] | None = None
    # Background jobs run by `python -m app.workers.run_jobs` (cron, every minute): (name, fn).
    # fn receives an AsyncSession and returns a short line for the log, or None when it did nothing.
    jobs: tuple[tuple[str, Callable[[Any], Awaitable[str | None]]], ...] = field(default_factory=tuple)


def load_modules(paths: tuple[str, ...] = INSTALLED_MODULES) -> list[CrmModule]:
    modules: list[CrmModule] = []
    seen: set[str] = set()
    for path in paths:
        mod = getattr(importlib.import_module(path), "module", None)
        if not isinstance(mod, CrmModule):
            raise TypeError(f"{path} must define `module = CrmModule(...)`")
        if mod.name in seen:
            raise ValueError(f"Duplicate module name: {mod.name}")
        seen.add(mod.name)
        if mod.models:
            importlib.import_module(mod.models)
        modules.append(mod)
    return modules
