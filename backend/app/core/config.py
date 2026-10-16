"""Application settings, loaded from environment variables and env files (see ENV_FILES).

Only infrastructure lives here (database, secrets, URLs). Business settings that staff change at run time
(campaign sender, SMTP account, send limits, business hours …) are stored in the database and edited in
Admin → Settings — see SPEC §9.
"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _is_production() -> bool:
    env = os.environ.get("ENVIRONMENT")
    if env is None:
        try:
            for line in (BACKEND_DIR / ".env").read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("ENVIRONMENT="):
                    env = line.split("=", 1)[1].strip().strip("'\"")
        except OSError:
            pass
    return (env or "").lower() == "production"


ENV_FILES = (
    *((BACKEND_DIR / "production.env",) if _is_production() else ()),
    BACKEND_DIR / ".env",
)


class Settings(BaseSettings):
    # Absolute paths: Passenger may start the app from a different working directory.
    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Windy City Wares CRM API"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://wcw:wcw@localhost:5432/wcw_crm"
    db_echo: bool = False
    db_use_null_pool: bool = False  # true on Passenger: processes come and go
    db_connect_timeout: int = 10  # seconds; fail fast instead of hanging a web worker

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # one working day

    # Key for secrets stored in the database (e.g. the SMTP password in Admin → Settings → Email).
    # A Fernet key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    data_encryption_key: str | None = None

    cors_origins: list[str] = ["http://localhost:3000"]

    # The CRM web app (used for links in emails, e.g. password reset).
    site_url: str = "http://localhost:3000"

    # Admin → Deployments: where the server keeps the checkout, the web app and the deploy log.
    deploy_repo_dir: str = str(BACKEND_DIR.parent)
    web_app_dir: str = str(Path.home() / "apps" / "crm" / "wcw-crm-web")
    deploy_log: str = str(Path.home() / "logs" / "wcw-crm-deploy.log")

    # First admin account, created by `python -m app.seed` when no admin exists.
    admin_email: str | None = None
    admin_password: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if self.is_production:
            if self.jwt_secret == "change-me" or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a long random value in production")
            if not self.data_encryption_key:
                raise ValueError("DATA_ENCRYPTION_KEY must be set in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
