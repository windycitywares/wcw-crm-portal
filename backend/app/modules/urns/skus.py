"""SKU templates: the owner's format with variables, rendered for a variation and read back from a SKU.

    WCW-{supplier:3}-{urn:4}-{sizes}{-option}   →   WCW-007-0345-10x1-3x3

Variables: {supplier:N} the supplier's CRM id padded to N digits · {urn:N} the urn's id padded to N digits ·
{sizes} each size in the variation (in the sizes list's order) written with the size format and joined with the
separator · {-option} an option code with its dash, empty until options are coded. Pure: no database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ETSY_MAX = 32
TOKEN = re.compile(r"\{(supplier|urn)(?::(\d))?\}|\{sizes\}|\{-option\}")
LITERAL = re.compile(r"^[A-Za-z0-9._-]*$")
SIZE_FORMAT_TOKENS = ("{code}", "{qty}")


class TemplateError(ValueError):
    pass


@dataclass(frozen=True)
class SkuFormat:
    template: str = "WCW-{supplier:3}-{urn:4}-{sizes}{-option}"
    size_format: str = "{code}x{qty}"
    separator: str = "-"


def _literals(text: str) -> list[str]:
    return [p for p in TOKEN.split(text) if p not in (None, "supplier", "urn") and not (p or "").isdigit()]


def check(fmt: SkuFormat, *, size_codes: list[str], max_supplier: int = 999, max_urn: int = 9999) -> list[str]:
    """Problems with a format, in words. Empty when it can be saved."""
    problems: list[str] = []
    t = fmt.template.strip()
    if not t:
        return ["The template can't be empty."]
    names = [m.group(0) for m in TOKEN.finditer(t)]
    leftover = TOKEN.sub("", t)
    if "{" in leftover or "}" in leftover:
        problems.append("Unknown variable in the template. Use {supplier:N}, {urn:N}, {sizes} and {-option}.")
    if not LITERAL.match(leftover):
        problems.append("Outside the variables, use only letters, digits, dash, dot and underscore.")
    if not any(n.startswith("{urn") for n in names):
        problems.append("The template needs {urn:N}: without it two urns could get the same SKU.")
    if "{sizes}" not in names:
        problems.append("The template needs {sizes}: without it two variations could get the same SKU.")
    if not any(n.startswith("{supplier") for n in names):
        problems.append("The template needs {supplier:N}.")
    for n in names:
        if len([x for x in names if x == n]) > 1:
            problems.append(f"{n} appears twice.")
            break
    if not all(tok in fmt.size_format for tok in SIZE_FORMAT_TOKENS):
        problems.append("The size format needs both {code} and {qty}, e.g. {code}x{qty}.")
    elif not LITERAL.match(fmt.size_format.replace("{code}", "").replace("{qty}", "")) or \
            fmt.size_format.replace("{code}", "").replace("{qty}", "") == "":
        problems.append("Put a letter or symbol between {code} and {qty} in the size format, e.g. x.")
    if not fmt.separator or not LITERAL.match(fmt.separator):
        problems.append("The size separator must be a dash, dot, underscore, letter or digit.")
    for m in TOKEN.finditer(t):
        if m.group(1) and not m.group(2):
            problems.append(f"Say how many digits for {{{m.group(1)}}}, e.g. {{{m.group(1)}:3}}.")
    if problems:
        return problems
    widths = {m.group(1): int(m.group(2)) for m in TOKEN.finditer(t) if m.group(1)}
    if len(str(max_supplier)) > widths["supplier"]:
        problems.append(f"Supplier #{max_supplier} needs {len(str(max_supplier))} digits: raise {{supplier:{widths['supplier']}}}.")
    if len(str(max_urn)) > widths["urn"]:
        problems.append(f"Urn #{max_urn} needs {len(str(max_urn))} digits: raise {{urn:{widths['urn']}}}.")
    sample = render(fmt, supplier_id=max_supplier, urn_id=max_urn,
                    sizes=[(c, 9) for c in size_codes[:2]] or [("10", 9)], option="XXX")
    if len(sample) > ETSY_MAX:
        problems.append(f"A long SKU would be {len(sample)} characters ({sample}); Etsy allows {ETSY_MAX}.")
    return problems


def render(fmt: SkuFormat, *, supplier_id: int, urn_id: int, sizes: list[tuple[str, int]],
           option: str | None = None) -> str:
    """The SKU for a variation. `sizes` is [(code, qty)] in the sizes list's order; zero quantities are left out."""
    parts = [fmt.size_format.replace("{code}", code).replace("{qty}", str(qty)) for code, qty in sizes if qty > 0]

    def sub(m: re.Match[str]) -> str:
        if m.group(1) == "supplier":
            return str(supplier_id).zfill(int(m.group(2) or 1))
        if m.group(1) == "urn":
            return str(urn_id).zfill(int(m.group(2) or 1))
        if m.group(0) == "{sizes}":
            return fmt.separator.join(parts)
        return f"-{option}" if option else ""

    return TOKEN.sub(sub, fmt.template.strip())


def reader(fmt: SkuFormat, size_codes: list[str]) -> re.Pattern[str]:
    """A pattern that reads a SKU written in this format back into supplier, urn, sizes and option."""
    out, pos = "", 0
    t = fmt.template.strip()
    for m in TOKEN.finditer(t):
        out += re.escape(t[pos:m.start()])
        if m.group(1):
            out += rf"(?P<{m.group(1)}>\d+)"
        elif m.group(0) == "{sizes}":
            out += r"(?P<sizes>.+?)"
        else:
            out += r"(?:-(?P<option>[A-Za-z][A-Za-z0-9]*))?"
        pos = m.end()
    out += re.escape(t[pos:])
    return re.compile(f"^{out}$", re.IGNORECASE)


def read(fmt: SkuFormat, sku: str, size_codes: list[str]) -> dict | None:
    """{"supplier": 7, "urn": 345, "sizes": {"10": 1, "3": 3}, "option": None} or None when it isn't one of ours."""
    m = reader(fmt, size_codes).match((sku or "").strip())
    if not m:
        return None
    one = re.compile("^" + re.escape(fmt.size_format).replace(re.escape("{code}"), r"(?P<code>[A-Za-z0-9.]+?)")
                     .replace(re.escape("{qty}"), r"(?P<qty>\d+)") + "$", re.IGNORECASE)
    sizes: dict[str, int] = {}
    for piece in m.group("sizes").split(fmt.separator):
        pm = one.match(piece)
        if not pm or pm.group("code") not in size_codes:
            return None
        sizes[pm.group("code")] = sizes.get(pm.group("code"), 0) + int(pm.group("qty"))
    return {"supplier": int(m.group("supplier")), "urn": int(m.group("urn")), "sizes": sizes,
            "option": m.groupdict().get("option")}
