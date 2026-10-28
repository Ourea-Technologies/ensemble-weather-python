"""Canonical request URLs (BEHAVIOR 3.1): one request, one edge-cache entry.

* a parameter the caller did not set, or set to its default, is omitted;
* parameters are sorted by name and each appears once;
* a comma list (``sources``, ``include``, ``network``, ``capability``, ...) is
  sorted and de-duplicated, its items joined by a literal ``,``;
* values are RFC 3986 percent-encoded (space as ``%20``, uppercase hex), except
  that ``prob`` and ``totals`` keep ``:`` and ``,`` literal and comma lists
  keep their separating ``,``;
* numbers are the shortest decimal that round-trips, never an exponent.
"""

from __future__ import annotations

import datetime as dt
import math
from decimal import Decimal
from typing import TYPE_CHECKING
from urllib.parse import quote

from ._decode import format_datetime
from .enums import OpenEnum
from .errors import UsageError

if TYPE_CHECKING:
    from collections.abc import Sequence

Scalar = str | int | float | bool | OpenEnum | dt.datetime


def encode_component(value: str) -> str:
    """Percent-encode one path segment or query value (RFC 3986 unreserved kept)."""
    return quote(value, safe="")


def format_number(value: float) -> str:
    """The shortest decimal that round-trips, without an exponent.

    An integral float prints without ``.0`` (``1661.0`` -> ``1661``), as every
    other SDK prints it, so the URL is the same cache key everywhere.
    """
    if isinstance(value, bool):
        raise UsageError(f"expected a number, got {value!r}")
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise UsageError(f"expected a finite number, got {value!r}")
    if value.is_integer() and abs(value) < 1e21:
        return str(int(value))
    text = repr(value)
    if "e" in text or "E" in text:
        text = str(format(Decimal(text), "f"))
    return text


def format_value(value: Scalar) -> str:
    """Format one query value (before percent-encoding)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, OpenEnum):
        return str(value.value)
    if isinstance(value, str):
        return value
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            raise UsageError("datetimes must be timezone-aware (for example UTC)")
        return format_datetime(value.astimezone(dt.timezone.utc))
    return format_number(value)


class Query:
    """Collects a request's parameters and renders the canonical query string."""

    def __init__(self) -> None:
        """Start an empty query."""
        self._params: dict[str, list[str]] = {}
        self._raw: set[str] = set()

    def add(self, name: str, value: Scalar | None, default: Scalar | None = None) -> None:
        """Add ``name=value`` unless ``value`` is unset or equals ``default``."""
        if value is None:
            return
        if default is not None and format_value(value) == format_value(default):
            return
        self._params[name] = [format_value(value)]

    def add_list(self, name: str, values: Sequence[str] | str | None) -> None:
        """Add a comma list, sorted, de-duplicated and joined by a literal ``,``.

        That is the server's canonical form; any other is a 301 (BEHAVIOR 3.1).
        """
        if values is None:
            return
        items = [values] if isinstance(values, str) else list(values)
        if items:
            self._params[name] = [",".join(encode_component(i) for i in sorted(set(items)))]
            self._raw.add(name)

    def add_raw(self, name: str, value: str) -> None:
        """Add a pre-built value sent without percent-encoding (``prob``, ``totals``)."""
        if value:
            self._params[name] = [value]
            self._raw.add(name)

    def render(self) -> str:
        """The query string, without ``?``, in canonical order."""
        parts = []
        for name in sorted(self._params):
            for value in self._params[name]:
                encoded = value if name in self._raw else encode_component(value)
                parts.append(f"{name}={encoded}")
        return "&".join(parts)
