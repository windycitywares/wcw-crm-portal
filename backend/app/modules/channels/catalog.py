"""The marketplaces the CRM knows. Only those with `available=True` can be connected today; the rest show as
"coming later" in Settings → Sales channels and in the sidebar's External shops group once connected."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Channel:
    key: str
    label: str
    available: bool


CHANNELS: dict[str, Channel] = {c.key: c for c in (
    Channel("etsy", "Etsy", True),
    Channel("amazon", "Amazon", False),
    Channel("walmart", "Walmart", False),
)}
