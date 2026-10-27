"""The I/O-free core shared by :class:`Client` and :class:`AsyncClient`.

It builds canonical requests, decides about credentials, redirects, retries
and caching, and turns responses into models or errors. The two clients only
move bytes.
"""

from __future__ import annotations

import dataclasses
import email.utils
import hashlib
import json
import logging
import math
import os
import platform
import random
import re
import ssl
import threading
import time
import warnings
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar

import httpx

from ._decode import DecodeError, decode_model
from ._query import Query, encode_component
from ._version import __version__
from .cache import Cache, CacheEntry, MemoryCache
from .enums import LocationType, UnitSystem
from .errors import (
    APIConnectionError,
    APIError,
    OureaDeprecationWarning,
    OureaError,
    ResponseTooLargeError,
    UnexpectedResponseError,
    UsageError,
    error_class,
)
from .models import (
    AlertsResponse,
    AttributionRegistry,
    CurrentResponse,
    ForecastResponse,
    LocationsResponse,
    NearbyLocationsResponse,
    NearbyPointResponse,
    PublicCatalogLocationDetail,
    PublicCatalogLocationPage,
    PublicCatalogStationDetail,
    PublicCatalogStationPage,
    RateLimit,
    Response,
    ResponseMeta,
    RunsResponse,
    SearchLocationsResponse,
    StormReportCard,
    StormReportsResponse,
)
from .probabilities import Chance, Total, prob_query, result_key, totals_query

if TYPE_CHECKING:
    import datetime as dt

logger = logging.getLogger("ensemble_weather")

DEFAULT_BASE_URL = "https://api.oureawx.com"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2
MAX_REDIRECTS = 5
MAX_RETRY_AFTER = 60.0
MAX_BODY_BYTES = 64 * 1024 * 1024
"""A response body over this size is an error, not an out-of-memory."""

API_KEY_ENV = "OUREA_API_KEY"
BASE_URL_ENV = "OUREA_BASE_URL"

_REDIRECTS = frozenset({301, 302, 307, 308})
_RETRY_STATUSES = frozenset({429, 502, 503, 504})
_RETRY_AFTER_STATUSES = frozenset({429, 503})

R = TypeVar("R", bound=Response)


class HasStateSlug(Protocol):
    """Anything naming a location: a ``LocationRef``, ``SearchHit``, ``LocationSummary``."""

    @property
    def state(self) -> str:
        """The state code."""
        ...

    @property
    def slug(self) -> str:
        """The location slug."""
        ...


LocationArg = str | HasStateSlug
UnitsArg = UnitSystem | str
StrList = Sequence[str] | str


def user_agent(product: str | None = None) -> str:
    """The SDK's User-Agent, optionally followed by the app's own product token."""
    runtime = f"{platform.python_implementation()}/{platform.python_version()}"
    base = f"ensemble-weather-python/{__version__} ({runtime})"
    return f"{base} {product}" if product else base


# --- warnings ------------------------------------------------------------------


_warned_lock = threading.Lock()
_warned: set[str] = set()


def _reset_deprecation_warnings() -> None:
    """Forget which operations already warned (for tests)."""
    with _warned_lock:
        _warned.clear()


_LINK_DEPRECATION = re.compile(r'<([^>]*)>\s*;[^,]*rel="?deprecation"?', re.IGNORECASE)


def _warn_deprecation(operation: str, headers: httpx.Headers) -> None:
    deprecation = headers.get("deprecation")
    sunset = headers.get("sunset")
    if deprecation is None and sunset is None:
        return
    with _warned_lock:
        if operation in _warned:
            return
        _warned.add(operation)
    parts = [f"The Ourea API has deprecated {operation}"]
    if deprecation:
        parts.append(f"Deprecation: {deprecation}")
    if sunset:
        parts.append(f"Sunset: {sunset}")
    match = _LINK_DEPRECATION.search(headers.get("link", ""))
    if match:
        parts.append(f"see {match.group(1)}")
    warnings.warn("; ".join(parts) + ".", OureaDeprecationWarning, stacklevel=4)


# --- calls ------------------------------------------------------------------------


@dataclass(frozen=True)
class Call(Generic[R]):
    """One API operation, ready to send."""

    operation: str
    path: str
    query: str
    model: type[R]
    open_route: bool = False
    finish: Callable[[R], R] | None = None


@dataclass(frozen=True)
class Prepared:
    """A call resolved against the client's configuration."""

    url: str
    headers: dict[str, str]
    cache_key: str | None
    cached: CacheEntry | None


@dataclass(frozen=True)
class Retry:
    """The decision to try again after ``delay`` seconds."""

    delay: float


@dataclass(frozen=True)
class RawResponse:
    """The final (post-redirect) response of one attempt."""

    status: int
    headers: httpx.Headers
    body: bytes


def _cache_control(headers: httpx.Headers) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for part in headers.get("cache-control", "").split(","):
        name, _, value = part.strip().partition("=")
        if name:
            out[name.lower()] = value.strip('"') if value else None
    return out


def parse_retry_after(value: str | None, now: float) -> float | None:
    """Seconds to wait from a ``Retry-After`` header (delta-seconds or HTTP-date)."""
    if value is None:
        return None
    text = value.strip()
    if text.isdigit():
        return float(text)
    try:
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - now)


def _is_tls_verification_failure(exc: BaseException) -> bool:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        if "CERTIFICATE_VERIFY_FAILED" in str(current):
            return True
        current = current.__cause__ or current.__context__
    return False


def read_bounded(chunks: Iterable[bytes], declared: str | None) -> bytes:
    """Read a body, refusing one over :data:`MAX_BODY_BYTES`."""
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise ResponseTooLargeError(MAX_BODY_BYTES)
    buffer = bytearray()
    for chunk in chunks:
        buffer += chunk
        if len(buffer) > MAX_BODY_BYTES:
            raise ResponseTooLargeError(MAX_BODY_BYTES)
    return bytes(buffer)


class BodyBuffer:
    """Accumulates an async body under the same bound as :func:`read_bounded`."""

    def __init__(self, declared: str | None) -> None:
        """Check the declared length before anything is read."""
        if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            raise ResponseTooLargeError(MAX_BODY_BYTES)
        self._buffer = bytearray()

    def add(self, chunk: bytes) -> None:
        """Append a chunk, refusing to grow past the bound."""
        self._buffer += chunk
        if len(self._buffer) > MAX_BODY_BYTES:
            raise ResponseTooLargeError(MAX_BODY_BYTES)

    def getvalue(self) -> bytes:
        """The body read so far."""
        return bytes(self._buffer)


# --- the core ---------------------------------------------------------------------


class Core:
    """Configuration plus every decision that does not need I/O."""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        units: UnitsArg,
        timeout: float,
        max_retries: int,
        cache: Cache | bool,
        send_key_on_open_routes: bool,
        app_user_agent: str | None,
    ) -> None:
        """Resolve the configuration (BEHAVIOR 2)."""
        key = api_key if api_key is not None else os.environ.get(API_KEY_ENV)
        self._api_key = key or None
        base = base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL
        self.base_url = base.rstrip("/")
        self._origin = httpx.URL(self.base_url)
        self.units = _units(units)
        if timeout <= 0 or not math.isfinite(timeout):
            raise UsageError("timeout must be a positive number of seconds")
        self.timeout = timeout
        if isinstance(max_retries, bool) or max_retries < 0:
            raise UsageError("max_retries must be 0 or more")
        self.max_retries = max_retries
        if cache is True:
            self.cache: Cache | None = MemoryCache()
        elif cache is False:
            self.cache = None
        else:
            self.cache = cache
        self.send_key_on_open_routes = send_key_on_open_routes
        self.user_agent = user_agent(app_user_agent)
        self.rate_limit: RateLimit | None = None
        self.clock: Callable[[], float] = time.time
        self.random: Callable[[], float] = random.random

    @property
    def has_api_key(self) -> bool:
        """Whether a key is configured (the key itself is never exposed)."""
        return self._api_key is not None

    def describe(self) -> str:
        """A repr-safe summary of the configuration (never the key)."""
        key = "set" if self._api_key else "none"
        return f"base_url={self.base_url!r}, api_key={key}, units={self.units.value!r}"

    # -- request side ------------------------------------------------------------

    def prepare(self, call: Call[Any]) -> Prepared:
        """Resolve URL, headers, credential and cache entry for ``call``."""
        url = self.base_url + call.path + (f"?{call.query}" if call.query else "")
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        send_key = self._api_key is not None and (
            not call.open_route or self.send_key_on_open_routes
        )
        if send_key and self._api_key is not None:
            headers["X-API-Key"] = self._api_key
        cache_key = None
        cached = None
        if self.cache is not None:
            identity = (
                hashlib.sha256(self._api_key.encode()).hexdigest()[:32]
                if send_key and self._api_key is not None
                else "anonymous"
            )
            cache_key = f"{url} {identity}"
            cached = self.cache.get(cache_key)
            if cached is not None and cached.etag:
                headers["If-None-Match"] = cached.etag
        logger.debug("GET %s", url)
        return Prepared(url=url, headers=headers, cache_key=cache_key, cached=cached)

    def fresh_from_cache(self, call: Call[R], prepared: Prepared) -> R | None:
        """The cached result if ``max-age`` still allows serving it unrevalidated."""
        entry = prepared.cached
        if entry is None or not entry.is_fresh(self.clock()):
            return None
        headers = httpx.Headers(list(entry.headers))
        return self._result(call, prepared, 200, headers, entry.body, from_cache=True)

    def redirect(
        self, prepared: Prepared, current: str, response_headers: httpx.Headers, status: int
    ) -> tuple[str, dict[str, str]]:
        """Where a redirect goes, and the headers to send there.

        The API key goes only to the configured base URL's origin.
        """
        target = httpx.URL(current).join(response_headers["location"])
        if status == 301 and current == prepared.url:
            logger.debug("301 from an SDK-built URL (not canonical?): %s -> %s", current, target)
        headers = dict(prepared.headers)
        same_origin = (target.scheme, target.host, target.port) == (
            self._origin.scheme,
            self._origin.host,
            self._origin.port,
        )
        if not same_origin:
            headers.pop("X-API-Key", None)
            headers.pop("If-None-Match", None)
        return str(target), headers

    @staticmethod
    def is_redirect(status: int, headers: httpx.Headers) -> bool:
        """Whether a response is a redirect the SDK follows."""
        return status in _REDIRECTS and "location" in headers

    # -- response side -----------------------------------------------------------

    def connection_retry(self, exc: httpx.TransportError, attempt: int) -> Retry | None:
        """Whether a connection failure is retried (TLS verification never is)."""
        retryable = isinstance(
            exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)
        )
        if not retryable or _is_tls_verification_failure(exc) or attempt > self.max_retries:
            return None
        return Retry(self._jitter(attempt))

    def connection_error(self, exc: Exception) -> APIConnectionError:
        """The error for a failure with no HTTP response."""
        return APIConnectionError(self._scrub(f"{type(exc).__name__}: {exc}"))

    def handle(
        self, call: Call[R], prepared: Prepared, response: RawResponse, attempt: int
    ) -> R | Retry:
        """Turn one attempt's response into a result, a retry, or an error."""
        status, headers, body = response.status, response.headers, response.body
        self.rate_limit = RateLimit.from_headers(headers)
        _warn_deprecation(call.operation, headers)
        if status == 304 and prepared.cached is not None:
            entry = self._revalidate(prepared, headers)
            merged = httpx.Headers(list(entry.headers))
            return self._result(call, prepared, 304, merged, entry.body, revalidated=True)
        if 200 <= status < 300:
            self._store(prepared, headers, body)
            return self._result(call, prepared, status, headers, body)
        error = self._error(status, headers, body)
        if status in _RETRY_STATUSES and attempt <= self.max_retries:
            wait = error.retry_after if status in _RETRY_AFTER_STATUSES else None
            if wait is not None:
                if wait > MAX_RETRY_AFTER:
                    raise error
                return Retry(wait)
            return Retry(self._jitter(attempt))
        raise error

    def _jitter(self, attempt: int) -> float:
        cap: float = min(8.0, 0.5 * 2 ** (attempt - 1))
        return self.random() * cap

    def _revalidate(self, prepared: Prepared, headers: httpx.Headers) -> CacheEntry:
        assert prepared.cached is not None  # noqa: S101 - checked by the caller
        old = prepared.cached
        merged = httpx.Headers(list(old.headers))
        for name, value in headers.items():
            merged[name] = value
        entry = dataclasses.replace(
            old,
            etag=headers.get("etag", old.etag),
            headers=tuple(merged.items()),
            stored_at=self.clock(),
            max_age=_max_age(headers),
        )
        if self.cache is not None and prepared.cache_key is not None:
            if "no-store" in _cache_control(headers):
                self.cache.delete(prepared.cache_key)
            else:
                self.cache.set(prepared.cache_key, entry)
        return entry

    def _store(self, prepared: Prepared, headers: httpx.Headers, body: bytes) -> None:
        if self.cache is None or prepared.cache_key is None:
            return
        etag = headers.get("etag")
        max_age = _max_age(headers)
        if "no-store" in _cache_control(headers) or (etag is None and not max_age):
            self.cache.delete(prepared.cache_key)
            return
        entry = CacheEntry(
            body=body,
            etag=etag,
            headers=tuple(headers.items()),
            stored_at=self.clock(),
            max_age=max_age,
        )
        self.cache.set(prepared.cache_key, entry)

    def _result(
        self,
        call: Call[R],
        prepared: Prepared,
        status: int,
        headers: httpx.Headers,
        body: bytes,
        *,
        revalidated: bool = False,
        from_cache: bool = False,
    ) -> R:
        try:
            data = json.loads(body)
            result = decode_model(call.model, data)
        except (ValueError, DecodeError) as exc:
            raise UnexpectedResponseError(
                f"{call.operation}: the response is not a valid {call.model.__name__} ({exc})"
            ) from exc
        meta = ResponseMeta(
            status=status,
            url=prepared.url,
            headers=headers,
            request_id=headers.get("x-request-id"),
            rate_limit=RateLimit.from_headers(headers),
            etag=headers.get("etag"),
            revalidated=revalidated,
            from_cache=from_cache or revalidated,
        )
        result = dataclasses.replace(result, meta=meta)
        return call.finish(result) if call.finish is not None else result

    def _error(self, status: int, headers: httpx.Headers, body: bytes) -> APIError:
        code: str | None = None
        message = f"HTTP {status}"
        try:
            data = json.loads(body)
        except ValueError:
            data = None
        if isinstance(data, dict) and isinstance(data.get("error"), str):
            code = data["error"]
            if isinstance(data.get("message"), str):
                message = data["message"]
        elif body:
            snippet = body[:200].decode("utf-8", "replace").strip()
            if snippet:
                message = f"HTTP {status}: {snippet}"
        cls = error_class(status, code)
        return cls(
            self._scrub(message),
            status=status,
            code=code,
            request_id=headers.get("x-request-id"),
            retry_after=parse_retry_after(headers.get("retry-after"), self.clock()),
            rate_limit=RateLimit.from_headers(headers),
        )

    def _scrub(self, text: str) -> str:
        if self._api_key:
            return text.replace(self._api_key, "[redacted]")
        return text

    # -- operations --------------------------------------------------------------

    def _units_for(self, units: UnitsArg | None) -> UnitSystem:
        return self.units if units is None else _units(units)

    def forecast_call(  # noqa: C901 - one branch per optional parameter
        self,
        path: str,
        query: Query,
        *,
        operation: str,
        units: UnitsArg | None,
        prob: Sequence[Chance] | None,
        totals: Sequence[Total] | None,
        max_hours: int | None,
        include_past: bool | None,
        models: bool | None,
        members: bool | None,
        daily: bool | None,
        max_days: int | None,
        hourly: bool | None,
        run: dt.datetime | str | None,
        sources: StrList | None,
        exclude_sources: StrList | None,
        nowcast: bool | None,
        diagnostics: StrList | None,
        feels_like: StrList | None,
        open_route: bool = False,
    ) -> Call[ForecastResponse]:
        """The shared parameters of both forecast routes."""
        system = self._units_for(units)
        query.add("units", system, UnitSystem.METRIC)
        query.add("max_hours", max_hours, 24)
        query.add("include_past", include_past, default=False)
        query.add("models", models, default=False)
        query.add("members", members, default=False)
        query.add("daily", daily, default=True)
        query.add("max_days", max_days)
        query.add("hourly", hourly, default=True)
        query.add("run", run)
        query.add_list("sources", sources)
        query.add_list("exclude_sources", exclude_sources)
        query.add("nowcast", nowcast, default=True)
        query.add_list("diagnostics", diagnostics)
        if feels_like is not None and _as_list(feels_like) != ["nws"]:
            query.add_list("feels_like", feels_like)
        chances = list(prob or [])
        wanted = list(totals or [])
        for item in chances:
            if not isinstance(item, Chance):
                raise UsageError(f"prob takes Chance terms, got {item!r}")
        for request in wanted:
            if not isinstance(request, Total):
                raise UsageError(f"totals takes Total requests, got {request!r}")
        prob_wire, chance_keys = prob_query(chances, system)
        totals_wire, total_keys = totals_query(wanted)
        query.add_raw("prob", prob_wire)
        query.add_raw("totals", totals_wire)

        def finish(result: ForecastResponse) -> ForecastResponse:
            changes: dict[str, Any] = {}
            # A response without answers leaves the list empty: nothing is invented.
            if chances and result.probabilities:
                by_key = {result_key(r, system): r for r in result.probabilities}
                ordered = []
                for chance, key in zip(chances, chance_keys, strict=True):
                    if key not in by_key:
                        raise UnexpectedResponseError(
                            f"{operation}: the response has no answer for {chance!r}"
                        )
                    ordered.append(dataclasses.replace(by_key[key], term=chance))
                changes["probabilities"] = ordered
            if wanted and result.window_totals:
                by_total = {
                    (t.variable.value, t.window_start_hours, t.window_end_hours): t
                    for t in result.window_totals
                }
                answered = []
                for total, tkey in zip(wanted, total_keys, strict=True):
                    if tkey not in by_total:
                        raise UnexpectedResponseError(
                            f"{operation}: the response has no answer for {total!r}"
                        )
                    answered.append(dataclasses.replace(by_total[tkey], term=total))
                changes["window_totals"] = answered
            return dataclasses.replace(result, **changes) if changes else result

        return Call(
            operation=operation,
            path=path,
            query=query.render(),
            model=ForecastResponse,
            open_route=open_route,
            finish=finish if chances or wanted else None,
        )

    def location_forecast(
        self,
        location: LocationArg,
        name: str | None,
        elevations: StrList | None,
        **options: Any,  # noqa: ANN401
    ) -> Call[ForecastResponse]:
        """``getLocationForecast``."""
        query = Query()
        query.add_list("elevations", elevations)
        return self.forecast_call(
            _location_path(location, name), query, operation="getLocationForecast", **options
        )

    def point_forecast(
        self,
        lat: float,
        lon: float,
        elevation_m: float | None,
        **options: Any,  # noqa: ANN401
    ) -> Call[ForecastResponse]:
        """``getPointForecast``."""
        query = _coordinates(lat, lon)
        query.add("elevation_m", elevation_m)
        return self.forecast_call(
            "/api/v1/forecast", query, operation="getPointForecast", **options
        )

    def current(
        self,
        path: str,
        query: Query,
        *,
        operation: str,
        units: UnitsArg | None,
        sources: StrList | None,
        exclude_sources: StrList | None,
        include_nowcast_hours: bool,
    ) -> Call[CurrentResponse]:
        """``getCurrentConditions`` / ``getCurrentByCoordinates``."""
        query.add("units", self._units_for(units), UnitSystem.METRIC)
        query.add_list("sources", sources)
        query.add_list("exclude_sources", exclude_sources)
        if include_nowcast_hours:
            query.add("include", "nowcast_hours")
        return Call(operation, path, query.render(), CurrentResponse)

    def alerts(self, path: str, query: Query, operation: str) -> Call[AlertsResponse]:
        """``getLocationAlerts`` / ``getAlertsByCoordinates``."""
        return Call(operation, path, query.render(), AlertsResponse)

    def nearby_location(
        self,
        location: LocationArg,
        name: str | None,
        *,
        limit: int | None,
        radius_km: float | None,
        units: UnitsArg | None,
    ) -> Call[NearbyLocationsResponse]:
        """``getNearbyLocations``."""
        query = Query()
        query.add("limit", limit, 3)
        query.add("radius_km", radius_km, 50)
        query.add("units", self._units_for(units), UnitSystem.METRIC)
        path = _location_path(location, name) + "/nearby"
        return Call("getNearbyLocations", path, query.render(), NearbyLocationsResponse)

    def nearby_point(
        self,
        lat: float,
        lon: float,
        *,
        limit: int | None,
        radius_km: float | None,
        units: UnitsArg | None,
    ) -> Call[NearbyPointResponse]:
        """``getNearbyByCoordinates``."""
        query = _coordinates(lat, lon)
        query.add("limit", limit, 3)
        query.add("radius_km", radius_km, 50)
        query.add("units", self._units_for(units), UnitSystem.METRIC)
        return Call("getNearbyByCoordinates", "/api/v1/nearby", query.render(), NearbyPointResponse)

    def search(
        self,
        q: str,
        *,
        state: str | None,
        county: str | None,
        location_type: LocationType | str | None,
        limit: int | None,
    ) -> Call[SearchLocationsResponse]:
        """``searchLocations`` (an open route: sent without the key)."""
        if len(q.strip()) < 2:
            raise UsageError("a search needs at least 2 characters")
        query = Query()
        query.add("q", q)
        query.add("state", None if state is None else _state(state))
        query.add("county", county)
        query.add("type", location_type)
        query.add("limit", limit, 20)
        return Call(
            "searchLocations",
            "/api/v1/search/locations",
            query.render(),
            SearchLocationsResponse,
            open_route=True,
        )

    def locations(
        self,
        state: str | None,
        *,
        location_type: LocationType | str | None,
        units: UnitsArg | None,
        limit: int | None,
        cursor: str | None,
    ) -> Call[LocationsResponse]:
        """``getAllLocations`` / ``getLocations``."""
        query = Query()
        query.add("type", location_type)
        query.add("units", self._units_for(units), UnitSystem.METRIC)
        query.add("limit", limit)
        query.add("cursor", cursor)
        if state is None:
            return Call("getAllLocations", "/api/v1/locations", query.render(), LocationsResponse)
        path = "/api/v1/locations/" + encode_component(_state(state))
        return Call("getLocations", path, query.render(), LocationsResponse)

    def catalog_locations(
        self,
        *,
        admin1: str | None,
        country: str | None,
        location_type: str | None,
        template: str | None,
        limit: int | None,
        cursor: str | None,
    ) -> Call[PublicCatalogLocationPage]:
        """``listCatalogLocations`` (keeps the key: keyed callers get their own budget)."""
        query = Query()
        query.add("admin1", admin1)
        query.add("country", country)
        query.add("type", location_type)
        query.add("template", template)
        query.add("limit", limit, 20)
        query.add("cursor", cursor)
        return Call(
            "listCatalogLocations",
            "/api/v1/catalog/locations",
            query.render(),
            PublicCatalogLocationPage,
        )

    def catalog_location(
        self, slug: str, *, include: StrList | None, locale: str | None
    ) -> Call[PublicCatalogLocationDetail]:
        """``getCatalogLocation`` (an open route)."""
        query = Query()
        query.add_list("include", include)
        query.add("locale", locale, "en")
        return Call(
            "getCatalogLocation",
            "/api/v1/catalog/locations/" + encode_component(_nonempty("slug", slug)),
            query.render(),
            PublicCatalogLocationDetail,
            open_route=True,
        )

    def catalog_stations(
        self,
        *,
        admin1: str | None,
        country: str | None,
        network: StrList | None,
        capabilities: StrList | None,
        status: str | None,
        limit: int | None,
        cursor: str | None,
    ) -> Call[PublicCatalogStationPage]:
        """``listCatalogStations`` (keeps the key)."""
        query = Query()
        query.add("admin1", admin1)
        query.add("country", country)
        query.add_list("network", network)
        query.add_repeated("capability", capabilities)
        query.add("status", status)
        query.add("limit", limit, 20)
        query.add("cursor", cursor)
        return Call(
            "listCatalogStations",
            "/api/v1/catalog/stations",
            query.render(),
            PublicCatalogStationPage,
        )

    def catalog_station(
        self, slug: str, *, include: StrList | None, locale: str | None
    ) -> Call[PublicCatalogStationDetail]:
        """``getCatalogStation`` (an open route)."""
        query = Query()
        query.add_list("include", include)
        query.add("locale", locale, "en")
        return Call(
            "getCatalogStation",
            "/api/v1/catalog/stations/" + encode_component(_nonempty("slug", slug)),
            query.render(),
            PublicCatalogStationDetail,
            open_route=True,
        )

    def runs(self, *, limit: int | None) -> Call[RunsResponse]:
        """``getAvailableRuns``."""
        query = Query()
        query.add("limit", limit, 10)
        return Call("getAvailableRuns", "/api/v1/runs", query.render(), RunsResponse)

    def storm_reports(self, *, limit: int | None) -> Call[StormReportsResponse]:
        """``getStormReports``."""
        query = Query()
        query.add("limit", limit, 20)
        return Call(
            "getStormReports", "/api/v1/storm-reports", query.render(), StormReportsResponse
        )

    def storm_report(self, report_id: int) -> Call[StormReportCard]:
        """``getStormReport``."""
        if isinstance(report_id, bool) or not isinstance(report_id, int):
            raise UsageError(f"a storm report id is an integer, got {report_id!r}")
        return Call("getStormReport", f"/api/v1/storm-reports/{report_id}", "", StormReportCard)

    def attribution(self) -> Call[AttributionRegistry]:
        """``getAttribution`` (an open route)."""
        return Call(
            "getAttribution", "/api/v1/attribution", "", AttributionRegistry, open_route=True
        )


# --- argument helpers -------------------------------------------------------------


def _units(value: UnitsArg) -> UnitSystem:
    try:
        member = UnitSystem(value)
    except ValueError:
        member = None
    if member is None or member.is_unknown:
        raise UsageError(f"units must be metric, imperial or kelvin, not {value!r}")
    return member


def _as_list(values: StrList) -> list[str]:
    return [values] if isinstance(values, str) else list(values)


def _nonempty(what: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise UsageError(f"{what} must be a non-empty string, got {value!r}")
    return value


def _state(state: str) -> str:
    """Lowercase a two-letter USPS code; pass anything else through."""
    _nonempty("state", state)
    return state.lower() if len(state) == 2 and state.isalpha() else state


def _location_path(location: LocationArg, name: str | None) -> str:
    if name is not None:
        if not isinstance(location, str):
            raise UsageError("with a separate name, the first argument is the state")
        state, slug = location, name
    elif isinstance(location, str):
        if location.count("/") != 1:
            raise UsageError(
                f"a location is 'state/slug' (for example 'or/mt-hood-meadows'), got {location!r}"
            )
        state, slug = location.split("/")
    else:
        state, slug = location.state, location.slug
    return (
        "/api/v1/locations/"
        + encode_component(_state(state))
        + "/"
        + encode_component(_nonempty("slug", slug))
    )


def _coordinates(lat: float, lon: float) -> Query:
    for name, value, bound in (("lat", lat, 90), ("lon", lon, 180)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise UsageError(f"{name} must be a number, got {value!r}")
        if not -bound <= value <= bound:
            raise UsageError(f"{name} must be within +/-{bound}, got {value!r}")
    query = Query()
    query.add("lat", lat)
    query.add("lon", lon)
    return query


def _max_age(headers: httpx.Headers) -> float | None:
    directives = _cache_control(headers)
    if "no-cache" in directives:
        return 0.0
    raw = directives.get("max-age")
    if raw is None or not raw.isdigit():
        return None
    return float(raw)


__all__ = [
    "MAX_BODY_BYTES",
    "BodyBuffer",
    "Call",
    "Core",
    "LocationArg",
    "OureaDeprecationWarning",
    "OureaError",
    "Prepared",
    "RawResponse",
    "Retry",
    "StrList",
    "UnitsArg",
    "read_bounded",
]
