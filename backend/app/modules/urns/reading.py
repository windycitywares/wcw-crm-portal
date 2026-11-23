"""Read how many pieces of each size an Etsy variation holds, from its words.

    "10 inch Large"                 → {"10": 1}
    "Set of 4 Keepsakes (3 inch)"   → {"3": 4}
    "10 inch + 2 Keepsakes"         → {"10": 1, "3": 2}

Every size has aliases (its own "10 inch", "10in", 10" … plus words like "large" or "keepsake" the owner adds in
Settings → Sizes). A part of the text in which no size is found makes the result `clear=False`, so the review
table asks a person instead of guessing. Pure: no database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

WORDS = {"one": 1, "single": 1, "two": 2, "pair": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "twelve": 12}
SPLIT = re.compile(r"\s*(?:\+|&|,|;|/|\band\b|\bwith\b|\bplus\b)\s*", re.IGNORECASE)
INCH = r"(?:\s*(?:inch(?:es)?|in\b|\"|”|″|''))"
COUNT = (
    re.compile(r"\b(?:set|pack|lot|bundle)\s+of\s+(\d+|[a-z]+)\b"),
    re.compile(r"\b(\d+)\s*(?:x|pcs?|pieces?|count|ct)\b"),
    re.compile(r"\bx\s*(\d+)\b"),
    re.compile(r"\b(\d+|[a-z]+)\s+(?:mini\s+|small\s+|large\s+)?(?:keepsakes?|urns?|pieces?|minis?|tokens?)\b"),
    re.compile(r"\bqty\s*:?\s*(\d+)\b"),
)


@dataclass(frozen=True)
class Size:
    code: str
    aliases: tuple[str, ...] = ()


@dataclass
class Reading:
    quantities: dict[str, int] = field(default_factory=dict)
    clear: bool = False
    note: str | None = None


def _num(token: str) -> int | None:
    if token.isdigit():
        n = int(token)
        return n if 0 < n <= 500 else None
    return WORDS.get(token)


def _patterns(size: Size) -> list[re.Pattern[str]]:
    words = sorted({a.strip().lower() for a in size.aliases if a.strip()}, key=len, reverse=True)
    pats = [re.compile(rf"(?<![\d.]){re.escape(size.code)}{INCH}", re.IGNORECASE)]
    pats += [re.compile(rf"(?<![\w]){re.escape(w)}(?![\w])", re.IGNORECASE) for w in words]
    return pats


def read(text: str, sizes: list[Size]) -> Reading:
    raw = (text or "").strip()
    if not raw:
        return Reading(note="No words to read")
    compiled = [(s, _patterns(s)) for s in sizes]
    found: dict[str, int] = {}
    unread: list[str] = []
    for part in [p for p in SPLIT.split(raw.lower()) if p.strip()]:
        hits = [(s, pat) for s, pats in compiled for pat in pats if pat.search(part)]
        codes = {s.code for s, _ in hits}
        if len(codes) != 1:
            if len(codes) > 1:
                unread.append(f"“{part.strip()}” names more than one size")
            elif re.search(r"\d", part) or len(SPLIT.split(raw)) > 1:
                unread.append(f"no size found in “{part.strip()}”")
            continue
        code = codes.pop()
        size = next(s for s, _ in hits)
        rest = _patterns(size)[0].sub(" ", part)  # take "10 inch" out so it isn't read as ten pieces
        counts = list(COUNT) + [re.compile(rf"\b(\d+|[a-z]+)\s+(?:[a-z]+\s+)?{re.escape(a.lower())}\b")
                                for a in size.aliases if a.strip()]
        qty = None
        for c in counts:
            m = c.search(rest)
            if m and _num(m.group(1)):
                qty = _num(m.group(1))
                break
        if qty is None and code in found:  # "Rose Keepsake, 3 inch": the same size said twice, not two pieces
            continue
        found[code] = found.get(code, 0) + (qty or 1)
    if not found:
        return Reading(note=unread[0] if unread else "No size found")
    return Reading(quantities=found, clear=not unread, note="; ".join(unread) or None)


def short_name(title: str, limit: int = 80) -> str:
    """A urn name from an Etsy title: the part before the first separator, trimmed."""
    t = (title or "").strip()
    cuts = [t.find(sep) for sep in (" | ", " – ", " — ", " - ", ", ", ": ") if t.find(sep) >= 8]
    if cuts:
        t = t[:min(cuts)].strip()
    return t[:limit].rstrip(" -,") or "Urn"


def options_key(options: dict | list | None) -> str:
    """One stable key for a variation's choices ({"Size": "10 inch"} or [{"name", "value"}]); "" for none."""
    if isinstance(options, list):
        pairs = [((o.get("name") or "").strip(), (o.get("value") or "").strip()) for o in options if isinstance(o, dict)]
    elif isinstance(options, dict):
        pairs = [(str(k or "").strip(), str(v or "").strip()) for k, v in options.items()]
    else:
        pairs = []
    pairs = sorted((k.lower(), v.lower()) for k, v in pairs if k or v)
    return "|".join(f"{k}={v}" for k, v in pairs)[:400]


def options_label(options: dict | None) -> str:
    if not options:
        return ""
    return " · ".join(f"{v}" if len(options) == 1 else f"{k}: {v}" for k, v in options.items())
