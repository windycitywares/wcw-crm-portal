"""Was this page's help useful? A thumbs up or down, with an optional comment, kept per guide so the pages
people find confusing can be rewritten (Settings → Help feedback)."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="help", router=router, models="app.modules.help.models")
