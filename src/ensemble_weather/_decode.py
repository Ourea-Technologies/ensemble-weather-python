"""Turn JSON into the frozen dataclass models, and back.

The models declare their fields with ordinary type hints; this module reads
those hints, so there is one source of truth per schema. Unknown JSON fields
are ignored (BEHAVIOR 1.5), unknown enum values become the enum's UNKNOWN
pseudo-member, and an absent optional field becomes ``None``.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import re
import types
import typing
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")

JSON_NAME = "json_name"
"""Field metadata key: the JSON name when it differs from the attribute."""

NOT_JSON = "not_json"
"""Field metadata key: the field is set by the SDK, never read from JSON."""


class DecodeError(ValueError):
    """A response body did not match the model the SDK expected."""

    def __init__(self, path: str, problem: str) -> None:
        """Record where in the document the problem was."""
        super().__init__(f"{path}: {problem}")
        self.path = path


@dataclasses.dataclass(frozen=True)
class _Field:
    attr: str
    json: str
    type: Any
    required: bool


_FIELDS: dict[type[Any], tuple[_Field, ...]] = {}


def _fields(cls: type[Any]) -> tuple[_Field, ...]:
    known = _FIELDS.get(cls)
    if known is not None:
        return known
    hints = typing.get_type_hints(cls)
    out = []
    for f in dataclasses.fields(cls):
        if f.metadata.get(NOT_JSON):
            continue
        required = f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
        out.append(_Field(f.name, f.metadata.get(JSON_NAME, f.name), hints[f.name], required))
    _FIELDS[cls] = result = tuple(out)
    return result


_FRACTION = re.compile(r"\.(\d+)")


def parse_datetime(text: str) -> dt.datetime:
    """Parse an RFC 3339 timestamp, on every supported Python version."""
    value = text.strip()
    if value[-1:] in {"Z", "z"}:
        value = value[:-1] + "+00:00"
    # Python 3.10 only accepts 3 or 6 fractional digits.
    value = _FRACTION.sub(lambda m: "." + (m.group(1) + "000000")[:6], value, count=1)
    return dt.datetime.fromisoformat(value)


def format_datetime(value: dt.datetime) -> str:
    """Format a timestamp the way the API does (UTC as ``Z``)."""
    text = value.isoformat()
    return text[:-6] + "Z" if text.endswith("+00:00") else text


def decode(tp: Any, value: Any, path: str = "$") -> Any:  # noqa: C901, PLR0911, PLR0912, PLR0915
    """Decode ``value`` (parsed JSON) as type ``tp``."""
    if tp is Any:
        return value
    origin = typing.get_origin(tp)
    if origin is typing.Union or origin is types.UnionType:
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if value is None:
            if len(args) < len(typing.get_args(tp)):
                return None
            raise DecodeError(path, "is null")
        if len(args) == 1:
            return decode(args[0], value, path)
        errors = []
        for arg in args:
            try:
                return decode(arg, value, path)
            except DecodeError as exc:  # noqa: PERF203 - one try per alternative
                errors.append(str(exc))
        raise DecodeError(path, "matches no alternative: " + "; ".join(errors))
    if value is None:
        raise DecodeError(path, "is null")
    if origin is list:
        if not isinstance(value, list):
            raise DecodeError(path, f"expected an array, got {type(value).__name__}")
        (item,) = typing.get_args(tp)
        return [decode(item, v, f"{path}[{i}]") for i, v in enumerate(value)]
    if origin is dict:
        if not isinstance(value, dict):
            raise DecodeError(path, f"expected an object, got {type(value).__name__}")
        _, item = typing.get_args(tp)
        return {k: decode(item, v, f"{path}.{k}") for k, v in value.items()}
    if not isinstance(tp, type):
        raise DecodeError(path, f"unsupported type {tp!r}")
    if dataclasses.is_dataclass(tp):
        return decode_model(tp, value, path)
    if issubclass(tp, Enum):
        if not isinstance(value, str):
            raise DecodeError(path, f"expected a string, got {type(value).__name__}")
        return tp(value)
    if tp is bool:
        if not isinstance(value, bool):
            raise DecodeError(path, f"expected a boolean, got {type(value).__name__}")
        return value
    if tp is int:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DecodeError(path, f"expected an integer, got {type(value).__name__}")
        if isinstance(value, float):
            if not value.is_integer():
                raise DecodeError(path, f"expected an integer, got {value!r}")
            return int(value)
        return value
    if tp is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DecodeError(path, f"expected a number, got {type(value).__name__}")
        return float(value)
    if tp is str:
        if not isinstance(value, str):
            raise DecodeError(path, f"expected a string, got {type(value).__name__}")
        return value
    if tp is dt.datetime or tp is dt.date:
        if not isinstance(value, str):
            raise DecodeError(path, f"expected a string, got {type(value).__name__}")
        try:
            return parse_datetime(value) if tp is dt.datetime else dt.date.fromisoformat(value)
        except ValueError as exc:
            raise DecodeError(path, f"not a valid {tp.__name__}: {value!r}") from exc
    raise DecodeError(path, f"unsupported type {tp!r}")


def decode_model(cls: type[T], value: Any, path: str = "$") -> T:
    """Decode a JSON object as the dataclass ``cls``."""
    if not isinstance(value, dict):
        raise DecodeError(path, f"expected an object, got {type(value).__name__}")
    kwargs: dict[str, Any] = {}
    for f in _fields(cls):
        if f.json in value:
            kwargs[f.attr] = decode(f.type, value[f.json], f"{path}.{f.json}")
        elif f.required:
            raise DecodeError(path, f"missing required field {f.json!r}")
    return cls(**kwargs)


def encode(value: Any) -> Any:  # noqa: PLR0911
    """Turn a model (or anything inside one) back into JSON-compatible data.

    Fields that are ``None`` are left out.
    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        out: dict[str, Any] = {}
        for f in _fields(type(value)):
            v = getattr(value, f.attr)
            if v is not None:
                out[f.json] = encode(v)
        return out
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dt.datetime):
        return format_datetime(value)
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, list):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    return value
