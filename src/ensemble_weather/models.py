"""Typed, immutable models for every response the SDK returns.

Each model is a frozen :func:`dataclasses.dataclass` named after its schema in
the OpenAPI contract. Unknown fields in a response are ignored, unknown enum
values keep their raw string (see :mod:`ensemble_weather.enums`), and a field
the server did not send is ``None``, never a made-up default such as ``0``.

Every forecast value is a :class:`Quantiles` distribution, not a single
number. :attr:`Quantiles.median` is offered as a convenience, and it is the
median, not "the forecast".

Values are in the units the request asked for (see :class:`UnitSystem`); the
SDK never converts response values.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

import httpx

from ._decode import JSON_NAME, NOT_JSON, decode_model, encode
from .enums import (
    Aggregation,
    AlertCertainty,
    AlertSeverity,
    AlertUrgency,
    AstronomicalSeason,
    AttributionSourceKind,
    ClampedOption,
    ConditionIcon,
    CurrentSource,
    DailyCondition,
    ElevationSource,
    FreezingLevelKind,
    GapFlowStatus,
    HourlyCondition,
    InversionKind,
    LocationType,
    MembersView,
    MoonPhase,
    NowcastLayer,
    NullReason,
    Op,
    PrecipitationType,
    PrecipKind,
    ProvenanceVariable,
    StationNetwork,
    StationStatus,
    StormOrientation,
    TemplateSectionKind,
    TemplateVariant,
    TotalAggregation,
    TotalVariable,
    UnitSystem,
    Variable,
    WindStatus,
)
from .errors import UsageError
from .probabilities import Chance, Total, Window

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pandas as pd

__all__ = [
    "ActiveAlert",
    "AlertsResponse",
    "AppliedOptions",
    "AttributionProvider",
    "AttributionRegistry",
    "AttributionSource",
    "CatalogResolvedEntry",
    "CatalogTemplateSummary",
    "CircularStats",
    "CmsTemplateSection",
    "CurrentConditions",
    "CurrentResponse",
    "CurrentStation",
    "DailyAstro",
    "DailyForecast",
    "DailyWind",
    "DayClimatology",
    "ElevationForecast",
    "EnsembleStats",
    "ForecastData",
    "ForecastResponse",
    "FreezingLevel",
    "GapFlow",
    "HourProvenance",
    "InversionInfo",
    "LocationElevation",
    "LocationRef",
    "LocationSummary",
    "LocationsResponse",
    "MemberForecast",
    "MemberGroup",
    "MembersCumulative",
    "Model",
    "ModelEntry",
    "ModelRunInfo",
    "ModelStats",
    "NearbyLocation",
    "NearbyLocationsResponse",
    "NearbyPointResponse",
    "NearestLocation",
    "NearestSensor",
    "PointInfo",
    "PrecipDisplay",
    "PrecipType",
    "ProbabilityResult",
    "ProbabilityThresholds",
    "PublicCatalogElevation",
    "PublicCatalogLocation",
    "PublicCatalogLocationDetail",
    "PublicCatalogLocationPage",
    "PublicCatalogNearbyStation",
    "PublicCatalogPhoto",
    "PublicCatalogPrimaryLocation",
    "PublicCatalogStation",
    "PublicCatalogStationDetail",
    "PublicCatalogStationPage",
    "PublicCatalogWebcam",
    "Quantiles",
    "RateLimit",
    "Response",
    "ResponseAttribution",
    "ResponseMeta",
    "RunEntry",
    "RunsResponse",
    "SearchHit",
    "SearchLocationsResponse",
    "Sector",
    "SensorObservation",
    "ServedRun",
    "SnowOutlook",
    "SnowOutlookQuantiles",
    "TimeSeriesPoint",
    "WindowTotal",
]

M = TypeVar("M", bound="Model")


@dataclass(frozen=True, kw_only=True)
class Model:
    """Base class of every model: decoding from and encoding to JSON."""

    @classmethod
    def from_dict(cls: type[M], data: Mapping[str, Any]) -> M:  # noqa: PYI019 - Python 3.10
        """Build the model from parsed JSON (unknown fields are ignored).

        Raises:
            ValueError: ``data`` does not match the schema.
        """
        return decode_model(cls, dict(data))

    def to_dict(self) -> dict[str, Any]:
        """Return the model as JSON-compatible data (``None`` fields left out)."""
        result: dict[str, Any] = encode(self)
        return result


# --- response metadata --------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class RateLimit:
    """The rate-limit state a response reported (``RateLimit-*`` headers).

    The SDK never hard-codes limits: these are what the server said. They are
    absent on responses the edge may share between callers (anonymous,
    edge-cacheable ones), so every field may be ``None``.

    Attributes:
        limit: The size of the budget this response counts against.
        remaining: Requests left before the binding limit refuses.
        reset: Seconds until the binding limit is whole again.
        policy: The budgets, e.g. ``"60;w=60, 10000;w=86400"``.
    """

    limit: int | None = None
    remaining: int | None = None
    reset: int | None = None
    policy: str | None = None

    @classmethod
    def from_headers(cls, headers: httpx.Headers) -> RateLimit | None:
        """Read the state from response headers, or ``None`` if there is none."""

        def number(name: str) -> int | None:
            raw = headers.get(name)
            try:
                return None if raw is None else int(raw.strip())
            except ValueError:
                return None

        state = cls(
            limit=number("ratelimit-limit"),
            remaining=number("ratelimit-remaining"),
            reset=number("ratelimit-reset"),
            policy=headers.get("ratelimit-policy"),
        )
        return None if state == cls() else state


@dataclass(frozen=True, kw_only=True)
class ResponseMeta:
    """What the HTTP exchange said about a response, beyond its body.

    Attributes:
        status: The final HTTP status (200 also for a revalidated 304).
        url: The URL the SDK requested.
        headers: The final response's headers.
        request_id: The ``X-Request-Id`` header, for support.
        rate_limit: The rate-limit state, if the response reported one.
        etag: The representation's entity tag.
        revalidated: ``True`` when the server answered ``304 Not Modified``
            and the body came from the local cache.
        from_cache: ``True`` when the body came from the local cache.
    """

    status: int = 200
    url: str = ""
    headers: httpx.Headers = field(default_factory=httpx.Headers)
    request_id: str | None = None
    rate_limit: RateLimit | None = None
    etag: str | None = None
    revalidated: bool = False
    from_cache: bool = False


@dataclass(frozen=True, kw_only=True)
class Response(Model):
    """Base class of top-level responses: adds :attr:`meta`."""

    meta: ResponseMeta = field(
        default_factory=ResponseMeta, compare=False, repr=False, metadata={NOT_JSON: True}
    )
    """The HTTP exchange's details: status, headers, rate limit, revalidation."""

    @property
    def rate_limit(self) -> RateLimit | None:
        """Shortcut for ``meta.rate_limit``."""
        return self.meta.rate_limit

    @property
    def revalidated(self) -> bool:
        """Shortcut for ``meta.revalidated``."""
        return self.meta.revalidated


# --- distributions ------------------------------------------------------------

_SERVED_RANGES = frozenset({(10, 90), (25, 75)})


@dataclass(frozen=True, kw_only=True)
class Quantiles(Model):
    """A distribution over the ensemble's members, as the server computed it.

    Every field is optional: a percentile the server did not send is
    ``None``, not ``0``. Wind direction is not a ``Quantiles`` but a
    :class:`CircularStats`.

    Attributes:
        mean: The ensemble mean.
        p10: The 10th percentile.
        p25: The 25th percentile.
        p50: The median.
        p75: The 75th percentile.
        p90: The 90th percentile.
        min: The lowest member.
        max: The highest member.
        probability: For precipitation, the chance of a measurable amount.
    """

    mean: float | None = None
    p10: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    p90: float | None = None
    min: float | None = None
    max: float | None = None
    probability: float | None = None

    @property
    def median(self) -> float | None:
        """The median (p50). It is the median, not "the forecast"."""
        return self.p50

    def range(self, low: int = 10, high: int = 90) -> tuple[float, float] | None:
        """The ``(low, high)`` percentiles, e.g. ``range(10, 90)``.

        Only the pairs the server serves are allowed: 10-90 and 25-75. There
        is no interpolation. Returns ``None`` when the server did not send
        both ends.

        Raises:
            UsageError: The pair is not one the server serves.
        """
        if (low, high) not in _SERVED_RANGES:
            raise UsageError(f"the server serves p10-p90 and p25-p75, not p{low}-p{high}")
        lo, hi = (self.p10, self.p90) if low == 10 else (self.p25, self.p75)
        if lo is None or hi is None:
            return None
        return (lo, hi)


# --- locations ---------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class LocationRef(Model):
    """A named location, as forecasts reference it.

    ``state`` and ``slug`` together name it: pass the object itself to
    :meth:`~ensemble_weather.Client.forecast`. A coordinate forecast's
    location has no ``slug`` or ``type`` (both ``None``).
    """

    slug: str | None = None
    state: str
    name: str
    lat: float
    lon: float
    elevation_m: float
    type: LocationType | None = None
    timezone: str


@dataclass(frozen=True, kw_only=True)
class LocationElevation(Model):
    """One named elevation of a location (ski-area base, mid, summit)."""

    name: str
    elevation: float
    default: bool | None = None


@dataclass(frozen=True, kw_only=True)
class LocationSummary(LocationRef):
    """A row of a location list or of ``nearby``."""

    county: str
    description: str | None = None
    elevations: list[LocationElevation] | None = None


@dataclass(frozen=True, kw_only=True)
class NearbyLocation(LocationSummary):
    """A nearby location and its distance."""

    distance_km: float


@dataclass(frozen=True, kw_only=True)
class SearchHit(LocationRef):
    """One location search result."""

    key: str
    """``"<state>/<slug>"``."""
    county: str


@dataclass(frozen=True, kw_only=True)
class SearchLocationsResponse(Response):
    """Location search results."""

    items: list[SearchHit]
    count: int


@dataclass(frozen=True, kw_only=True)
class LocationsResponse(Response):
    """One page of the locations list. ``next_cursor`` is ``None`` on the last."""

    state: str
    count: int
    locations: list[LocationSummary]
    next_cursor: str | None = None


@dataclass(frozen=True, kw_only=True)
class NearbyLocationsResponse(Response):
    """Locations near a named location."""

    location: LocationSummary
    radius_km: float
    count: int
    locations: list[NearbyLocation]


@dataclass(frozen=True, kw_only=True)
class NearbyPointResponse(Response):
    """Locations near a coordinate."""

    lat: float
    lon: float
    radius_km: float
    count: int
    locations: list[NearbyLocation]


@dataclass(frozen=True, kw_only=True)
class NearestLocation(Model):
    """A named location near a refused coordinate, answered without a key.

    Carried by :class:`~ensemble_weather.PermissionDeniedError` on a
    ``PRO_REQUIRED`` coordinate request, when one is within 10 km and 300 m
    of elevation. Pass ``slug`` with the state from ``url`` to
    :meth:`~ensemble_weather.Client.forecast`.

    Attributes:
        slug: The location's slug.
        url: The location route's path on this API.
        distance_km: Its distance from the requested point.
        elevation_m: Its elevation, metres.
    """

    slug: str
    url: str
    distance_km: float
    elevation_m: float


# --- attribution ---------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ResponseAttribution(Model):
    """The credit line every response carries. Show it with the data."""

    sources: list[str]
    credit: str
    url: str


@dataclass(frozen=True, kw_only=True)
class AttributionSource(Model):
    """One data source in the attribution registry."""

    id: str
    name: str
    kind: AttributionSourceKind
    provider: str


@dataclass(frozen=True, kw_only=True)
class AttributionProvider(Model):
    """One data provider, its licence and its sources."""

    id: str
    name: str
    credit: str
    licence: str
    licence_url: str
    terms_url: str
    modified: bool
    notices: list[str]
    sources: list[AttributionSource]


@dataclass(frozen=True, kw_only=True)
class AttributionRegistry(Response):
    """Every data provider the API draws on."""

    providers: list[AttributionProvider]


# --- forecast -------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ModelEntry(Model):
    """One contributing model and its own cycle."""

    id: str
    cycle: dt.datetime | None = None
    members: int | None = None


@dataclass(frozen=True, kw_only=True)
class ModelRunInfo(Model):
    """The model run a forecast was built from."""

    initialized_at: dt.datetime
    total_members: int
    models: list[ModelEntry]


@dataclass(frozen=True, kw_only=True)
class Sector(Model):
    """A circular sector, in degrees, clockwise from ``from_`` to ``to``."""

    from_: float = field(metadata={JSON_NAME: "from"})
    to: float


@dataclass(frozen=True, kw_only=True)
class CircularStats(Model):
    """The circular distribution of wind direction, in degrees.

    Each sector runs clockwise from ``from_`` to ``to``, so ``to`` may be
    numerically less than ``from_`` (``350`` to ``20`` crosses north); the
    SDK leaves it as sent.

    Attributes:
        mean: The circular mean direction.
        stddev: The circular standard deviation.
        sector_50: The narrowest sector holding half of the members.
        sector_90: The narrowest sector holding 90 % of the members.
    """

    mean: float
    stddev: float | None = None
    sector_50: Sector
    sector_90: Sector


@dataclass(frozen=True, kw_only=True)
class EnsembleStats(Model):
    """The distribution of every variable at one hour."""

    temperature: Quantiles
    feels_like: Quantiles | None = None
    dewpoint: Quantiles | None = None
    precipitation: Quantiles
    wind_speed: Quantiles
    wind_gust: Quantiles | None = None
    wind_direction: CircularStats
    """Circular: see :class:`CircularStats`."""
    snow_level: Quantiles | None = None
    slr: Quantiles | None = None
    snowfall: Quantiles | None = None
    cloud_cover: Quantiles | None = None
    skin_temperature: Quantiles | None = None
    """Only with ``include=["skin_temperature"]``."""
    mslp: Quantiles | None = None
    """Only with ``include=["mslp"]``."""
    cape: Quantiles | None = None
    relative_humidity: Quantiles | None = None


@dataclass(frozen=True, kw_only=True)
class PrecipType(Model):
    """An hour's most likely precipitation type and its chances."""

    type: PrecipitationType
    snow_probability: float
    rain_probability: float


@dataclass(frozen=True, kw_only=True)
class InversionInfo(Model):
    """A temperature inversion at the hour."""

    kind: InversionKind
    depth: float
    strength: float


@dataclass(frozen=True, kw_only=True)
class FreezingLevel(Model):
    """Where the freezing level is.

    ``kind`` says which fields apply: ``height`` (with :attr:`height` and
    :attr:`above_freezing_layer_aloft`), ``above_profile`` (with
    :attr:`top`) or ``below_surface`` (neither).
    """

    kind: FreezingLevelKind
    height: float | None = None
    above_freezing_layer_aloft: bool | None = None
    top: float | None = None


@dataclass(frozen=True, kw_only=True)
class HourProvenance(Model):
    """Which post-processing rule shaped each variable (``diagnostics=provenance``)."""

    densified: bool | None = None
    ngr: list[ProvenanceVariable] | None = None
    fallback: list[ProvenanceVariable] | None = None
    borrowed: list[ProvenanceVariable] | None = None
    spread_floored: list[ProvenanceVariable] | None = None
    floor_clamped: list[ProvenanceVariable] | None = None
    bucket_split: list[ProvenanceVariable] | None = None
    distribution_parameters: list[ProvenanceVariable] | None = None
    spread_interpolated: list[ProvenanceVariable] | None = None
    interpolated_contributor: list[ProvenanceVariable] | None = None
    moment_matched_family: list[ProvenanceVariable] | None = None
    lapse_profile: list[ProvenanceVariable] | None = None
    lapse_climatology: list[ProvenanceVariable] | None = None
    lapse_prism: list[ProvenanceVariable] | None = None
    spread_clamped_low: list[ProvenanceVariable] | None = None
    spread_clamped_high: list[ProvenanceVariable] | None = None
    gust_dressed: list[ProvenanceVariable] | None = None


@dataclass(frozen=True, kw_only=True)
class ModelStats(Model):
    """One model's statistics at an hour (``models=true``)."""

    id: str
    temperature: Quantiles | None = None
    dewpoint: Quantiles | None = None
    precipitation: Quantiles | None = None
    wind_speed: Quantiles | None = None
    wind_direction: CircularStats | None = None
    snow_level: Quantiles | None = None
    slr: Quantiles | None = None
    snowfall: Quantiles | None = None
    interpolated: bool | None = None


@dataclass(frozen=True, kw_only=True)
class MemberForecast(Model):
    """One ensemble member's values at an hour (``members=true``)."""

    member_id: int
    temperature: float | None = None
    precipitation: float | None = None
    precipitation_hours: int | None = None
    wind_speed: float | None = None
    wind_direction: float | None = None
    snow_level: float | None = None
    slr: float | None = None
    snowfall: float | None = None
    cumulative_precipitation: float | None = None
    cumulative_snowfall: float | None = None


@dataclass(frozen=True, kw_only=True)
class MemberGroup(Model):
    """One model's members at an hour."""

    id: str
    members: list[MemberForecast]


@dataclass(frozen=True, kw_only=True)
class MembersCumulative(Model):
    """The distribution of the members' running totals at an hour."""

    precipitation: Quantiles | None = None
    snowfall: Quantiles | None = None


@dataclass(frozen=True, kw_only=True)
class TimeSeriesPoint(Model):
    """One forecast hour."""

    valid_time: dt.datetime
    lead_time_hours: int
    is_night: bool
    condition: HourlyCondition
    condition_text: str
    condition_icon: ConditionIcon
    gust_notable: bool | None = None
    precipitation_type: PrecipType | None = None
    inversion: InversionInfo | None = None
    freezing_level: FreezingLevel | None = None
    ensemble: EnsembleStats
    provenance: HourProvenance | None = None
    model_means: list[ModelStats] | None = None
    members: list[MemberGroup] | None = None
    members_cumulative: MembersCumulative | None = None
    cumulative_precipitation: float | None = None
    cumulative_snowfall: float | None = None


@dataclass(frozen=True, kw_only=True)
class PrecipDisplay(Model):
    """What a day's precipitation summary shows."""

    kind: PrecipKind
    chance: float
    amount: float | None = None


@dataclass(frozen=True, kw_only=True)
class DailyAstro(Model):
    """Sun and moon for a date."""

    sunrise: dt.datetime | None = None
    sunset: dt.datetime | None = None
    moon_phase: MoonPhase
    moon_illumination: float
    astronomical_season: AstronomicalSeason


@dataclass(frozen=True, kw_only=True)
class DayClimatology(Model):
    """The climatological temperature for a date."""

    mean: float
    std: float


@dataclass(frozen=True, kw_only=True)
class DailyWind(Model):
    """A day's wind summary."""

    status: WindStatus | None = None
    peak_speed: float | None = None
    peak_speed_p90: float | None = None
    is_gust: bool | None = None
    sustained_speed: float | None = None


@dataclass(frozen=True, kw_only=True)
class DailyForecast(Model):
    """One local calendar date's summary.

    ``total_precipitation`` and ``total_snowfall`` are the distributions of each
    member's own day total, computed by the server; they are not sums of
    hourly quantiles.
    """

    date: dt.date
    condition: DailyCondition
    condition_text: str
    condition_icon: ConditionIcon
    precipitation_type: PrecipitationType | None = None
    high: Quantiles
    low: Quantiles
    feels_like_high: Quantiles | None = None
    feels_like_low: Quantiles | None = None
    total_precipitation: Quantiles
    total_snowfall: Quantiles | None = None
    precipitation_probability: float
    precipitation_occurrence_probability: float
    snow_probability: float
    snow_level_mean: float | None = None
    snow_level: Quantiles | None = None
    total_precipitation_if_wet: Quantiles | None = None
    total_snowfall_if_wet: Quantiles | None = None
    precipitation_display: PrecipDisplay
    cloud_cover_mean: float | None = None
    wind: DailyWind | None = None
    storm_orientation: StormOrientation | None = None
    storm_orientation_description: str | None = None
    astro: DailyAstro
    temperature_climatology: DayClimatology | None = None


@dataclass(frozen=True, kw_only=True)
class SnowOutlookQuantiles(Model):
    """The distributions behind :class:`SnowOutlook`'s headline numbers."""

    next_24h: Quantiles | None = None
    next_48h: Quantiles | None = None
    next_7d: Quantiles | None = None


@dataclass(frozen=True, kw_only=True)
class SnowOutlook(Model):
    """Snowfall over the next 24 h, 48 h and 7 days, computed by the server."""

    next_24h: float | None = None
    next_48h: float | None = None
    next_7d: float | None = None
    overnight_4pm_9am: float | None = None
    quantiles: SnowOutlookQuantiles | None = None


@dataclass(frozen=True, kw_only=True)
class ForecastData(Model):
    """The hourly series and the daily summaries."""

    max_hours: int
    interval_hours: int
    timeseries: list[TimeSeriesPoint] = field(default_factory=list)
    """The hourly series (empty with ``hourly=false``)."""
    daily: list[DailyForecast] = field(default_factory=list)
    """The daily summaries (empty with ``daily=false``)."""
    snow_outlook: SnowOutlook | None = None

    def to_dataframe(self) -> pd.DataFrame:
        """The hourly series as a :class:`pandas.DataFrame` (needs ``[pandas]``).

        One row per hour, indexed by ``valid_time``; one column per served
        statistic, named ``<variable>.<statistic>`` (``temperature.p10``).
        The values are exactly the server's; nothing is computed.
        """
        from ._pandas import hourly_frame  # noqa: PLC0415 - pandas is optional

        return hourly_frame(self.timeseries)

    def daily_dataframe(self) -> pd.DataFrame:
        """The daily summaries as a :class:`pandas.DataFrame` (needs ``[pandas]``)."""
        from ._pandas import daily_frame  # noqa: PLC0415 - pandas is optional

        return daily_frame(self.daily)


@dataclass(frozen=True, kw_only=True)
class ElevationForecast(Model):
    """A full forecast at one of a location's extra elevations."""

    name: str
    elevation: float
    lat: float
    lon: float
    hourly: list[TimeSeriesPoint] | None = None
    daily: list[DailyForecast] | None = None
    snow_outlook: SnowOutlook | None = None


@dataclass(frozen=True, kw_only=True)
class ProbabilityThresholds(Model):
    """The thresholds behind the headline probabilities, in the request's units."""

    hourly_precipitation: float
    hourly_snowfall: float
    daily_precipitation_probability: float
    daily_precipitation_occurrence_probability: float
    daily_snow_probability: float


@dataclass(frozen=True, kw_only=True)
class ProbabilityResult(Model):
    """One answered probability term, with its full reference class.

    Attributes:
        term: The canonical term the SDK sent (``"snowfall:ge:6.000:24h"``);
            the SDK matches each result to the caller's term by it.
        variable: The variable asked about.
        op: ``ge`` or ``le``.
        threshold: In the request's units, at the variable's served precision.
        window_start_hours: The window's first hour.
        window_end_hours: The window's end hour.
        aggregation: How the window's hours were combined.
        from_: The window's first instant (JSON ``from``).
        to: The window's end (exclusive).
        probability: The share of members meeting the term, 0..1, or ``None``
            (see :attr:`null_reason`). ``None`` is not zero.
        members: The members that voted.
        null_reason: Why :attr:`probability` is ``None``; ``None`` otherwise.
        request: The :class:`~ensemble_weather.Chance` this answers, as the
            caller wrote it.
    """

    term: str
    variable: Variable
    op: Op
    threshold: float
    window_start_hours: int
    window_end_hours: int
    aggregation: Aggregation
    from_: dt.datetime | None = field(default=None, metadata={JSON_NAME: "from"})
    to: dt.datetime | None = None
    probability: float | None = None
    members: int
    null_reason: NullReason | None = None
    request: Chance | None = field(default=None, compare=False, metadata={NOT_JSON: True})

    @property
    def window(self) -> Window:
        """The window as a :class:`~ensemble_weather.Window`."""
        return Window(self.window_start_hours, self.window_end_hours)


@dataclass(frozen=True, kw_only=True)
class WindowTotal(Model):
    """One answered window total: the distribution of each member's total.

    Attributes:
        term: The canonical term the SDK sent (``"precipitation:48h"``); the
            SDK matches each result to the caller's request by it.
        variable: ``precipitation`` or ``snowfall``.
        window_start_hours: The window's first hour.
        window_end_hours: The window's end hour.
        aggregation: ``total`` for precipitation and snowfall.
        from_: The window's first instant (JSON ``from``).
        to: The window's end (exclusive).
        quantiles: The distribution, or ``None`` (see :attr:`null_reason`).
        members: The members whose values cover the whole window.
        null_reason: Why :attr:`quantiles` is ``None``; ``None`` otherwise.
        request: The :class:`~ensemble_weather.Total` this answers.
    """

    term: str
    variable: TotalVariable
    window_start_hours: int
    window_end_hours: int
    aggregation: TotalAggregation
    from_: dt.datetime | None = field(default=None, metadata={JSON_NAME: "from"})
    to: dt.datetime | None = None
    quantiles: Quantiles | None = None
    members: int
    null_reason: NullReason | None = None
    request: Total | None = field(default=None, compare=False, metadata={NOT_JSON: True})

    @property
    def window(self) -> Window:
        """The window as a :class:`~ensemble_weather.Window`."""
        return Window(self.window_start_hours, self.window_end_hours)


@dataclass(frozen=True, kw_only=True)
class AppliedOptions(Model):
    """The options the server applied, after clamping to the caller's tier."""

    max_hours: int | None = None
    max_days: int | None = None
    clamped: list[ClampedOption]


@dataclass(frozen=True, kw_only=True)
class GapFlow(Model):
    """A gap-flow wind event (Columbia Gorge style)."""

    status: GapFlowStatus | None = None
    pressure_diff_hpa: float | None = None
    wind_multiplier: float | None = None
    direction: str | None = None


@dataclass(frozen=True, kw_only=True)
class NearestSensor(Model):
    """An observing station used by the nowcast blend."""

    station_id: str
    name: str
    source: str
    distance_km: float
    elevation_diff: float
    effective_distance_km: float
    observation_time: dt.datetime


@dataclass(frozen=True, kw_only=True)
class PointInfo(Model):
    """Where a coordinate forecast was computed."""

    requested_lat: float
    requested_lon: float
    lat: float
    lon: float
    resolution_deg: float
    elevation: float
    elevation_source: ElevationSource
    state: str


@dataclass(frozen=True, kw_only=True)
class CurrentStation(Model):
    """The station that anchored current conditions."""

    station_id: str
    name: str
    observation_time: dt.datetime


@dataclass(frozen=True, kw_only=True)
class CurrentConditions(Model):
    """Right now: a view of one served hour, never a second forecast."""

    time: dt.datetime
    temperature: float
    feels_like: float | None = None
    condition: str
    condition_text: str
    condition_icon: ConditionIcon
    wind_speed: float
    wind_gust: float | None = None
    wind_direction: float
    relative_humidity: float | None = None
    dewpoint: float | None = None
    precipitation_probability: float | None = None
    source: CurrentSource
    station: CurrentStation | None = None


@dataclass(frozen=True, kw_only=True)
class ForecastResponse(Response):
    """A forecast: the hourly series, daily summaries, and what was asked.

    :attr:`probabilities` and :attr:`window_totals` are in the order of the
    caller's ``prob`` and ``totals`` arguments (the SDK sends them in a
    canonical order and maps the answers back); duplicate terms share one
    result.
    """

    thresholds: ProbabilityThresholds | None = None
    probabilities: list[ProbabilityResult] = field(default_factory=list)
    """One result per ``prob`` term, in the caller's order."""
    window_totals: list[WindowTotal] = field(default_factory=list)
    """One result per ``totals`` request, in the caller's order."""
    applied: AppliedOptions | None = None
    location: LocationRef
    model_run: ModelRunInfo
    units: UnitSystem
    forecast: ForecastData
    elevation_forecasts: list[ElevationForecast] | None = None
    nowcast_applied: bool
    nowcast_unavailable: list[NowcastLayer] | None = None
    members_view: MembersView | None = None
    gap_flow: GapFlow | None = None
    nearest_sensors: list[NearestSensor] | None = None
    point: PointInfo | None = None
    current: CurrentConditions | None = None
    attribution: ResponseAttribution

    def to_dataframe(self) -> pd.DataFrame:
        """The hourly series as a DataFrame; see :meth:`ForecastData.to_dataframe`."""
        return self.forecast.to_dataframe()


# --- current and alerts -------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ActiveAlert(Model):
    """An active weather alert."""

    id: str
    event: str
    severity: AlertSeverity
    urgency: AlertUrgency
    certainty: AlertCertainty
    headline: str
    onset: dt.datetime | None = None
    expires: dt.datetime
    ends: dt.datetime | None = None


@dataclass(frozen=True, kw_only=True)
class SensorObservation(Model):
    """A recent observation from a nearby station."""

    station_id: str
    name: str
    source: str
    observation_time: dt.datetime
    temperature: float | None = None
    dewpoint: float | None = None
    relative_humidity: float | None = None
    wind_speed: float | None = None
    wind_gust: float | None = None
    wind_direction: float | None = None
    pressure: float | None = None
    precipitation: float | None = None
    precipitation_rate: float | None = None
    reflectivity: float | None = None
    pavement_temp: float | None = None
    subsurface_temp: float | None = None
    visibility: float | None = None
    cloud_cover: float | None = None
    ceiling_height: float | None = None
    snow_depth: float | None = None
    swe: float | None = None
    swe_percent_of_median: float | None = None
    snowfall: float | None = None
    solar_radiation: float | None = None
    pavement_condition: str | None = None


@dataclass(frozen=True, kw_only=True)
class CurrentResponse(Response):
    """Current conditions, nearby observations and active alerts."""

    location: LocationRef
    alerts: list[ActiveAlert]
    alerts_as_of: dt.datetime
    sensor_count: int
    sensors: list[SensorObservation]
    current: CurrentConditions | None = None
    as_of: dt.datetime
    model_run_initialized_at: dt.datetime | None = None
    nowcast_hours: list[TimeSeriesPoint] | None = None
    units: UnitSystem
    attribution: ResponseAttribution
    nowcast_unavailable: list[NowcastLayer] | None = None


@dataclass(frozen=True, kw_only=True)
class AlertsResponse(Response):
    """Active alerts for a location."""

    location: LocationRef
    alert_count: int
    as_of: dt.datetime
    alerts: list[ActiveAlert]
    attribution: ResponseAttribution


# --- runs -----------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ServedRun(Model):
    """What a forecast request serves now."""

    initialized_at: dt.datetime
    models: list[ModelEntry]


@dataclass(frozen=True, kw_only=True)
class RunEntry(Model):
    """An init time at least two models completed."""

    initialized_at: dt.datetime


@dataclass(frozen=True, kw_only=True)
class RunsResponse(Response):
    """The served run and the recent runs, newest first.

    ``next_cursor`` is ``None`` on the last page.
    """

    served: ServedRun | None = None
    runs: list[RunEntry]
    count: int
    next_cursor: str | None = None


# --- catalog --------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class PublicCatalogLocation(LocationRef):
    """A catalog location with its public content."""

    county: str | None = None
    country: str | None = None
    aliases: list[str] | None = None
    description_short: str | None = None
    description_long: str | None = None
    microclimate_notes: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    best_seasons: list[str] | None = None
    key_factors: list[str] | None = None
    tags: list[str] | None = None
    external_links: Any = None
    is_featured: bool | None = None


@dataclass(frozen=True, kw_only=True)
class PublicCatalogLocationPage(Response):
    """One page of the location catalog. ``next_cursor`` is ``None`` on the last."""

    items: list[PublicCatalogLocation]
    next_cursor: str | None = None


@dataclass(frozen=True, kw_only=True)
class PublicCatalogElevation(Model):
    """One named elevation in the catalog."""

    label: str
    elevation_m: float
    lat_override: float | None = None
    lon_override: float | None = None
    is_default: bool


@dataclass(frozen=True, kw_only=True)
class PublicCatalogPhoto(Model):
    """A catalog photo and its licence."""

    url: str
    caption: str | None = None
    credit: str | None = None
    alt_text: str | None = None
    license: str | None = None
    license_url: str | None = None


@dataclass(frozen=True, kw_only=True)
class PublicCatalogWebcam(Model):
    """A webcam at a catalog entry."""

    name: str
    url: str
    embed_type: str | None = None
    provider: str | None = None
    refresh_interval_seconds: int | None = None


@dataclass(frozen=True, kw_only=True)
class PublicCatalogNearbyStation(Model):
    """An observing station near a catalog location."""

    slug: str
    name: str
    network: StationNetwork
    station_status: StationStatus
    distance_km: float | None = None
    elevation_diff_m: float | None = None
    is_primary: bool


@dataclass(frozen=True, kw_only=True)
class CmsTemplateSection(Model):
    """One section of a catalog page template."""

    kind: TemplateSectionKind
    key: str
    config: dict[str, Any] | None = None


@dataclass(frozen=True, kw_only=True)
class CatalogTemplateSummary(Model):
    """The page template of a catalog entry (``include=template``)."""

    id: str
    location_type: LocationType | None = None
    template_variant: TemplateVariant | None = None
    spec: list[CmsTemplateSection]


@dataclass(frozen=True, kw_only=True)
class CatalogResolvedEntry(Model):
    """A resolved content entry (``include=content``)."""

    id: str
    content_type_key: str
    title: str
    body: dict[str, Any]
    slot: str
    display_order: int
    resolved_locale: str
    updated_at: dt.datetime


@dataclass(frozen=True, kw_only=True)
class PublicCatalogLocationDetail(PublicCatalogLocation, Response):
    """A catalog location with its elevations, media and nearby stations."""

    elevations: list[PublicCatalogElevation]
    photos: list[PublicCatalogPhoto]
    webcams: list[PublicCatalogWebcam]
    nearby_stations: list[PublicCatalogNearbyStation]
    template: CatalogTemplateSummary | None = None
    content: list[CatalogResolvedEntry] | None = None


@dataclass(frozen=True, kw_only=True)
class PublicCatalogStation(LocationRef):
    """A catalog observing station."""

    county: str | None = None
    country: str | None = None
    aliases: list[str] | None = None
    network: StationNetwork | None = None
    source_station_id: str | None = None
    elevation_msl_m: float | None = None
    sensor_height_agl_m: float | None = None
    sensor_capabilities: list[str] | None = None
    station_status: StationStatus | None = None
    last_report_at: dt.datetime | None = None
    last_report_summary: Any = None
    install_date: dt.date | None = None
    decommission_date: dt.date | None = None
    update_frequency_minutes: int | None = None
    station_url: str | None = None
    data_url: str | None = None
    description_short: str | None = None
    description_long: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    tags: list[str] | None = None
    is_featured: bool | None = None


@dataclass(frozen=True, kw_only=True)
class PublicCatalogStationPage(Response):
    """One page of the station catalog. ``next_cursor`` is ``None`` on the last."""

    items: list[PublicCatalogStation]
    next_cursor: str | None = None


@dataclass(frozen=True, kw_only=True)
class PublicCatalogPrimaryLocation(Model):
    """The location a station primarily serves."""

    slug: str
    name: str
    lat: float
    lon: float
    elevation_m: float
    type: str


@dataclass(frozen=True, kw_only=True)
class PublicCatalogStationDetail(PublicCatalogStation, Response):
    """A catalog station with its media and primary location."""

    photos: list[PublicCatalogPhoto]
    webcams: list[PublicCatalogWebcam]
    primary_location: PublicCatalogPrimaryLocation | None = None
    template: CatalogTemplateSummary | None = None
    content: list[CatalogResolvedEntry] | None = None
