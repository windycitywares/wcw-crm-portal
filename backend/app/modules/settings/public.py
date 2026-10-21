"""Public side of settings: test-mode status (no login needed)."""

from fastapi import APIRouter, Response

from app.core.database import engine
from app.services.testenv import TestEnvironment

router = APIRouter(prefix="/environment", tags=["environment"])


@router.get("")
async def environment(response: Response) -> dict[str, bool]:
    """Whether the CRM is running on test data, so every page can say so. Public: holds nothing secret."""
    response.headers["Cache-Control"] = "no-store"
    status = await TestEnvironment(engine).status()
    return {"test": status["effective"] == "test"}
