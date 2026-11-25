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
from ._errors import UsageError
from .enums import (
    Aggregation,
    AlertCertainty,
    AlertClass,
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
    PassStatusLevel,
    PrecipitationType,
    PrecipKind,
    ProvenanceVariable,
    SnowCharacter,
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
from .probabilities import Chance, Total, Window

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pandas as pd

__all__ = [
    "ActiveAlert",
    "AlertOutlineCollection",
    "AlertOutlineFeature",
    "AlertOutlineGeometry",
    "AlertOutlineProperties",
    "AlertsResponse",
    "AppliedOptions",
    "AttributionProvider",
    "AttributionRegistry",
    "AttributionSource",
    "AvalancheForecast",
    "AvalancheZoneCollection",
    "AvalancheZoneFeature",
    "AvalancheZoneGeometry",
    "BandColumns",
    "CatalogResolvedEntry",
    "CatalogTemplateSummary",
    "CircularStats",
    "CmsTemplateSection",
    "CompositionResponse",
    "CurrentConditions",
    "CurrentResponse",
    "CurrentStation",
    "DailyAstro",
    "DailyForecast",
    "DailyWind",
    "DayClimatology",
    "DayDeparture",
    "DayNormal",
    "DayPercentile",
    "ElevationForecast",
    "ElevationSummary",
    "EnsembleStats",
    "ExploreItem",
    "ExploreResponse",
    "ExploreValue",
    "ForecastData",
    "ForecastLocation",
    "ForecastResponse",
    "FreezingLevel",
    "GapFlow",
    "HourProvenance",
    "InversionInfo",
    "LocationRef",
    "LocationSummary",
    "LocationsResponse",
    "MeasuredPrecipitation",
    "MemberForecast",
    "MemberGroup",
    "MemberPlume",
    "MemberQuantiles",
    "MembersCumulative",
    "MembersSpread",
    "Model",
    "ModelColumns",
    "ModelEntry",
    "ModelRunInfo",
    "ModelStats",
    "NearbyLocation",
    "NearbyLocationsResponse",
    "NearbyPointResponse",
    "NearestLocation",
    "NearestSensor",
    "PassCamera",
    "PassChance",
    "PassChances",
    "PassForecast",
    "PassHour",
    "PassOfficialStatus",
    "PassRoadSensor",
    "PassSnow24h",
    "PassSnowWindow",
    "PassStatusSegment",
    "PassTravelWindow",
    "PassTravelWindows",
    "PlaceSummary",
    "PlumeBands",
    "PlumeHeadline",
    "PointInfo",
    "PooledColumns",
    "PrecipDisplay",
    "PrecipOutlook",
    "PrecipType",
    "PrecipitationByType",
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
    "SeasonDay",
    "SeasonResponse",
    "SeasonStation",
    "SeasonTotal",
    "Sector",
    "SensorObservation",
    "ServedRun",
    "SnowLevelRange",
    "SnowOnGround",
    "SnowOutlook",
    "SnowOutlookQuantiles",
    "SnowTrendDay",
    "SnowTrendGrid",
    "SnowTrendResponse",
    "SnowTrendResponseElevation",
    "SnowTrendRun",
    "SnowpackAspect",
    "SnowpackDepth",
    "SnowpackLayer",
    "SnowpackModel",
    "SnowpackPlumeDepth",
    "SnowpackPlumeModel",
    "SnowpackPlumeResponse",
    "SnowpackResponse",
    "SnowpackResponseDefinitions",
    "SnowpackRun",
    "SnowpackSpot",
    "SnowpackSpotAnchor",
    "SnowpackStep",
    "SummaryEvent",
    "SummaryValues",
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
class ElevationSummary(Model):
    """One named elevation of a location (ski-area base, mid, summit). Attributes.

    Name: The elevation's id: the name to pass in ``elevations=``. display_name: What the
    place is called, for display ("K-1 Lodge"). elevation: In the request's length units (m,
    ft), to 0.1. default: ``True`` on the primary only.
    """

    name: str
    display_name: str | None = None
    height: float = field(metadata={JSON_NAME: "elevation"})
    """(JSON ``elevation``)"""
    default: bool | None = None


@dataclass(frozen=True, kw_only=True)
class LocationSummary(LocationRef):
    """A row of a location list or of ``nearby``."""

    county: str
    description: str | None = None
    elevations: list[ElevationSummary] | None = None


@dataclass(frozen=True, kw_only=True)
class NearbyLocation(LocationSummary):
    """A nearby location and its distance."""

    distance_km: float


@dataclass(frozen=True, kw_only=True)
class SearchHit(LocationRef):
    """One location search result."""

    key: str
    """The hit's identity."""
    county: str
    explore: ExploreValue | None = None
    """With a metric ``sort``, the hit's value of that metric."""


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
    items: list[LocationSummary] = field(metadata={JSON_NAME: "locations"})
    """(JSON ``locations``)"""
    next_cursor: str | None = None


@dataclass(frozen=True, kw_only=True)
class NearbyLocationsResponse(Response):
    """Locations near a named location."""

    origin: LocationSummary = field(metadata={JSON_NAME: "location"})
    """(JSON ``location``)"""
    radius_km: float
    count: int
    items: list[NearbyLocation] = field(metadata={JSON_NAME: "locations"})
    """(JSON ``locations``)"""


@dataclass(frozen=True, kw_only=True)
class NearbyPointResponse(Response):
    """Locations near a coordinate."""

    lat: float
    lon: float
    radius_km: float
    count: int
    items: list[NearbyLocation] = field(metadata={JSON_NAME: "locations"})
    """(JSON ``locations``)"""


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
    display_members: list[int] | None = None
    """Display-only members (plumes and charts), not in the blend."""
    display_members_snowfall: str | None = None
    """``borrowed_from_deterministic`` when the display members' snowfall is borrowed."""


@dataclass(frozen=True, kw_only=True)
class ModelRunInfo(Model):
    """The model run a forecast was built from."""

    initialized_at: dt.datetime
    total_members: int
    contributors: list[ModelEntry] = field(metadata={JSON_NAME: "models"})
    """(JSON ``models``)"""


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
    snow_level_wet_bulb: Quantiles | None = None
    """The snow level on the NWS (wet-bulb) scale."""
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

    kind: PrecipitationType = field(metadata={JSON_NAME: "type"})
    """(JSON ``type``)"""
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
    :attr:`warm_layer_aloft`), ``above_profile`` (with
    :attr:`top`) or ``below_surface`` (neither).
    """

    kind: FreezingLevelKind
    height: float | None = None
    warm_layer_aloft: bool | None = field(
        default=None, metadata={JSON_NAME: "above_freezing_layer_aloft"}
    )
    """(JSON ``above_freezing_layer_aloft``)"""
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
    snow_level_wet_bulb: Quantiles | None = None
    slr: Quantiles | None = None
    snowfall: Quantiles | None = None
    interpolated: bool | None = None


@dataclass(frozen=True, kw_only=True)
class MemberForecast(Model):
    """One ensemble member's values at an hour (``members=true``)."""

    id: int = field(metadata={JSON_NAME: "member_id"})
    """(JSON ``member_id``)"""
    temperature: float | None = None
    precipitation: float | None = None
    precipitation_hours: int | None = None
    wind_speed: float | None = None
    wind_direction: float | None = None
    snow_level: float | None = None
    snow_level_wet_bulb: float | None = None
    slr: float | None = None
    snowfall: float | None = None
    cumulative_precipitation: float | None = None
    cumulative_snowfall: float | None = None


@dataclass(frozen=True, kw_only=True)
class MemberGroup(Model):
    """One model's members at an hour."""

    id: str
    items: list[MemberForecast] = field(metadata={JSON_NAME: "members"})
    """(JSON ``members``)"""


@dataclass(frozen=True, kw_only=True)
class MembersCumulative(Model):
    """The distribution of the members' running totals at an hour."""

    precipitation: MemberQuantiles | None = None
    snowfall: MemberQuantiles | None = None


@dataclass(frozen=True, kw_only=True)
class TimeSeriesPoint(Model):
    """One forecast hour."""

    valid_at: dt.datetime = field(metadata={JSON_NAME: "valid_time"})
    """(JSON ``valid_time``)"""
    lead_hours: int = field(metadata={JSON_NAME: "lead_time_hours"})
    """(JSON ``lead_time_hours``)"""
    is_night: bool
    measured: bool | None = None
    """``True`` on an hour whose values are observed, not forecast."""
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
    members_6h: MembersCumulative | None = None
    """The members' 6-hour totals ending at this hour (00/06/12/18Z)."""
    members_spread: MembersSpread | None = None
    cumulative_precipitation: float | None = None
    cumulative_snowfall: float | None = None
    snow_character: SnowCharacter | None = None
    precipitation_by_type: PrecipitationByType | None = None


@dataclass(frozen=True, kw_only=True)
class PrecipDisplay(Model):
    """What a day's precipitation summary shows."""

    kind: PrecipKind
    chance: float
    amount: float | None = None
    snow_amount: float | None = None
    """The day's snowfall to show (the mean of ``total_snowfall``)."""


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
    covered_from: dt.datetime | None = None
    """On today's row, the first hour the forecast covers."""
    measured_precipitation: MeasuredPrecipitation | None = None
    snow_character: SnowCharacter | None = None
    slr: float | None = None
    """The day's snow-to-liquid ratio."""
    snow_level_range: SnowLevelRange | None = None
    snow_level_wet_bulb: Quantiles | None = None
    snow_level_wet_bulb_range: SnowLevelRange | None = None
    normal: DayNormal | None = None
    departure: DayDeparture | None = None
    percentile: DayPercentile | None = None


@dataclass(frozen=True, kw_only=True)
class SnowOutlookQuantiles(Model):
    """The distributions behind :class:`SnowOutlook`'s headline numbers."""

    next_24h: Quantiles | None = None
    next_48h: Quantiles | None = None
    next_72h: Quantiles | None = None
    next_7d: Quantiles | None = None


@dataclass(frozen=True, kw_only=True)
class SnowOutlook(Model):
    """Snowfall over the next 24 h, 48 h and 7 days, computed by the server."""

    next_24h: float | None = None
    next_48h: float | None = None
    next_72h: float | None = None
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
    precipitation_outlook: PrecipOutlook | None = None
    plume: MemberPlume | None = None
    """The plume view (``members="plume"``): columns, not hourly rows."""

    def to_dataframe(self) -> pd.DataFrame:
        """The hourly series as a :class:`pandas.DataFrame` (needs ``[pandas]``).

        One row per hour, indexed by ``valid_at``; one column per served
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
    display_name: str | None = None
    height: float = field(metadata={JSON_NAME: "elevation"})
    """(JSON ``elevation``)"""
    lat: float
    lon: float
    hourly: list[TimeSeriesPoint] | None = None
    daily: list[DailyForecast] | None = None
    snow_outlook: SnowOutlook | None = None
    precipitation_outlook: PrecipOutlook | None = None
    plume: MemberPlume | None = None
    snow_on_ground: SnowOnGround | None = None
    nearest_sensors: list[NearestSensor] | None = None


@dataclass(frozen=True, kw_only=True)
class ProbabilityThresholds(Model):
    """The thresholds behind the headline probabilities, in the request's units."""

    hourly_precipitation: float
    hourly_snowfall: float
    daily_precipitation: float = field(metadata={JSON_NAME: "daily_precipitation_probability"})
    """(JSON ``daily_precipitation_probability``)"""
    daily_precipitation_occurrence: float = field(
        metadata={JSON_NAME: "daily_precipitation_occurrence_probability"}
    )
    """(JSON ``daily_precipitation_occurrence_probability``)"""
    daily_snow: float = field(metadata={JSON_NAME: "daily_snow_probability"})
    """(JSON ``daily_snow_probability``)"""


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
        value: The share of members meeting the term, 0..1, or ``None``
            (see :attr:`null_reason`). ``None`` is not zero.
        members: The members that voted.
        null_reason: Why :attr:`value` is ``None``; ``None`` otherwise.
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
    value: float | None = field(default=None, metadata={JSON_NAME: "probability"})
    """(JSON ``probability``)"""
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
        start_hours: The window's first hour (JSON ``window_start_hours``).
        end_hours: The window's end hour (JSON ``window_end_hours``).
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
    start_hours: int = field(metadata={JSON_NAME: "window_start_hours"})
    """(JSON ``window_start_hours``)"""
    end_hours: int = field(metadata={JSON_NAME: "window_end_hours"})
    """(JSON ``window_end_hours``)"""
    aggregation: TotalAggregation
    from_: dt.datetime | None = field(default=None, metadata={JSON_NAME: "from"})
    to: dt.datetime | None = None
    quantiles: Quantiles | None = None
    members: int
    method: str | None = None
    """How the total was computed: ``members`` or ``ensemble_moments``."""
    null_reason: NullReason | None = None
    request: Total | None = field(default=None, compare=False, metadata={NOT_JSON: True})

    @property
    def window(self) -> Window:
        """The window as a :class:`~ensemble_weather.Window`."""
        return Window(self.start_hours, self.end_hours)


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

    id: str = field(metadata={JSON_NAME: "station_id"})
    """(JSON ``station_id``)"""
    name: str
    observation_time: dt.datetime
    calm: bool | None = None
    """``True`` when the station reported calm wind."""


@dataclass(frozen=True, kw_only=True)
class CurrentConditions(Model):
    """Right now: a view of one served hour, never a second forecast."""

    time: dt.datetime
    temperature: float
    feels_like: float | None = None
    code: str = field(metadata={JSON_NAME: "condition"})
    """(JSON ``condition``)"""
    text: str = field(metadata={JSON_NAME: "condition_text"})
    """(JSON ``condition_text``)"""
    icon: ConditionIcon = field(metadata={JSON_NAME: "condition_icon"})
    """(JSON ``condition_icon``)"""
    wind_speed: float
    wind_gust: float | None = None
    wind_direction: float
    relative_humidity: float | None = None
    dewpoint: float | None = None
    precipitation_probability: float | None = None
    source: CurrentSource
    station: CurrentStation | None = None
    measured: bool | None = None
    """``True`` when the values are a station's measurement, not the forecast."""
    cloud_cover: float | None = None


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
    location: ForecastLocation
    model_run: ModelRunInfo
    units: UnitSystem
    series: ForecastData = field(metadata={JSON_NAME: "forecast"})
    """(JSON ``forecast``)"""
    elevations: list[ElevationForecast] | None = field(
        default=None, metadata={JSON_NAME: "elevation_forecasts"}
    )
    """(JSON ``elevation_forecasts``)"""
    nowcast_applied: bool
    nowcast_unavailable: list[NowcastLayer] | None = None
    members_view: MembersView | None = None
    gap_flow: GapFlow | None = None
    nearest_sensors: list[NearestSensor] | None = None
    point: PointInfo | None = None
    current: CurrentConditions | None = None
    snow_on_ground: SnowOnGround | None = None
    avalanche: AvalancheForecast | None = None
    """Today's avalanche danger rating for the location's forecast zone, if any."""
    attribution: ResponseAttribution

    def to_dataframe(self) -> pd.DataFrame:
        """The hourly series as a DataFrame; see :meth:`ForecastData.to_dataframe`."""
        return self.series.to_dataframe()


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
    sent: dt.datetime | None = None
    message_type: str | None = None
    """``alert``, ``update`` or ``cancel``."""
    references: list[str] | None = None
    sender_name: str | None = None
    area_desc: str | None = None
    description: str | None = None
    instruction: str | None = None
    source_url: str | None = None
    event_key: str | None = None
    vtec_action: str | None = None


@dataclass(frozen=True, kw_only=True)
class SensorObservation(Model):
    """A recent observation from a nearby station."""

    station_id: str
    name: str
    source: str
    observed_at: dt.datetime = field(metadata={JSON_NAME: "observation_time"})
    """(JSON ``observation_time``)"""
    distance_km: float | None = None
    """The station's distance from the location."""
    elevation_diff: float | None = None
    """The station's elevation minus the location's, in the length unit."""
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
    now: CurrentConditions | None = field(default=None, metadata={JSON_NAME: "current"})
    """(JSON ``current``)"""
    as_of: dt.datetime
    model_run_initialized_at: dt.datetime | None = None
    nowcast_hours: list[TimeSeriesPoint] | None = None
    units: UnitSystem
    attribution: ResponseAttribution
    nowcast_unavailable: list[NowcastLayer] | None = None
    summary: PlaceSummary | None = None
    pass_: PassForecast | None = field(default=None, metadata={JSON_NAME: "pass"})
    """A mountain pass's forecast (JSON ``pass``); ``None`` elsewhere."""


@dataclass(frozen=True, kw_only=True)
class AlertsResponse(Response):
    """Active alerts for a location."""

    location: LocationRef
    count: int = field(metadata={JSON_NAME: "alert_count"})
    """(JSON ``alert_count``)"""
    as_of: dt.datetime
    items: list[ActiveAlert] = field(metadata={JSON_NAME: "alerts"})
    """(JSON ``alerts``)"""
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
    items: list[RunEntry] = field(metadata={JSON_NAME: "runs"})
    """(JSON ``runs``)"""
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
    display_name: str | None = None
    height_m: float = field(metadata={JSON_NAME: "elevation_m"})
    """(JSON ``elevation_m``)"""
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
    status: StationStatus = field(metadata={JSON_NAME: "station_status"})
    """(JSON ``station_status``)"""
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
    variant: TemplateVariant | None = field(default=None, metadata={JSON_NAME: "template_variant"})
    """(JSON ``template_variant``)"""
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
    locale: str = field(metadata={JSON_NAME: "resolved_locale"})
    """(JSON ``resolved_locale``)"""
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
    source_id: str | None = field(default=None, metadata={JSON_NAME: "source_station_id"})
    """(JSON ``source_station_id``)"""
    elevation_msl_m: float | None = None
    sensor_height_agl_m: float | None = None
    sensor_capabilities: list[str] | None = None
    status: StationStatus | None = field(default=None, metadata={JSON_NAME: "station_status"})
    """(JSON ``station_status``)"""
    last_report_at: dt.datetime | None = None
    last_report_summary: Any = None
    install_date: dt.date | None = None
    decommission_date: dt.date | None = None
    update_frequency_minutes: int | None = None
    url: str | None = field(default=None, metadata={JSON_NAME: "station_url"})
    """(JSON ``station_url``)"""
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
    indexable: bool | None = None
    primary_location: PublicCatalogPrimaryLocation | None = None
    template: CatalogTemplateSummary | None = None
    content: list[CatalogResolvedEntry] | None = None


# --- forecast additions ----------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ForecastLocation(LocationRef):
    """The forecast's ``location``.

    The one ``LocationRef`` (every field where it was) plus what a forecast client labels
    and picks with, so the forecast body alone is enough to draw a plume or a meteogram at a
    named elevation (no ``/nearby`` call, no client-side unit conversion).
    """

    elevation: float
    """``elevation_m`` in the request's length units (m for ``metric``/``kelvin``, ft for
    ``imperial``), to 0.1 -- the elevation ``forecast.timeseries`` (and its members) is served
    at.
    """
    elevations: list[ElevationSummary] | None = None
    """The location's named elevations -- exactly the list its ``/nearby`` and list rows serve
    (``LocationSummary.elevations``): the primary first and its ONE ``default: true``, then
    each other elevation (ski-area base / mid / summit), in the request's ...
    """


@dataclass(frozen=True, kw_only=True)
class MemberQuantiles(Quantiles):
    """A distribution over the ensemble MEMBERS.

    (``members_cumulative``, ``members_spread``, ``members_6h``): the ``Quantiles`` shape.
    """


@dataclass(frozen=True, kw_only=True)
class MembersSpread(Model):
    """The members' spread at this hour for the plume's instantaneous variables.

    The Quantiles of every member's own ``temperature`` (temperature unit) and
    ``snow_level`` (length unit) here, over the members as served.
    """

    temperature: MemberQuantiles | None = None
    snow_level: MemberQuantiles | None = None
    snow_level_wet_bulb: MemberQuantiles | None = None
    """The Quantiles of the members' own ``snow_level_wet_bulb`` (the snow level on the NWS
    scale), over the members ``snow_level`` is over.
    """
    slr: MemberQuantiles | None = None
    """The snow-to-liquid ratio over the members SNOWING at this hour (their own ``snowfall``
    above 0), at 00/06/12/18Z only, in both member views.
    """
    wind_speed: MemberQuantiles | None = None
    """The members' own wind speed at this hour, in the wind unit."""


@dataclass(frozen=True, kw_only=True)
class PrecipitationByType(Model):
    """This hour's headline precipitation.

    (``ensemble.precipitation.mean``) split by phase, in the precipitation units -- ``rain +
    snow + rain_snow_mix + freezing_rain`` is the hour's mean (to the served precision), so
    a stacked bar is the headline bar.
    """

    rain: float
    snow: float
    """The liquid that falls as snow (not snow depth; that is ``ensemble.snowfall``)."""
    rain_snow_mix: float
    freezing_rain: float
    """-- liquid that freezes on contact (counted in ``rain`` before)."""


@dataclass(frozen=True, kw_only=True)
class SnowLevelRange(Model):
    """A day's snow level over its wet hours (m, or ft with ``units=imperial``).

    The lowest and highest hourly ensemble-mean snow level among them, and their
    precipitation-weighted mean.
    """

    low: float
    """The lowest hourly snow level among the wet hours."""
    high: float
    """The highest hourly snow level among the wet hours."""
    mean: float
    """The wet hours' snow level, weighted by their precipitation."""


@dataclass(frozen=True, kw_only=True)
class DayNormal(Model):
    """The day's climate normal at the forecast point.

    The mean, over the day of year +/-15 days of every year of the station's record, of the
    very quantities this row states -- the local CALENDAR date's maximum hourly temperature
    (``high``, the quantity ``high`` is), its minimum (``low``) and its precipitation TOTAL
    (``precipitation``, dry days included; a daily total, never an hourly amount).
    """

    high: float | None = None
    """Mean local-calendar-day maximum temperature."""
    low: float | None = None
    """Mean local-calendar-day minimum temperature."""
    precipitation: float | None = None
    """Mean local-calendar-day precipitation total, dry days included."""
    source: str
    """A climatology station's own record, or the ERA5 cell of the point."""
    distance_km: float
    """Great-circle distance from the point to the station (or the cell centre), km."""


@dataclass(frozen=True, kw_only=True)
class DayDeparture(Model):
    """The served headline minus the normal, in the request's units.

    ``high.p50 - normal.high`` and ``low.p50 - normal.low``.
    """

    high: float | None = None
    low: float | None = None


@dataclass(frozen=True, kw_only=True)
class DayPercentile(Model):
    """How unusual the day is.

    Where the served headline (``p50``) falls in the day's climatological distribution, as a
    percentile 0-100, ``Pr{climate <= forecast}`` -- 95 for ``precipitation`` reads "wetter
    than 95% of this date's days".
    """

    high: float | None = None
    low: float | None = None
    precipitation: float | None = None


@dataclass(frozen=True, kw_only=True)
class PrecipOutlook(Model):
    """Rolling liquid-equivalent totals over the same windows as ``snow_outlook``.

    For places where rain is the story (the favorites cards' "0.6 in rain" with its range).
    """

    next_24h: float | None = None
    """Sum of the hourly precipitation means over the 24 h from the first served hour; ``null``
    when not covered.
    """
    next_48h: float | None = None
    """The same over 48 h."""
    next_72h: float | None = None
    """The same over 72 h."""
    next_7d: float | None = None
    """The same over 168 h."""
    quantiles: SnowOutlookQuantiles | None = None


@dataclass(frozen=True, kw_only=True)
class SnowOnGround(Model):
    """What the snowpack model states is on the ground at a spot at one hour."""

    beta: bool
    """Always ``true`` while the product is a beta; fields may be added."""
    depth: float
    """Snow depth: cm, or in (imperial)."""
    basis: str
    """``measured``: the run started from a snow-depth sensor at the spot."""
    surface: str | None = None
    """The surface class at the hour; ``/snowpack``'s ``definitions.surface`` carries the text of
    each value (an open set).
    """
    valid_time: dt.datetime
    """The hour the depth is for."""
    generated_at: dt.datetime
    """When the snowpack run that produced it finished."""


@dataclass(frozen=True, kw_only=True)
class AvalancheForecast(Model):
    """The avalanche center's danger rating for the forecast zone the location's point is in.

    From avalanche.org's public map layer.
    """

    center_id: str
    """The avalanche center's short id."""
    center_name: str
    zone_id: int
    """avalanche.org's id for the forecast zone; for a CAIC forecast area, an id at or above
    2^52 derived from CAIC's area id (stable for that grouping of CAIC's polygons).
    """
    zone_name: str
    danger_level: int | None = None
    """The North American Public Avalanche Danger Scale level, 1-5; present only when
    ``status`` is ``rated``.
    """
    danger_label: str | None = None
    """Display text: the scale's English name for ``danger_level`` (Low, Moderate,
    Considerable, High, Extreme), derived from the level, never the center's own wording;
    ``null`` exactly when ``danger_level`` is.
    """
    status: str
    """``rated``: a current rating."""
    valid_from: dt.datetime | None = None
    """When the center's current product took effect (UTC), when stated."""
    valid_until: dt.datetime | None = None
    """When the center's current product expires (UTC), when stated."""
    url: str = field(metadata={JSON_NAME: "forecast_url"})
    """(JSON ``forecast_url``) The center's full forecast for the zone."""
    center_url: str
    attribution: str
    """The credit to show with the block: "Avalanche forecast by <center> via avalanche.org",
    or "Avalanche forecast by Colorado Avalanche Information Center via
    avalanche.state.co.us" for a CAIC area.
    """


# --- the plume view --------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class MemberPlume(Model):
    """One served series' members in columns (``members=plume``)."""

    headline: PlumeHeadline
    bands: PlumeBands
    models: list[ModelColumns]
    """One entry per model with members in the served window, in the order aifs, aigefs,
    gefs, ifs_ens, rrfs.
    """
    pool: PooledColumns | None = field(default=None, metadata={JSON_NAME: "members"})
    """(JSON ``members``)"""


@dataclass(frozen=True, kw_only=True)
class PlumeHeadline(Model):
    """The lines a plume draws over its members, at every served hour (``valid_time``).

    The blend's ``temperature`` and ``snow_level`` means (``ensemble.*.mean``) and its
    running totals (``cumulative_precipitation``, ``cumulative_snowfall``: the "Ourea
    forecast" line), and that snowfall line at a 10:1 snow-to-liquid ratio
    (``cumulative_snowfall_10to1``), and its ``wind_speed`` mean and its snowfall in each 6
    hours ...
    """

    valid_time: list[dt.datetime]
    temperature: list[float | None]
    snow_level: list[float | None]
    snow_level_wet_bulb: list[float | None]
    """The blend's snow level on the NWS scale (``ensemble.snow_level_wet_bulb.mean``, the
    height of the 0.5 C wet-bulb); ``snow_level`` is the rain line.
    """
    cumulative_precipitation: list[float | None]
    cumulative_snowfall: list[float | None]
    """The hourly series' ``cumulative_snowfall``: the running sum of the day cards' snowfall
    (``daily[].precipitation_display.snow_amount``), spread inside each local date by the
    blend's hourly mean snowfall, so at the end of each date served whole ...
    """
    cumulative_snowfall_10to1: list[float | None]
    """The headline's running snowfall at a fixed 10:1 snow-to-liquid ratio, in the snowfall
    units (in / mm), at the amount precision: each hour's served snowfall with its SLR
    (``ensemble.slr.mean``) replaced by 10 -- the liquid that falls as snow, ...
    """
    wind_speed: list[float | None]
    """The forecast's hourly wind speed, the hourly series' ``ensemble.wind_speed.mean``, in
    the wind unit (mph / km/h / m/s as ``units`` says) at the wind precision (0.1), at every
    served hour.
    """
    snowfall_6h: list[float | None]
    """The forecast's snowfall in the 6 hours ending at each 00/06/12/18Z hour, in the
    snowfall units (in / mm) at the amount precision: the rise of ``cumulative_snowfall``
    over ``(valid_time - 6 h, valid_time]``, computed here so no client ...
    """


@dataclass(frozen=True, kw_only=True)
class PlumeBands(Model):
    """The members' distributions, at the served hours that carry at least one (``valid_time``.

    The synoptic hours in practice): ``cumulative_precipitation`` / ``cumulative_snowfall``
    are the row form's ``members_cumulative`` (the spread of the members' running totals,
    never a sum of hourly percentiles), ``temperature`` / ``snow_level`` its
    ``members_spread``, ``precipitation_6h`` / ``snowfall_6h`` its ``members_6h`` ...
    """

    valid_time: list[dt.datetime]
    cumulative_precipitation: BandColumns
    cumulative_snowfall: BandColumns
    cumulative_snowfall_10to1: BandColumns
    """The members' running snowfall at 10:1 -- each member's snowfall with its SLR replaced
    by 10 (its snowing liquid x 10, every phase gate of its ``snowfall`` kept, the
    ``snowfall_total_10to1`` map's member rule), totalled as ``cumulative_snowfall`` ...
    """
    temperature: BandColumns
    snow_level: BandColumns
    snow_level_wet_bulb: BandColumns
    """The row form's ``members_spread.snow_level_wet_bulb`` -- the members' snow level on the
    NWS scale, at the hours ``snow_level`` carries a band.
    """
    precipitation_6h: BandColumns
    snowfall_6h: BandColumns
    slr: BandColumns | None = None
    wind_speed: BandColumns | None = None
    """``members_spread.wind_speed``."""


@dataclass(frozen=True, kw_only=True)
class BandColumns(Model):
    """One band's statistics.

    (Hyndman-Fan type 7 over the served member values), each an array aligned to
    ``PlumeBands.valid_time``, ``null`` where the band is absent at that hour.
    """

    mean: list[float | None]
    min: list[float | None]
    p10: list[float | None]
    p25: list[float | None]
    p50: list[float | None] | None = None
    p75: list[float | None]
    p90: list[float | None]
    max: list[float | None]


@dataclass(frozen=True, kw_only=True)
class PooledColumns(Model):
    """The members as ONE unlabelled pool, for a caller without the plume's paid detail.

    (Free and anonymous; ``members_view: pool``).
    """

    valid_time: list[dt.datetime]
    temperature: list[list[float | None]]
    precipitation: list[list[float | None]]
    precipitation_hours: list[list[int | None]]
    """``[member][step]``: the hours each ``precipitation`` and ``snowfall`` value covers: the grid
    step (6), less where a member's first value covers less; ``null`` where the value is
    absent.
    """
    cumulative_precipitation: list[list[float | None]]
    snow_level: list[list[float | None]]
    snow_level_wet_bulb: list[list[float | None]]
    snowfall: list[list[float | None]]
    cumulative_snowfall: list[list[float | None]]
    slr: list[list[float | None]]
    cumulative_precipitation_band_members: list[int]
    """The rows (indices into every column) in ``bands.cumulative_precipitation``'s fixed
    population, ascending: that band's ``mean`` is the mean of these rows' running totals.
    """
    cumulative_snowfall_band_members: list[int]
    """Likewise for ``bands.cumulative_snowfall``."""
    cumulative_snowfall_10to1_band_members: list[int]
    """Likewise for ``bands.cumulative_snowfall_10to1``."""


@dataclass(frozen=True, kw_only=True)
class ModelColumns(Model):
    """One model's members over its NATIVE steps inside the served window (``valid_time``.

    The hours at which a member of the model carries a value -- every hour for RRFS, every
    sixth for the global ensembles; never padded to the hourly series).
    """

    id: str
    valid_time: list[dt.datetime]
    member_ids: list[int]
    """The members, ascending (``MemberForecast.member_id``)."""
    temperature: list[list[float | None]]
    precipitation: list[list[float | None]]
    precipitation_hours: list[list[int | None]]
    """``[member][step]``: the hours each ``precipitation`` value covers; ``null`` where it is
    absent or its span unknown.
    """
    cumulative_precipitation: list[list[float | None]]
    snow_level: list[list[float | None]]
    snow_level_wet_bulb: list[list[float | None]]
    """``[Member][step]``, each member's ``MemberForecast.snow_level_wet_bulb`` (the snow level
    on the NWS scale); ``null`` exactly where its ``snow_level`` is.
    """
    snowfall: list[list[float | None]]
    cumulative_snowfall: list[list[float | None]]
    cumulative_snowfall_p50: list[float | None]
    """One value per ``valid_time`` step (not per member): the median of the model's members'
    ``cumulative_snowfall`` there (Hyndman-Fan type 7, as ``bands``: the middle value, or the
    midpoint of the two middle ones; a single-member model's own total), ...
    """
    cumulative_snowfall_10to1_p50: list[float | None]
    """As ``cumulative_snowfall_p50``, over the members' running snowfall at 10:1 (see
    ``PlumeBands.cumulative_snowfall_10to1``).
    """
    temperature_mean: list[float | None]
    """The model's mean lines."""
    precipitation_mean: list[float | None]
    """The mean of ``precipitation`` (see ``temperature_mean``)."""
    cumulative_precipitation_mean: list[float | None]
    """The mean of ``cumulative_precipitation`` (see ``temperature_mean``)."""
    snow_level_mean: list[float | None]
    """The mean of ``snow_level`` (see ``temperature_mean``)."""
    snow_level_wet_bulb_mean: list[float | None]
    """The mean of ``snow_level_wet_bulb`` (see ``temperature_mean``)."""
    snowfall_mean: list[float | None]
    """The mean of ``snowfall`` (see ``temperature_mean``)."""
    cumulative_snowfall_mean: list[float | None]
    """The mean of ``cumulative_snowfall`` (see ``temperature_mean``), beside its median
    ``cumulative_snowfall_p50``.
    """
    cumulative_snowfall_10to1_mean: list[float | None]
    """The mean of the members' running snowfall at 10:1, beside
    ``cumulative_snowfall_10to1_p50`` (the members' 10:1 column itself is not served).
    """
    wind_speed_mean: list[float | None] | None = None
    """The mean of ``wind_speed`` (see ``temperature_mean``)."""
    cumulative_precipitation_band_member_ids: list[int]
    """Which of this model's ``member_ids`` are in ``bands.cumulative_precipitation``, ascending."""
    cumulative_snowfall_band_member_ids: list[int]
    """As ``cumulative_precipitation_band_member_ids``, for ``bands.cumulative_snowfall``."""
    cumulative_snowfall_10to1_band_member_ids: list[int]
    """As ``cumulative_precipitation_band_member_ids``, for ``bands.cumulative_snowfall_10to1``."""
    wind_speed: list[list[float | None]] | None = None
    """Pro (``members_view: full``) only; absent in the plume view."""
    wind_direction: list[list[float | None]] | None = None
    """Pro only; absent in the plume view."""
    slr: list[list[float | None]] | None = None
    """In both views."""


# --- place summary and mountain passes -------------------------------------------


@dataclass(frozen=True, kw_only=True)
class PlaceSummary(Model):
    """A short plain-language summary of what is coming at a place.

    Written by the server from templates filled with served values (never free text from a
    model).
    """

    short: str
    """One sentence: the most important thing at the place, by priority (an NWS alert,
    precipitation starting or stopping soon, snow coming, wind or a large temperature
    change, then the day's headline).
    """
    long: list[str]
    """One to three sentences for the location page, each from a different kind of event."""
    events: list[SummaryEvent]
    """The event behind each sentence of ``long``, in the same order (``events[i]`` wrote
    ``long[i]``), so a client can style a sentence (an alert chip, a snow icon) without
    parsing text.
    """
    elevation_name: str | None = None
    """The served elevation the sentences describe: its display name where the catalog has
    one, else its name.
    """
    elevation: float
    """The height the sentences describe, in the response's length units (m, ft)."""
    run: dt.datetime
    """The init of the forecast run the sentences were written from."""
    generated_at: dt.datetime
    """When the sentences were written (the request's now); the "updated" stamp."""


@dataclass(frozen=True, kw_only=True)
class SummaryEvent(Model):
    """One event behind a place summary's sentences (its template and values)."""

    kind: str
    """What the sentence is about."""
    template: str
    """The phrasing used, ``<template>.<variant>`` (``snow_coming.v1.3``), stable across releases
    so sentences can be counted, reviewed and later translated.
    """
    at: dt.datetime | None = None
    """The hour the event begins (precipitation starting or stopping, an alert's onset, a
    pass event).
    """
    until: dt.datetime | None = None
    """When the event ends, where the sentence says so (an alert's end, a snow window's end)."""
    alert_id: str | None = None
    """The ``alerts[].id`` an ``alert`` event states."""
    values: SummaryValues | None = None
    """The served numbers the sentence states, unrounded, in the response's units."""


@dataclass(frozen=True, kw_only=True)
class SummaryValues(Model):
    """Each number a summary sentence states, as served."""

    snowfall: float | None = None
    """The window's headline snowfall total (mm, in): for ``snow_coming`` the forecast's
    ``snow_outlook.<snowfall_window>``; for ``pass_snow_starts`` the window's
    ``pass.snow_windows[].total``.
    """
    snowfall_p10: float | None = None
    """The window's served p10 (``snow_outlook.quantiles.<window>.p10``, or the pass window's
    ``p10``).
    """
    snowfall_p90: float | None = None
    """The window's served p90."""
    snowfall_window: str | None = None
    """Which window ``snowfall`` totals."""
    temperature: float | None = None
    """A day's served high (``daily[].high.mean``) a ``day_headline`` or ``temperature_change``
    states.
    """
    wind_gust: float | None = None
    """The served hourly gust mean (``ensemble.wind_gust.mean``) a ``wind`` sentence states."""
    precipitation_probability: float | None = None
    """The served chance (0-1) behind the sentence's likelihood word."""


@dataclass(frozen=True, kw_only=True)
class PassForecast(Model):
    """Is the pass getting weather? At the pass's own point and elevation.

    Forecast quantities only, in the response's units.
    """

    elevation: float
    """The pass's elevation, in the response's length units (m, ft)."""
    elevation_m: float
    """The pass's elevation in metres, whatever ``units`` is."""
    from_: dt.datetime = field(metadata={JSON_NAME: "from"})
    """The first hour of ``hours`` (the hour containing now); the 24 h and 48 h windows open
    here.
    """
    snow_24h: PassSnow24h
    chances: PassChances
    snow_windows: list[PassSnowWindow]
    """Each spell of snow at the pass in the next 48 h, in time order; empty when none."""
    hours: list[PassHour]
    """The next 48 hours at the pass, from ``from``, one per hour."""
    windows: PassTravelWindows
    official_status: PassOfficialStatus | None = None
    road_sensors: list[PassRoadSensor] | None = None
    """The state DOT road-weather stations nearest the pass, nearest first: at most 3, within
    25 km, each with its newest reading in the last 3 h.
    """
    cameras: list[PassCamera] | None = None
    """The DOT's own cameras at the pass, in the order the pass's curation lists them."""


@dataclass(frozen=True, kw_only=True)
class PassSnow24h(Model):
    """The next 24 h of snow at the pass.

    Exactly the default forecast's own ``snow_outlook.next_24h`` and
    ``snow_outlook.quantiles.next_24h`` (unpinned, the nowcast on, the same cycle), so the
    pass page, the passes board and search state one number.
    """

    total: float | None = None
    """``snow_outlook.next_24h`` (mm, in); null where the forecast does not reach 24 h."""
    p10: float | None = None
    """``snow_outlook.quantiles.next_24h.p10``; null without members covering the window."""
    p90: float | None = None
    """``snow_outlook.quantiles.next_24h.p90``."""
    starts_at: dt.datetime | None = None
    """The start of the first snow spell (``snow_windows[0].start``) when it begins inside the
    24 h; null otherwise.
    """


@dataclass(frozen=True, kw_only=True)
class PassChances(Model):
    """Chances at the pass over the next ``window_hours`` hours.

    Each the share of the forecast's members meeting the event (the ``?prob=`` machinery),
    except the gust chance (see its ``method``).
    """

    window_hours: int
    """The window's length, 24."""
    from_: dt.datetime = field(metadata={JSON_NAME: "from"})
    to: dt.datetime
    p_snow_ge_1in: PassChance
    """Snowfall total over the window of 1 in (25.4 mm) or more: `prob=snowfall:ge:<1
    in>:24h`.
    """
    p_snow_ge_6in: PassChance
    """Snowfall total over the window of 6 in (152.4 mm) or more."""
    p_wet_below_freezing: PassChance
    """Some hour of the window in which the member is at or below freezing (``threshold``: 0 C,
    32 F) with precipitation of at least ``precipitation_threshold`` (0.254 mm, 0.01 in) in
    the member's value ending at that hour: a wet road at or below ...
    """
    p_gust_gt_40mph: PassChance
    """A gust over 40 mph (17.9 m/s; threshold fixed, does not change with units) in the
    window.
    """


@dataclass(frozen=True, kw_only=True)
class PassChance(Model):
    """One pass chance: a probability with its threshold and members, never a bare number."""

    probability: float | None = None
    """0-1 (0.001); null when it cannot be answered (``null_reason``)."""
    threshold: float
    """The event's threshold, in the response's units."""
    precipitation_threshold: float | None = None
    """For ``p_wet_below_freezing``, the precipitation that makes an hour wet, in the
    response's units.
    """
    members: int
    """The members that voted (0 for ``hourly_gust_distribution``)."""
    method: str
    null_reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class PassSnowWindow(Model):
    """One window of snow at the pass: its start, end and snowfall range."""

    start: dt.datetime
    """When the first snowing hour begins (its ``valid_time`` minus 1 h)."""
    end: dt.datetime
    """When the last snowing hour ends (its ``valid_time``)."""
    total: float
    """The sum of the hourly snowfall means over the spell (mm, in), as ``snow_outlook`` sums
    its windows.
    """
    p10: float | None = None
    """The p10 of the members' own totals over the spell (``?totals=`` machinery); omitted
    without enough members.
    """
    p90: float | None = None
    """The p90 of the members' own totals over the spell."""
    p_ge_1in: float | None = None
    """The share of members whose own total over the spell is 1 in (25.4 mm) or more;
    threshold fixed, does not change with units.
    """


@dataclass(frozen=True, kw_only=True)
class PassHour(Model):
    """One hour at the pass: the road-relevant forecast values."""

    time: dt.datetime
    """The hour's ``valid_time``; amounts are over the hour ending then."""
    temperature: float
    """``ensemble.temperature.mean``."""
    precipitation: float
    """``ensemble.precipitation.mean`` (mm, in)."""
    precipitation_probability: float | None = None
    """``ensemble.precipitation.probability``, 0-1."""
    precipitation_type: str | None = None
    """The hour's served ``precipitation_type.type``; omitted on a dry hour."""
    snowfall: float
    """``ensemble.snowfall.mean`` (mm, in); 0 without snow."""
    snow_level: float | None = None
    """``ensemble.snow_level.mean`` (m, ft); omitted where not served."""
    snow_level_margin: float | None = field(
        default=None, metadata={JSON_NAME: "snow_level_above_pass"}
    )
    """(JSON ``snow_level_above_pass``) ``snow_level`` minus the pass's elevation (m, ft).

    Above 0 the snow level is above the pass (rain at the pass when wet), below 0 it is
    under it.
    """
    freezing_on_wet_road: bool
    """The hour is at or below freezing (temperature mean at or below 0 C, 32 F) and wet:
    precipitation of at least 0.254 mm (0.01 in) in this hour or one of the two before it.
    """
    wind_speed: float
    """``ensemble.wind_speed.mean``."""
    wind_gust: float | None = None
    """``ensemble.wind_gust.mean``; omitted where not served."""
    gust_over_40mph: bool
    """``wind_gust`` is over 40 mph (17.9 m/s); threshold fixed, does not change with units."""
    blowing_snow: bool
    """Gusts of 25 mph (11.2 m/s) or more at or below freezing with loose snow to move: snow
    falling this hour, 1 in (25.4 mm) or more fallen in the 24 served hours before it, or
    snow on the ground at the pass (``snow_on_ground``).
    """


@dataclass(frozen=True, kw_only=True)
class PassTravelWindows(Model):
    """The least- and most-weather travel windows at the pass.

    The quietest and the busiest stretch of weather at the pass in the next
    ``horizon_hours``, by one fixed rule on the hours above: an hour has weather when it is
    snowing (``snowfall`` at least 0.04 in, 1 mm), ``freezing_on_wet_road``, or
    ``gust_over_40mph``.
    """

    horizon_hours: int
    """The horizon's length in hours, 24."""
    least_weather: PassTravelWindow | None = None
    """Null when every hour has weather."""
    most_weather: PassTravelWindow | None = None
    """Null when no hour has weather."""


@dataclass(frozen=True, kw_only=True)
class PassTravelWindow(Model):
    """One travel window: its start, end and the weather it holds."""

    start: dt.datetime
    """When the run's first hour begins."""
    end: dt.datetime
    """When its last hour ends."""
    snowfall: float
    """The sum of the hourly snowfall means over the run (mm, in)."""
    freezing_on_wet_road_hours: int
    max_wind_gust: float | None = None
    """The highest hourly gust mean in the run; omitted where no gust is served."""


@dataclass(frozen=True, kw_only=True)
class PassOfficialStatus(Model):
    """The DOT's own status for the road over the pass.

    Chain controls and closures as the DOT publishes them, its wording verbatim.
    """

    source: str
    """The DOT feed."""
    attribution: str
    """Who to credit, as the client shows it."""
    url: str
    """The DOT's own page for this road, to link out to."""
    checked_at: dt.datetime
    """How fresh the DOT's feed behind these segments was at Ourea's last read: the time the
    DOT wrote the file Ourea last read (Caltrans rewrites it every minute; Ourea reads it
    every 5), and the older of two when the segments span two DOT ...
    """
    stale: bool
    """``checked_at`` is more than 30 minutes before ``as_of``."""
    level: PassStatusLevel
    segments: list[PassStatusSegment]
    """The DOT's chain-control and closure points on the road over the pass, each direction,
    in the pass's curated order.
    """


@dataclass(frozen=True, kw_only=True)
class PassStatusSegment(Model):
    """One DOT chain-control or closure point, as the DOT publishes it."""

    id: str
    """The DOT's own id for the point."""
    route: str
    direction: str
    """The direction the point controls, as the DOT names it."""
    location: str
    """The DOT's name for the point (its trailing field padding removed)."""
    state: str = field(metadata={JSON_NAME: "status"})
    """(JSON ``status``) The DOT's status code, verbatim."""
    level: PassStatusLevel
    text: str = field(metadata={JSON_NAME: "status_text"})
    """(JSON ``status_text``) The DOT's own description of the status, verbatim."""
    updated_at: dt.datetime
    """When the DOT set this status."""
    lat: float
    lon: float
    road_condition: str | None = None
    """The DOT's own report of the road surface there, verbatim, where it gives one beside
    the restriction (WSDOT, ODOT).
    """
    weather_condition: str | None = None
    """The DOT's own report of the weather there, verbatim (WSDOT, ODOT)."""


@dataclass(frozen=True, kw_only=True)
class PassRoadSensor(Model):
    """One state DOT road-weather station's newest reading, in the response's units."""

    station_id: str
    """The station's id in its network."""
    name: str
    """The station's registry name, else its id."""
    source: str
    """The feed: ``rwis`` (Caltrans CWWP2 RWIS) or ``wsdot``."""
    attribution: str
    """Who measured it, as the client credits it."""
    distance_km: float
    """Straight-line distance from the pass, km."""
    elevation: float | None = None
    """The station's registry elevation in the response's length units (m, ft)."""
    elevation_m: float | None = None
    """The station's registry elevation in metres."""
    observed_at: dt.datetime
    stale: bool
    """``observed_at`` is more than 60 minutes before ``as_of``."""
    pavement_condition: str | None = None
    """The pavement state the sensor reports (NTCIP 1204 essSurfaceStatus as ``/current``
    sensors serve it: dry, trace_moisture, wet, chemically_wet, ice_warning, ice_watch,
    snow_warning, snow_watch, absorption, dew, frost, absorption_at_dewpoint).
    """
    pavement_temp: float | None = None
    """Pavement surface temperature: °C, °F (imperial) or K (kelvin)."""
    subsurface_temp: float | None = None
    """As ``pavement_temp``."""
    temperature: float | None = None
    """Air temperature, as ``pavement_temp``."""
    wind_speed: float | None = None
    """m/s or mph (imperial)."""
    wind_gust: float | None = None
    """As ``wind_speed``."""
    wind_direction: float | None = None
    """Degrees clockwise from north."""
    visibility: float | None = None
    """m, or statute miles (imperial)."""


@dataclass(frozen=True, kw_only=True)
class PassCamera(Model):
    """One DOT camera, a still image the DOT refreshes about once a minute."""

    id: str
    title: str
    """The DOT's name for the camera."""
    image_url: str
    """The DOT's current still image."""
    url: str
    """The DOT's own page for the camera, to link out to."""
    captured_at: dt.datetime | None = None
    """The image's time (its Last-Modified) when Ourea last checked it, every 15 minutes; the
    image at ``image_url`` may be newer.
    """
    stale: bool
    """``captured_at`` is unknown or more than 60 minutes before ``as_of``: the camera may be
    frozen.
    """
    source: str
    attribution: str


# --- explore ---------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ExploreResponse(Response):
    """One page of a ranking."""

    metric: str
    order: str
    units: UnitSystem
    unit: str
    """The unit of every ``value``, ``p10`` and ``p90``."""
    items: list[ExploreItem]
    count: int
    """Items on this page."""
    next_cursor: str | None = None
    """Pass as ``?cursor=`` (same other parameters) for the next page; null at the end."""


@dataclass(frozen=True, kw_only=True)
class ExploreItem(Model):
    """One ranked point of a place."""

    rank: int
    """1-based, across pages."""
    location: LocationRef
    elevation_name: str | None = None
    """The named elevation; ``null`` = the place's own point."""
    elevation_display_name: str | None = None
    """What the elevation ``elevation_name`` is called, as ``ElevationSummary.display_name``;
    absent where it has no name.
    """
    elevation: float
    """The point's elevation, m or ft by ``units``."""
    value: float
    """The metric's value as the place's page serves it, in ``unit``."""
    p10: float | None = None
    """Present only on ``snow_today`` (the day's served ``total_snowfall.p10``, where it has a
    ``snow_amount``) and ``precip_today`` (``total_precipitation_if_wet.p10``, where the day is
    not ``none``).
    """
    p90: float | None = None
    """As ``p10``."""
    as_of: dt.datetime
    """When the value was taken: the forecast windows when recorded from the served run,
    ``base_depth`` its hour, ``new_snow_24h`` the snowpack run's first hour, the season its
    newest computed day.
    """
    initialized_at: dt.datetime | None = None
    """Forecast windows only, the served run's ``model_run.initialized_at``."""
    source: str
    distance_km: float | None = None
    """With ``near`` only, from it (0.1 km)."""
    path: str
    """The place's forecast route; add ``?elevations=<elevation_name>`` for a named point."""


@dataclass(frozen=True, kw_only=True)
class ExploreValue(Model):
    """A search hit's Explore value; the fields mean what an ``ExploreItem``'s do."""

    metric: str
    value: float
    unit: str
    p10: float | None = None
    p90: float | None = None
    as_of: dt.datetime
    initialized_at: dt.datetime | None = None
    source: str


# --- composition -----------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class CompositionResponse(Response):
    """``GET /api/v1/composition``."""

    initialized_at: dt.datetime
    """The reference init: the newest contributing cycle, a forecast's
    ``model_run.initialized_at``.
    """
    models: list[ModelEntry]
    """Each contributing model, its own cycle and its members (``members`` absent only when the
    cycle's member count is not known).
    """
    model_count: int
    """Entries in ``models``."""
    total_members: int
    """The sum of ``models[].members``: the members the blend draws on."""


# --- season ----------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class SeasonResponse(Response):
    """-- observed season-to-date precipitation at a location."""

    location: LocationRef
    water_year: int
    """The water year by its ending year."""
    starts: dt.date
    """The first local day of the water year."""
    through: dt.date
    """The last local day with an observed row (the day before ``starts`` when there is none)."""
    as_of: dt.datetime | None = None
    """When the newest day row was computed; null with no rows."""
    units: UnitSystem
    precipitation: SeasonTotal | None = None
    """Null until the location has an observed day."""
    snowfall: SeasonTotal | None = None
    """Always null for now; season snowfall is not served yet."""
    station: SeasonStation | None = None
    """The nearest SNOTEL or SCAN gauge within 25 km and 300 m with rows this water year, or
    null.
    """
    daily: list[SeasonDay] | None = None
    """Only with ``include=daily``."""
    attribution: ResponseAttribution


@dataclass(frozen=True, kw_only=True)
class SeasonTotal(Model):
    """A season-to-date total: the amount, its source, coverage and normal."""

    amount: float = field(metadata={JSON_NAME: "total"})
    """(JSON ``total``) Sum over the covered days, in ``unit``."""
    unit: str
    source: str
    """``mrms_multisensor``: the gridded analysis at the location; ``station_gauge``: the
    location is a gauge site and this is the gauge's accumulator.
    """
    days_covered: int
    days_missing: int
    """Days since ``starts`` with no complete observation; not counted as dry."""
    provisional_days: int
    """Covered days still inside the 7-day restate window."""
    normal_to_date: float | None = None
    """PRISM 1991-2020 over the covered days, in ``unit``; null where no normal is loaded."""
    percent_of_normal: int | None = None
    normal_source: str | None = None


@dataclass(frozen=True, kw_only=True)
class SeasonStation(Model):
    """The station whose season-to-date record is shown beside the total."""

    id: str
    """The NRCS station triplet."""
    network: str
    name: str
    distance_km: float
    elevation_m: float
    precipitation_total: float | None = None
    """The gauge's water-year accumulator on ``through`` (mm or in)."""
    precipitation_percent_of_median: int | None = None
    swe: float | None = None
    """Snow water equivalent on ``through`` (mm or in)."""
    swe_percent_of_median: int | None = None
    snow_depth: float | None = None
    """Snow depth on ``through`` (cm or in)."""
    through: dt.date
    """The gauge's newest day."""


@dataclass(frozen=True, kw_only=True)
class SeasonDay(Model):
    """One day of the season's daily record (``include=daily``)."""

    date: dt.date
    precipitation: float | None = None
    """The day's total; null when an hour was not observed."""
    snowfall: float | None = None
    """Always null for now."""
    provisional: bool


# --- snow trend ------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class SnowTrendResponse(Response):
    """-- each recent run's daily snowfall at a location's point, by source."""

    location: LocationRef
    units: UnitSystem
    elevation: SnowTrendResponseElevation
    """The point the grids are for."""
    retention_days: int
    """How many days back runs are kept."""
    dates: list[dt.date]
    """The columns, location-local dates ascending."""
    grids: list[SnowTrendGrid]
    """``ourea`` first; with the ``model_data`` entitlement then ``aifs``, ``aigefs``, ``gefs``,
    ``ifs_ens`` and ``rrfs``.
    """


@dataclass(frozen=True, kw_only=True)
class SnowTrendResponseElevation(Model):
    """The point the grids are for."""

    name: str | None = None
    """The named elevation; ``null`` for a location with one point."""
    display_name: str | None = None
    """What that elevation is called, as ``ElevationSummary.display_name``; absent where it has
    no name.
    """
    height: float = field(metadata={JSON_NAME: "elevation"})
    """(JSON ``elevation``) Its elevation, in m (metric) or ft (imperial)."""


@dataclass(frozen=True, kw_only=True)
class SnowTrendGrid(Model):
    """One source's grid: ``ourea`` (the served forecast) or a model (Pro)."""

    source: str
    """``ourea``, or a model id."""
    runs: list[SnowTrendRun]
    """Oldest first; the last is the newest."""


@dataclass(frozen=True, kw_only=True)
class SnowTrendRun(Model):
    """One run's row of the grid: its init and one cell per date."""

    backfilled: bool
    """``true``: re-rendered after the fact from the pinned run (``?run=<initialized_at>``) by
    the post-deploy backfill -- today's calibration and no live nowcast, so it can differ
    slightly from what was served then.
    """
    initialized_at: dt.datetime
    """``ourea``: the served body's ``model_run.initialized_at``."""
    days: list[SnowTrendDay | None]
    """One entry per ``dates`` entry, in order; ``null`` where the run has no value."""


@dataclass(frozen=True, kw_only=True)
class SnowTrendDay(Model):
    """One cell of the grid: a run's snowfall for one local day."""

    date: dt.date
    """The ``dates`` entry this day is for."""
    amount: float | None = field(default=None, metadata={JSON_NAME: "snow"})
    """(JSON ``snow``) The day's snowfall in mm (metric) or inches (imperial), at the served amount
    precision.
    """
    partial: bool
    """The run covers only part of this local day."""
    p10: float | None = None
    """The range's low end."""
    p90: float | None = None
    """The range's high end, as ``p10``."""
    kind: str | None = None
    """``ourea`` only: the day's ``precipitation_display.kind``."""


# --- snowpack (beta) -------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class SnowpackResponse(Response):
    """The snowpack forecast of a location's spots."""

    beta: bool
    """Always ``true`` while the product is a beta; fields may be added."""
    location: LocationRef
    units: UnitSystem
    model_run: SnowpackRun | None = None
    stale: bool
    """The newest run's blend cycle is more than 24 h old."""
    spots: list[SnowpackSpot]
    """The location's own point first, then its named elevations in their display order."""
    definitions: SnowpackResponseDefinitions


@dataclass(frozen=True, kw_only=True)
class SnowpackResponseDefinitions(Model):
    """What the snowpack codes (surface, grain form) mean, for display."""

    surface: dict[str, str]
    """Each surface class and what it means."""
    layer_form: dict[str, str]
    """Each layer form and what it is."""


@dataclass(frozen=True, kw_only=True)
class SnowpackRun(Model):
    """The newest snowpack run among the spots served."""

    initialized_at: dt.datetime
    """The blend cycle the snowpack model was driven with."""
    generated_at: dt.datetime
    model: SnowpackModel


@dataclass(frozen=True, kw_only=True)
class SnowpackModel(Model):
    """The snow model that produced the run, and its licence."""

    name: str
    by: str
    license: str
    version: str | None = None
    """The build that ran: the commits of Ourea's SNOWPACK and MeteoIO source it was built
    from, as ``snowpack <commit> meteoio <commit>``.
    """


@dataclass(frozen=True, kw_only=True)
class SnowpackSpot(Model):
    """The snowpack at one of a location's spots (an elevation)."""

    name: str | None = None
    """The named elevation (``location.elevations[].name``); ``null`` is the location's own
    point.
    """
    display_name: str | None = None
    """What the named elevation is called, as ``ElevationSummary.display_name``; absent for the
    location's own point and where the catalog has no name for the elevation.
    """
    elevation: float
    """In the response's units (m or ft)."""
    elevation_m: float
    initialized_at: dt.datetime
    """The blend cycle this spot's forecast was driven with; older than
    ``model_run.initialized_at`` when the newest run did not reach the spot.
    """
    anchor: SnowpackSpotAnchor | None = None
    """The snow-depth sensor at the spot."""
    depth: SnowpackDepth
    depth_change_24h: float | None = None
    """The depth at ``depth.start_time`` less this spot's modelled depth 24 h before, in the
    depth's units and rounding (cm or in; a loss is negative): the model's own change,
    snowfall, settlement and melt together.
    """
    swe: list[float]
    """Hourly snow water equivalent (mm or in), parallel to ``depth.p50``."""
    steps: list[SnowpackStep]
    """One entry every six hours."""
    layers: list[SnowpackLayer]
    """Buried layers at ``depth.start_time``, at most three."""
    aspects: list[SnowpackAspect] | None = None
    """The snow on a 38° slope at the spot facing each way, in the order north, east, south,
    west.
    """


@dataclass(frozen=True, kw_only=True)
class SnowpackSpotAnchor(Model):
    """The snow-depth sensor at the spot."""

    station: str
    """The station's catalog slug."""
    name: str
    network: str


@dataclass(frozen=True, kw_only=True)
class SnowpackStep(Model):
    """One time step of a spot's snowpack: its surface and new snow."""

    valid_time: dt.datetime
    surface: str
    """A key of ``definitions.surface``: today ``none``, ``powder``, ``wind_affected``, ``settled``,
    ``wet``, ``crust`` or ``ice_crust``.
    """
    new_snow_24h: float
    """New snow of the 24 h to ``valid_time``, as it lies (cm or in)."""
    new_snow_density_kg_m3: float | None = None
    """Its density."""
    settlement_24h: float | None = None
    """How far the snow on the ground 24 h earlier settled (cm or in)."""


@dataclass(frozen=True, kw_only=True)
class SnowpackLayer(Model):
    """One layer of a spot's modelled snowpack."""

    form: str
    """A key of ``definitions.layer_form``: today ``faceted_grains``, ``depth_hoar``,
    ``buried_surface_hoar``, ``melt_freeze_crust``, ``ice_layer`` or ``rounding_facets``.
    """
    thickness: float
    """cm or in."""
    depth: float
    """From the surface down to the layer's top (cm or in)."""
    formed: dt.date


@dataclass(frozen=True, kw_only=True)
class SnowpackAspect(Model):
    """The snow on one slope at a spot, described as the spot's flat ground is.

    The model run on a slope of ``slope_angle_deg`` facing ``aspect``, with the flat
    ground's snowfall and the slope's own sun.
    """

    facing: str = field(metadata={JSON_NAME: "aspect"})
    """(JSON ``aspect``) The way the slope faces: ``north``, ``east``, ``south`` or ``west``."""
    slope_angle_deg: float
    """How steep the slope is, degrees from horizontal."""
    depth: SnowpackDepth
    """Hourly snow depth on the slope, measured vertically as the flat depth is."""
    depth_change_24h: float | None = None
    """As the spot's ``depth_change_24h``, this slope's own (open loop on both sides), read
    from the same earlier run as the spot's and from no other.
    """
    steps: list[SnowpackStep]
    """One entry every six hours, at the spot's own ``steps[].valid_time``."""
    layers: list[SnowpackLayer]
    """Buried layers on the slope at ``depth.start_time``, at most three."""


@dataclass(frozen=True, kw_only=True)
class SnowpackDepth(Model):
    """Hourly snow depth from ``start_time`` (cm or in)."""

    start_time: dt.datetime
    interval_hours: int
    basis: str
    """``measured``: started from a sensor reading at the spot."""
    p10: list[float] | None = None
    p50: list[float]
    p90: list[float] | None = None


@dataclass(frozen=True, kw_only=True)
class SnowpackPlumeResponse(Response):
    """A location's snow-depth plume."""

    beta: bool
    """Always ``true`` while the product is a beta; fields may be added."""
    location: LocationRef
    units: UnitSystem
    model_run: SnowpackRun | None = None
    """The run the plume is from: the 12Z blend cycle the members were read from."""
    stale: bool
    """The plume's blend cycle is more than 24 h old."""
    depth: SnowpackPlumeDepth | None = None
    """The members' depth at each step."""
    models: list[SnowpackPlumeModel] | None = None
    """Every member's own series, by model, each model to its own horizon."""
    member_depths: list[list[float]] | None = None
    """Every member's depth as ONE unlabelled pool, for Free and anonymous callers (absent
    for Plus and Pro, who are served ``models``).
    """
    spread: str
    """What the bands are, in a sentence a client may show beside them."""


@dataclass(frozen=True, kw_only=True)
class SnowpackPlumeDepth(Model):
    """The members' depth at each step."""

    start_time: dt.datetime
    """The time of the first value of every series in the body."""
    interval_hours: int
    """Hours between values (3)."""
    members: list[int]
    """Members that reach each step; it falls where a model's horizon ends."""
    p50: list[float] | None = None
    """The members' median depth, in the response's units."""
    mean: list[float]
    """Served to every caller, as the bands are."""
    p10: list[float]
    """Every caller (Plus and Pro only before)."""
    p25: list[float]
    """Every caller (Plus and Pro only before)."""
    p75: list[float]
    """Every caller (Plus and Pro only before)."""
    p90: list[float]
    """Every caller (Plus and Pro only before)."""


@dataclass(frozen=True, kw_only=True)
class SnowpackPlumeModel(Model):
    """One model's members in the snow-depth plume."""

    id: str
    """``aifs``, ``aigefs``, ``gefs`` or ``ifs_ens``; tolerate one this SDK does not know."""
    member_ids: list[int]
    """The model's own member numbers, in the order of ``depth``."""
    depth: list[list[float]]
    """One series per member, from ``depth.start_time`` every ``depth.interval_hours``."""
    depth_mean: list[float]
    """The equal-weight mean of this model's members' ``depth`` at each of the model's own
    steps (from ``depth.start_time`` every ``depth.interval_hours``, to the model's horizon:
    the length of its members' series), in the response's units.
    """
    members_skipped: int
    """Members not run because the ground starts bare and they bring no snow; their series is
    0 throughout.
    """


# --- GeoJSON: alert outlines and avalanche zones ---------------------------------


@dataclass(frozen=True, kw_only=True)
class AlertOutlineCollection(Response):
    """A GeoJSON ``FeatureCollection``.

    (RFC 7946) of the active winter and wind alerts' outlines, with this response's
    ``attribution`` as a foreign member.
    """

    type: str
    features: list[AlertOutlineFeature]
    """One Feature per alert, ordered by ``properties.id``."""
    attribution: ResponseAttribution


@dataclass(frozen=True, kw_only=True)
class AlertOutlineFeature(Model):
    """One alert's outline, a GeoJSON ``Feature``."""

    type: str
    geometry: AlertOutlineGeometry
    properties: AlertOutlineProperties


@dataclass(frozen=True, kw_only=True)
class AlertOutlineGeometry(Model):
    """A GeoJSON ``Polygon`` or ``MultiPolygon``."""

    type: str
    coordinates: list[list[list[Any]]]


@dataclass(frozen=True, kw_only=True)
class AlertOutlineProperties(Model):
    """The alert, under the names ``ActiveAlert`` uses for the same fields, and its ``class``."""

    id: str
    """NWS alert identifier (urn:oid:…), as ``ActiveAlert.id``."""
    event: str
    class_: AlertClass = field(metadata={JSON_NAME: "class"})
    severity: str
    """As ``ActiveAlert.severity``."""
    urgency: str
    """As ``ActiveAlert.urgency``."""
    certainty: str
    """As ``ActiveAlert.certainty``."""
    headline: str
    onset: dt.datetime | None = None
    """When the hazard begins."""
    expires: dt.datetime
    """When NWS is due to re-issue this message; not the alert's end (see
    ``ActiveAlert.expires``).
    """
    ends: dt.datetime | None = None
    """When the hazard ends."""
    sender_name: str | None = None
    """The NWS office."""
    source_url: str
    """The NWS forecast page of a point inside the outline, which lists the alert and links
    to its text: where "view on NWS" goes.
    """


@dataclass(frozen=True, kw_only=True)
class AvalancheZoneCollection(Response):
    """A GeoJSON ``FeatureCollection``.

    (RFC 7946) of the avalanche centers' forecast zones, each with its published rating, and
    this response's ``attribution`` as a foreign member.
    """

    type: str
    features: list[AvalancheZoneFeature]
    """One Feature per zone, the less specific first: where zones overlap, the one drawn last
    is the one a point there is served.
    """
    attribution: ResponseAttribution


@dataclass(frozen=True, kw_only=True)
class AvalancheZoneFeature(Model):
    """One forecast zone, a GeoJSON ``Feature``."""

    type: str
    id: int
    """The zone's id, as ``properties.zone_id``."""
    geometry: AvalancheZoneGeometry
    properties: AvalancheForecast


@dataclass(frozen=True, kw_only=True)
class AvalancheZoneGeometry(Model):
    """A GeoJSON ``MultiPolygon``.

    An array of polygons, each an array of rings (the outer one first, then any holes), each
    ring closed.
    """

    type: str
    coordinates: list[list[list[Any]]]


@dataclass(frozen=True, kw_only=True)
class MeasuredPrecipitation(Model):
    """Present only on a day part of which is a measurement.

    The leading date, when the radar (MRMS radar-only) measured hours between its local
    midnight and the reference init -- and absent otherwise.
    """

    amount: float
    through: dt.datetime
