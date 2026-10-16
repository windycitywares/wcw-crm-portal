"""Pydantic types shared by several modules."""

import re
from typing import Annotated

from pydantic import AfterValidator

_COLOR = re.compile(r"^(#[0-9a-fA-F]{6}|neutral|accent|success|warning|danger|info)$")


def _color(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if not _COLOR.match(value):
        raise ValueError("Use #rrggbb or one of neutral, accent, success, warning, danger, info")
    return value


# A display colour: a theme tone name (rendered with the UI's tokens) or #rrggbb.
Color = Annotated[str | None, AfterValidator(_color)]
