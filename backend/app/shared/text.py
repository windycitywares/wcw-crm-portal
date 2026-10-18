"""Small text helpers shared by modules."""

import re
import unicodedata


def slugify(label: str, max_len: int = 60) -> str:
    """"Marketplace (Etsy/Amazon)" → "marketplace_etsy_amazon" (ASCII, lower case, underscores)."""
    ascii_ = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_.lower()).strip("_")
    return slug[:max_len] or "value"


def phone_digits(value: str | None) -> str:
    """The digits of a phone number, so one number written two ways is one number.

    "(312) 555-0142", "+1 312 555 0142" and "13125550142" all come out "3125550142": punctuation goes, and
    so does the country code in front of a North-American number, because the shop writes down the number a
    customer typed while a text gateway sends E.164. Nothing else is dropped — a wrong match is worse than a
    missing one — so the "1" only goes when it is what stands in front of ten other digits.
    """
    digits = re.sub(r"\D+", "", value or "")
    return digits[1:] if len(digits) == 11 and digits.startswith("1") else digits
