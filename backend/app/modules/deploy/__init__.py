"""Admin → Deployments: pause/resume, schedule, "Deploy now", versions and the deploy log."""

from app.modules import CrmModule

from .router import router

module = CrmModule(name="deploy", router=router, models="app.modules.deploy.models")
