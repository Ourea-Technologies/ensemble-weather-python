"""Optional pandas views of a forecast. Imported only when asked for."""

from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING, Any

from ._decode import encode

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pandas as pd

    from .models import DailyForecast, TimeSeriesPoint

_STATS = ("mean", "p10", "p25", "p50", "p75", "p90", "min", "max", "probability")


def _pandas() -> Any:  # noqa: ANN401 - the optional module
    try:
        import pandas  # noqa: ICN001, PLC0415 - optional, imported on use
    except ImportError as exc:  # pragma: no cover - exercised without pandas
        msg = "to_dataframe() needs pandas: pip install 'ensemble-weather[pandas]'"
        raise ImportError(msg) from exc
    return pandas


def _flatten(prefix: str, value: object, row: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, inner in value.items():
            _flatten(f"{prefix}.{key}" if prefix else key, inner, row)
    elif not isinstance(value, list):
        row[prefix] = value


def hourly_frame(points: Sequence[TimeSeriesPoint]) -> pd.DataFrame:
    """One row per hour; ``ensemble`` statistics as ``<variable>.<stat>`` columns."""
    pandas = _pandas()
    rows = []
    for point in points:
        row: dict[str, Any] = {
            "valid_time": point.valid_time,
            "lead_time_hours": point.lead_time_hours,
            "is_night": point.is_night,
            "condition": point.condition.value,
        }
        for f in fields(point.ensemble):
            quantiles = getattr(point.ensemble, f.name)
            if quantiles is None or not hasattr(quantiles, "p50"):
                continue
            for stat in _STATS:
                value = getattr(quantiles, stat)
                if value is not None:
                    row[f"{f.name}.{stat}"] = value
        rows.append(row)
    frame: pd.DataFrame = pandas.DataFrame(rows)
    return frame.set_index("valid_time") if rows else frame


def daily_frame(days: Sequence[DailyForecast]) -> pd.DataFrame:
    """One row per date; nested fields flattened to dotted column names."""
    pandas = _pandas()
    rows = []
    for day in days:
        row: dict[str, Any] = {}
        _flatten("", encode(day), row)
        row["date"] = day.date
        rows.append(row)
    frame: pd.DataFrame = pandas.DataFrame(rows)
    return frame.set_index("date") if rows else frame
