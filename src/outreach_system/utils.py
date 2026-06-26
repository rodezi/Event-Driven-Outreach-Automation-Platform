from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")


def mask_email(value: str | None) -> str:
    if not value or "@" not in value:
        return "<missing>"
    local, domain = value.split("@", 1)
    masked_local = f"{local[:1]}*" if len(local) <= 2 else f"{local[:2]}***"
    return f"{masked_local}@{domain}"


def unique_preserving_order(values: Iterable[T]) -> list[T]:
    seen: set[T] = set()
    result: list[T] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
