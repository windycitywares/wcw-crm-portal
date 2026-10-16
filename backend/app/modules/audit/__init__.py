"""Audit log: append-only history of changes and security events (SPEC §3.1)."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="audit", router=router, models="app.modules.audit.models")
