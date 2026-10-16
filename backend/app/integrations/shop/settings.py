from pydantic import BaseModel, Field, model_validator

DEFAULT_SHOP_API = "https://api.windycitywares.com/api/v1"


class ShopSettings(BaseModel):
    """Admin → Settings → Integrations → Shop."""

    enabled: bool = False
    webhook_secret: str = Field(default="", max_length=200)  # secret, shared with the shop (CRM_WEBHOOK_SECRET there)
    shop_api_url: str = Field(default=DEFAULT_SHOP_API, max_length=300)
    shop_api_token: str = Field(default="", max_length=500)  # secret, for reading orders (batch 5)

    @model_validator(mode="after")
    def _check(self) -> "ShopSettings":
        if self.webhook_secret and len(self.webhook_secret) < 32:
            raise ValueError("The webhook secret must be at least 32 characters (use Generate)")
        if self.shop_api_url and not self.shop_api_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError("The shop API address must start with https://")
        if self.enabled and not self.webhook_secret:
            raise ValueError("To turn the shop connection on, set the webhook secret")
        return self


SECRETS = ("webhook_secret", "shop_api_token")
