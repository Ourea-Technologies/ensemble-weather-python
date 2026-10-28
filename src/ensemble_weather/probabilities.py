"""Probability terms (``prob=``) and window totals (``totals=``).

The server computes every probability and every window total from the full
ensemble. This module only *describes* what to ask for; it never derives a
probability from quantiles or sums hourly values (that gives wrong answers:
per-hour quantiles do not add up to a window total).

Examples:
    >>> from ensemble_weather import Chance, Total, Window
    >>> snow = Chance.at_least("snowfall", 6, "in")  # P(0-24 h snowfall >= 6 in)
    >>> freeze = Chance.at_most("temperature", 32, "degF", window=Window(6, 18), aggregation="all")
    >>> storm = Total("snowfall", window=72)  # the 0-72 h storm-total distribution
    >>> storm.window.to_query()
    '72h'
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from ._units import check_unit, convert, format_rounded, precision, request_unit
from .enums import Aggregation, Op, OpenEnum, TotalVariable, Unit, UnitSystem, Variable
from .errors import UsageError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["MAX_WINDOW_HOURS", "Chance", "Total", "Window", "WindowLike"]

MAX_WINDOW_HOURS = 360
"""The furthest hour a window may end at."""

_AMOUNTS = frozenset({Variable.PRECIPITATION, Variable.SNOWFALL})
_OP_ORDER = {Op.GE: 0, Op.LE: 1}
_AGGREGATION_ORDER = {Aggregation.TOTAL: 0, Aggregation.ANY: 1, Aggregation.ALL: 2}


@dataclass(frozen=True)
class Window:
    """Hours ``start`` to ``end`` from the forecast's first served hour.

    ``Window(0, 24)`` (or just ``24`` wherever a window is accepted) is the
    first 24 hours. The end may be at most 360.
    """

    start: int = 0
    end: int = 24

    def __post_init__(self) -> None:
        """Validate the bounds."""
        for name, value in (("start", self.start), ("end", self.end)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise UsageError(f"window {name} must be a whole number of hours, got {value!r}")
        if not 0 <= self.start < self.end <= MAX_WINDOW_HOURS:
            raise UsageError(
                f"window must satisfy 0 <= start < end <= {MAX_WINDOW_HOURS}, "
                f"got {self.start}-{self.end} h"
            )

    @property
    def hours(self) -> int:
        """The window's length in hours."""
        return self.end - self.start

    def to_query(self) -> str:
        """The wire form: ``24h``, or ``6-18h`` when it does not start at 0."""
        return f"{self.end}h" if self.start == 0 else f"{self.start}-{self.end}h"


WindowLike = int | Window | tuple[int, int]
"""A :class:`Window`, an end hour (``24`` is hours 0-24) or a ``(start, end)`` pair."""


def _window(value: WindowLike) -> Window:
    if isinstance(value, Window):
        return value
    if isinstance(value, tuple):
        start, end = value
        return Window(start, end)
    return Window(0, value)


E = TypeVar("E", bound=OpenEnum)


def _member(cls: type[E], value: object) -> E:
    try:
        member: E | None = cls(value)
    except ValueError:
        member = None
    if member is None or member.is_unknown:
        allowed = ", ".join(m.value for m in cls)
        raise UsageError(f"{value!r} is not a valid {cls.__name__}; expected one of {allowed}")
    return member


@dataclass(frozen=True, init=False)
class Chance:
    """One probability term: the chance that ``variable`` ``op`` ``threshold``.

    Attributes:
        variable: What to ask about.
        op: ``ge`` (at least) or ``le`` (at most).
        threshold: The threshold. With ``unit``, the SDK converts it to the
            request's units (exact factors); without, it is already in them.
        unit: The threshold's unit, or ``None`` for the request's units.
        window: The hours the term covers (default 0-24 h).
        aggregation: ``total`` for precipitation and snowfall (their only,
            default, choice); ``any`` (default) or ``all`` for the others.
            ``None`` means the variable's default.
    """

    variable: Variable
    op: Op
    threshold: float
    unit: Unit | None
    window: Window
    aggregation: Aggregation | None

    def __init__(
        self,
        variable: Variable | str,
        op: Op | str,
        threshold: float,
        unit: Unit | str | None = None,
        *,
        window: WindowLike = 24,
        aggregation: Aggregation | str | None = None,
    ) -> None:
        """Build and validate a term. Prefer :meth:`at_least` / :meth:`at_most`."""
        var = _member(Variable, variable)
        oper = _member(Op, op)
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise UsageError(f"threshold must be a number, got {threshold!r}")
        if not math.isfinite(threshold):
            raise UsageError(f"threshold must be finite, got {threshold!r}")
        unit_member: Unit | None = None
        if unit is not None:
            unit_member = _member(Unit, unit)
            check_unit(var, unit_member)
        agg: Aggregation | None = None
        if aggregation is not None:
            agg = _member(Aggregation, aggregation)
            if var in _AMOUNTS and agg != Aggregation.TOTAL:
                raise UsageError(
                    f"{var.value} supports only aggregation 'total', not {agg.value!r}"
                )
            if var not in _AMOUNTS and agg == Aggregation.TOTAL:
                raise UsageError(f"{var.value} supports aggregation 'any' or 'all', not 'total'")
        object.__setattr__(self, "variable", var)
        object.__setattr__(self, "op", oper)
        object.__setattr__(self, "threshold", threshold)
        object.__setattr__(self, "unit", unit_member)
        object.__setattr__(self, "window", _window(window))
        object.__setattr__(self, "aggregation", agg)

    @classmethod
    def at_least(
        cls,
        variable: Variable | str,
        threshold: float,
        unit: Unit | str | None = None,
        *,
        window: WindowLike = 24,
        aggregation: Aggregation | str | None = None,
    ) -> Chance:
        """The chance that ``variable`` is at least ``threshold`` (``ge``)."""
        return cls(variable, Op.GE, threshold, unit, window=window, aggregation=aggregation)

    @classmethod
    def at_most(
        cls,
        variable: Variable | str,
        threshold: float,
        unit: Unit | str | None = None,
        *,
        window: WindowLike = 24,
        aggregation: Aggregation | str | None = None,
    ) -> Chance:
        """The chance that ``variable`` is at most ``threshold`` (``le``)."""
        return cls(variable, Op.LE, threshold, unit, window=window, aggregation=aggregation)

    @property
    def effective_aggregation(self) -> Aggregation:
        """The aggregation the server applies (the variable's default if unset)."""
        if self.aggregation is not None:
            return self.aggregation
        return Aggregation.TOTAL if self.variable in _AMOUNTS else Aggregation.ANY

    def __repr__(self) -> str:
        """Return a compact, readable representation."""
        agg = None if self.aggregation is None else self.aggregation.value
        unit = None if self.unit is None else self.unit.value
        return (
            f"Chance(variable={self.variable.value!r}, op={self.op.value!r}, "
            f"threshold={self.threshold!r}, unit={unit!r}, window={self.window!r}, "
            f"aggregation={agg!r})"
        )


@dataclass(frozen=True, init=False)
class Total:
    """One window total: the distribution of each member's total over a window.

    This is the only storm total the SDK offers. Never add up hourly
    quantiles instead: the sum of per-hour medians is not the median total.
    """

    variable: TotalVariable
    window: Window

    def __init__(self, variable: TotalVariable | str, window: WindowLike = 24) -> None:
        """Build and validate a window-total request."""
        var = _member(TotalVariable, variable)
        object.__setattr__(self, "variable", var)
        object.__setattr__(self, "window", _window(window))

    def __repr__(self) -> str:
        """Return a compact, readable representation."""
        return f"Total(variable={self.variable.value!r}, window={self.window!r})"


# --- wire form ---------------------------------------------------------------

ChanceKey = tuple[str, str, str, int, int, str]
TotalKey = tuple[str, int, int]


def chance_key(chance: Chance, units: UnitSystem) -> ChanceKey:
    """The identity of a term as the server sees it, for ``units``.

    Two terms with the same key are one term on the wire and share a result.
    """
    target = request_unit(chance.variable, units)
    value = float(chance.threshold)
    if chance.unit is not None:
        value = convert(value, chance.unit, target)
    threshold = format_rounded(value, precision(chance.variable, units))
    return (
        chance.variable.value,
        chance.op.value,
        threshold,
        chance.window.start,
        chance.window.end,
        chance.effective_aggregation.value,
    )


def _chance_wire(key: ChanceKey) -> str:
    variable, op, threshold, start, end, aggregation = key
    text = f"{variable}:{op}:{threshold}:{Window(start, end).to_query()}"
    default = Aggregation.TOTAL if Variable(variable) in _AMOUNTS else Aggregation.ANY
    if aggregation != default.value:
        text += f":{aggregation}"
    return text


def _chance_sort(key: ChanceKey) -> tuple[str, int, int, int, int, float]:
    variable, op, threshold, start, end, aggregation = key
    return (
        variable,
        _OP_ORDER[Op(op)],
        start,
        end,
        _AGGREGATION_ORDER[Aggregation(aggregation)],
        float(threshold),
    )


def prob_query(chances: Sequence[Chance], units: UnitSystem) -> tuple[str, list[str]]:
    """The canonical ``prob=`` value, and each caller term's canonical spelling in order.

    The server echoes that spelling as ``ProbabilityResult.term``, so results
    are matched to the caller's terms by it (BEHAVIOR 4).
    """
    keys = [chance_key(c, units) for c in chances]
    unique = sorted(set(keys), key=_chance_sort)
    return ",".join(_chance_wire(k) for k in unique), [_chance_wire(k) for k in keys]


def total_key(total: Total) -> TotalKey:
    """The identity of a window total."""
    return (total.variable.value, total.window.start, total.window.end)


def _total_wire(key: TotalKey) -> str:
    variable, start, end = key
    return f"{variable}:{Window(start, end).to_query()}"


def totals_query(totals: Sequence[Total]) -> tuple[str, list[str]]:
    """The canonical ``totals=`` value, and each caller request's canonical spelling.

    The server echoes that spelling as ``WindowTotal.term`` (BEHAVIOR 5).
    """
    keys = [total_key(t) for t in totals]
    unique = sorted(set(keys))
    return ",".join(_total_wire(k) for k in unique), [_total_wire(k) for k in keys]
