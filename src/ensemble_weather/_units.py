"""Unit handling for the caller's threshold input (BEHAVIOR 4 and 7).

Only the caller's *input* is converted, with exact factors. Response values
are never converted: to get other units, ask the server for them.
"""

from __future__ import annotations

import math

from .enums import Unit, UnitSystem, Variable
from .errors import UsageError

_DEPTH, _TEMPERATURE, _HEIGHT, _SPEED = "depth", "temperature", "height", "speed"

_UNIT_KIND = {
    Unit.MM: _DEPTH,
    Unit.IN: _DEPTH,
    Unit.DEG_C: _TEMPERATURE,
    Unit.DEG_F: _TEMPERATURE,
    Unit.K: _TEMPERATURE,
    Unit.M: _HEIGHT,
    Unit.FT: _HEIGHT,
    Unit.M_PER_S: _SPEED,
    Unit.MPH: _SPEED,
}

_VARIABLE_KIND = {
    Variable.PRECIPITATION: _DEPTH,
    Variable.SNOWFALL: _DEPTH,
    Variable.TEMPERATURE: _TEMPERATURE,
    Variable.SNOW_LEVEL: _HEIGHT,
    Variable.WIND_SPEED: _SPEED,
}

_SYSTEM_UNIT = {
    UnitSystem.METRIC: {
        _DEPTH: Unit.MM,
        _TEMPERATURE: Unit.DEG_C,
        _HEIGHT: Unit.M,
        _SPEED: Unit.M_PER_S,
    },
    UnitSystem.IMPERIAL: {
        _DEPTH: Unit.IN,
        _TEMPERATURE: Unit.DEG_F,
        _HEIGHT: Unit.FT,
        _SPEED: Unit.MPH,
    },
    UnitSystem.KELVIN: {
        _DEPTH: Unit.MM,
        _TEMPERATURE: Unit.K,
        _HEIGHT: Unit.M,
        _SPEED: Unit.M_PER_S,
    },
}

# Exact factors to the metric unit of each kind (BEHAVIOR 7).
_TO_METRIC = {Unit.IN: 25.4, Unit.FT: 0.3048, Unit.MPH: 0.44704}


def check_unit(variable: Variable, unit: Unit) -> None:
    """Raise :class:`UsageError` if ``unit`` cannot measure ``variable``."""
    if _UNIT_KIND[unit] != _VARIABLE_KIND[variable]:
        raise UsageError(f"{variable.value} cannot be given in {unit.value}")


def request_unit(variable: Variable, units: UnitSystem) -> Unit:
    """The unit the server reads ``variable`` thresholds in, for ``units``."""
    return _SYSTEM_UNIT[units][_VARIABLE_KIND[variable]]


def convert(value: float, source: Unit, target: Unit) -> float:
    """Convert a caller's threshold between two units of the same kind."""
    if source == target:
        return value
    if _UNIT_KIND[source] == _TEMPERATURE:
        celsius = value
        if source == Unit.DEG_F:
            celsius = (value - 32) * 5 / 9
        elif source == Unit.K:
            celsius = value - 273.15
        if target == Unit.DEG_F:
            return celsius * 9 / 5 + 32
        if target == Unit.K:
            return celsius + 273.15
        return celsius
    metric = value * _TO_METRIC.get(source, 1.0)
    return metric / _TO_METRIC.get(target, 1.0)


def precision(variable: Variable, units: UnitSystem) -> int:
    """The number of decimals the server serves ``variable`` at."""
    if variable in {Variable.PRECIPITATION, Variable.SNOWFALL}:
        return 3 if units == UnitSystem.IMPERIAL else 2
    if variable == Variable.SNOW_LEVEL:
        return 0
    return 1


def format_rounded(value: float, decimals: int) -> str:
    """Round half away from zero on ``value * 10**decimals`` and print it.

    This is the server's own rounding, in IEEE-754 doubles: 0.0625 at 3
    decimals is ``0.063`` (banker's rounding would give 0.062), and 1.005 at
    2 decimals is ``1.00`` because 1.005 * 100 is 100.4999... A negative zero
    prints as ``0``. Python's :func:`round` is banker's rounding, so it is not
    used here.
    """
    if not math.isfinite(value):
        raise UsageError(f"threshold must be finite, got {value!r}")
    scaled = value * 10**decimals
    whole = math.trunc(scaled)
    if abs(scaled - whole) >= 0.5:
        whole += 1 if scaled > 0 else -1
    number = int(whole)
    if decimals == 0:
        return str(number)
    digits = str(abs(number)).rjust(decimals + 1, "0")
    sign = "-" if number < 0 else ""
    return f"{sign}{digits[:-decimals]}.{digits[-decimals:]}"
