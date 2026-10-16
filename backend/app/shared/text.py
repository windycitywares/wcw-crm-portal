"""Small text helpers shared by modules."""

import re
import unicodedata


def slugify(label: str, max_len: int = 60) -> str:
    """"Marketplace (Etsy/Amazon)" → "marketplace_etsy_amazon" (ASCII, lower case, underscores)."""
    ascii_ = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_.lower()).strip("_")
    return slug[:max_len] or "value"
