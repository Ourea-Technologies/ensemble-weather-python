"""The synchronous client."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, TypeVar

import httpx

from ._core import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    MAX_REDIRECTS,
    Call,
    Core,
    LocationArg,
    RawResponse,
    Retry,
    StrList,
    UnitsArg,
    _coordinates,
    _location_path,
    read_bounded,
)
from ._query import Query

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Callable, Iterator, Sequence
    from types import TracebackType

    from ._core import Prepared
    from .cache import Cache
    from .enums import LocationType, StationStatus, TemplateVariant
    from .models import (
        AlertsResponse,
        AttributionRegistry,
        CurrentResponse,
        ForecastResponse,
        LocationsResponse,
        LocationSummary,
        NearbyLocationsResponse,
        NearbyPointResponse,
        PublicCatalogLocation,
        PublicCatalogLocationDetail,
        PublicCatalogLocationPage,
        PublicCatalogStation,
        PublicCatalogStationDetail,
        PublicCatalogStationPage,
        RateLimit,
        Response,
        RunsResponse,
        SearchLocationsResponse,
    )
    from .probabilities import Chance, Total

__all__ = ["Client"]

R = TypeVar("R", bound="Response")


class Client:
    """A synchronous client for the Ourea probabilistic weather API.

    Use it as a context manager so its connections are closed::

        with Client() as client:
            forecast = client.forecast("or/mt-hood-meadows")

    Args:
        api_key: Your API key. Defaults to the ``OUREA_API_KEY`` environment
            variable; with neither, calls are anonymous (Free tier), which is
            valid. The key is sent only as ``X-API-Key``, only to the base
            URL's host, and never to the open routes (search, catalog detail,
            attribution) unless ``send_key_on_open_routes`` is set, so those
            share the edge cache with everyone.
        base_url: The API's base URL. Defaults to ``OUREA_BASE_URL``, else
            ``https://api.oureawx.com``.
        units: The default unit system for every request that accepts one.
        timeout: Seconds per attempt.
        max_retries: Retries after the first attempt (0 disables retrying).
            Connection errors, 429, 502, 503 and 504 are retried.
        cache: ``True`` (default) for an in-memory ETag cache, ``False`` to
            disable caching, or your own :class:`~ensemble_weather.Cache`.
        send_key_on_open_routes: Send the key on the open routes too, so
            every request is attributed to it (and none is edge-cached).
        user_agent: Your app's product token, appended to the SDK's own.
        transport: An ``httpx`` transport, for tests and proxies. TLS
            verification is always on with the default transport, and the SDK
            has no option to turn it off.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        units: UnitsArg = "metric",
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        cache: Cache | bool = True,
        send_key_on_open_routes: bool = False,
        user_agent: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Create a client; see the class docstring for the arguments."""
        self._core = Core(
            api_key=api_key,
            base_url=base_url,
            units=units,
            timeout=timeout,
            max_retries=max_retries,
            cache=cache,
            send_key_on_open_routes=send_key_on_open_routes,
            app_user_agent=user_agent,
        )
        self._http = httpx.Client(transport=transport, timeout=timeout, follow_redirects=False)
        self._sleep: Callable[[float], None] = time.sleep

    # -- lifecycle -----------------------------------------------------------------

    def __enter__(self) -> Client:  # noqa: PYI034 - Self needs Python 3.11
        """Enter the context: the client itself."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the client's connections."""
        self.close()

    def close(self) -> None:
        """Close the client's connections."""
        self._http.close()

    def __repr__(self) -> str:
        """Describe the client without revealing the key."""
        return f"Client({self._core.describe()})"

    @property
    def rate_limit(self) -> RateLimit | None:
        """The rate-limit state of the last response, if it reported one."""
        return self._core.rate_limit

    @property
    def cache(self) -> Cache | None:
        """The ETag cache in use, or ``None`` when caching is disabled."""
        return self._core.cache

    # -- transport -------------------------------------------------------------------

    def _run(self, call: Call[R]) -> R:
        prepared = self._core.prepare(call)
        fresh = self._core.fresh_from_cache(call, prepared)
        if fresh is not None:
            return fresh
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._send(prepared)
            except httpx.TransportError as exc:
                retry = self._core.connection_retry(exc, attempt)
                if retry is None:
                    raise self._core.connection_error(exc) from exc
                self._sleep(retry.delay)
                continue
            outcome = self._core.handle(call, prepared, response, attempt)
            if isinstance(outcome, Retry):
                self._sleep(outcome.delay)
                continue
            return outcome

    def _send(self, prepared: Prepared) -> RawResponse:
        url, headers = prepared.url, prepared.headers
        for hop in range(MAX_REDIRECTS + 1):
            request = self._http.build_request("GET", url, headers=headers)
            response = self._http.send(request, stream=True)
            try:
                if self._core.is_redirect(response.status_code, response.headers) and (
                    hop < MAX_REDIRECTS
                ):
                    url, headers = self._core.redirect(
                        prepared, url, response.headers, response.status_code
                    )
                    continue
                body = read_bounded(response.iter_bytes(), response.headers.get("content-length"))
                return RawResponse(response.status_code, response.headers, body)
            finally:
                response.close()
        raise AssertionError("unreachable")  # pragma: no cover

    # -- forecasts -------------------------------------------------------------------

    def forecast(
        self,
        location: LocationArg,
        slug: str | None = None,
        *,
        prob: Sequence[Chance] | None = None,
        totals: Sequence[Total] | None = None,
        units: UnitsArg | None = None,
        max_hours: int | None = None,
        include_past: bool | None = None,
        models: bool | None = None,
        members: bool | None = None,
        elevations: StrList | None = None,
        daily: bool | None = None,
        max_days: int | None = None,
        hourly: bool | None = None,
        run: dt.datetime | str | None = None,
        sources: StrList | None = None,
        exclude_sources: StrList | None = None,
        nowcast: bool | None = None,
        diagnostics: StrList | None = None,
        include: StrList | None = None,
        feels_like: StrList | None = None,
    ) -> ForecastResponse:
        """The forecast for a named location (``getLocationForecast``). Anonymous OK.

        Args:
            location: ``"or/mt-hood-meadows"``, a state code with ``slug``, or
                any object with ``state`` and ``slug`` (a search hit, a
                ``LocationRef``).
            slug: The location slug, when ``location`` is just the state.
            prob: Probability terms (:class:`~ensemble_weather.Chance`),
                answered in :attr:`ForecastResponse.probabilities` in this order.
            totals: Window totals (:class:`~ensemble_weather.Total`), answered
                in :attr:`ForecastResponse.window_totals` in this order.
            units: This request's unit system (default: the client's).
            max_hours: Hours of hourly series (6-360, default 24).
            include_past: Start the hourly series at the run's init.
            models: Per-model breakdowns (Pro).
            members: Individual member values (Free: the plume view).
            elevations: ``"all"`` or names of the location's extra elevations.
            daily: Include the daily summaries (default true).
            max_days: The number of daily rows (default: the tier's horizon).
            hourly: Include the hourly series (default true).
            run: A specific model init, for historical queries (Pro).
            sources: Observation sources the nowcast may use.
            exclude_sources: Observation sources the nowcast must not use.
            nowcast: Blend in the latest observations (default true).
            diagnostics: Opt-in diagnostics: ``provenance``.
            include: Opt-in variables: ``skin_temperature``, ``mslp``.
            feels_like: The feels-like index (``nws``, the default and only one).

        Raises:
            NotFoundError: The location does not exist.
            UsageError: An argument is invalid; nothing was sent.
        """
        call = self._core.location_forecast(
            location,
            slug,
            elevations,
            units=units,
            prob=prob,
            totals=totals,
            max_hours=max_hours,
            include_past=include_past,
            models=models,
            members=members,
            daily=daily,
            max_days=max_days,
            hourly=hourly,
            run=run,
            sources=sources,
            exclude_sources=exclude_sources,
            nowcast=nowcast,
            diagnostics=diagnostics,
            include=include,
            feels_like=feels_like,
        )
        return self._run(call)

    def get_point_forecast(
        self,
        lat: float,
        lon: float,
        *,
        elevation_m: float | None = None,
        prob: Sequence[Chance] | None = None,
        totals: Sequence[Total] | None = None,
        units: UnitsArg | None = None,
        max_hours: int | None = None,
        include_past: bool | None = None,
        models: bool | None = None,
        members: bool | None = None,
        daily: bool | None = None,
        max_days: int | None = None,
        hourly: bool | None = None,
        run: dt.datetime | str | None = None,
        sources: StrList | None = None,
        exclude_sources: StrList | None = None,
        nowcast: bool | None = None,
        diagnostics: StrList | None = None,
        include: StrList | None = None,
        feels_like: StrList | None = None,
    ) -> ForecastResponse:
        """The forecast at coordinates (``getPointForecast``). Needs a Pro key.

        ``elevation_m`` forecasts at that elevation instead of the terrain's.
        Coordinates are sent exactly as given. The other arguments are as for
        :meth:`forecast`.

        Raises:
            PermissionDeniedError: The key is not Pro (``PRO_REQUIRED``).
            OutsideCoverageError: The point is outside the forecast domain.
        """
        call = self._core.point_forecast(
            lat,
            lon,
            elevation_m,
            units=units,
            prob=prob,
            totals=totals,
            max_hours=max_hours,
            include_past=include_past,
            models=models,
            members=members,
            daily=daily,
            max_days=max_days,
            hourly=hourly,
            run=run,
            sources=sources,
            exclude_sources=exclude_sources,
            nowcast=nowcast,
            diagnostics=diagnostics,
            include=include,
            feels_like=feels_like,
        )
        return self._run(call)

    # -- current conditions and alerts ------------------------------------------------

    def current(
        self,
        location: LocationArg,
        slug: str | None = None,
        *,
        units: UnitsArg | None = None,
        sources: StrList | None = None,
        exclude_sources: StrList | None = None,
        include_nowcast_hours: bool = False,
    ) -> CurrentResponse:
        """Current conditions at a named location (``getCurrentConditions``)."""
        path = _location_path(location, slug) + "/current"
        return self._run(
            self._core.current(
                path,
                Query(),
                operation="getCurrentConditions",
                units=units,
                sources=sources,
                exclude_sources=exclude_sources,
                include_nowcast_hours=include_nowcast_hours,
            )
        )

    def current_at(
        self,
        lat: float,
        lon: float,
        *,
        elevation_m: float | None = None,
        units: UnitsArg | None = None,
        sources: StrList | None = None,
        exclude_sources: StrList | None = None,
        include_nowcast_hours: bool = False,
    ) -> CurrentResponse:
        """Current conditions at coordinates (``getCurrentByCoordinates``). Pro."""
        query = _coordinates(lat, lon)
        query.add("elevation_m", elevation_m)
        return self._run(
            self._core.current(
                "/api/v1/current",
                query,
                operation="getCurrentByCoordinates",
                units=units,
                sources=sources,
                exclude_sources=exclude_sources,
                include_nowcast_hours=include_nowcast_hours,
            )
        )

    def alerts(self, location: LocationArg, slug: str | None = None) -> AlertsResponse:
        """Active alerts at a named location (``getLocationAlerts``)."""
        path = _location_path(location, slug) + "/alerts"
        return self._run(self._core.alerts(path, Query(), "getLocationAlerts"))

    def alerts_at(self, lat: float, lon: float) -> AlertsResponse:
        """Active alerts at coordinates (``getAlertsByCoordinates``). Pro."""
        query = _coordinates(lat, lon)
        return self._run(self._core.alerts("/api/v1/alerts", query, "getAlertsByCoordinates"))

    # -- places ----------------------------------------------------------------------

    def nearby(
        self,
        location: LocationArg,
        slug: str | None = None,
        *,
        limit: int | None = None,
        radius_km: float | None = None,
        units: UnitsArg | None = None,
    ) -> NearbyLocationsResponse:
        """Locations near a named location (``getNearbyLocations``)."""
        return self._run(
            self._core.nearby_location(
                location, slug, limit=limit, radius_km=radius_km, units=units
            )
        )

    def nearby_at(
        self,
        lat: float,
        lon: float,
        *,
        limit: int | None = None,
        radius_km: float | None = None,
        units: UnitsArg | None = None,
    ) -> NearbyPointResponse:
        """Locations near coordinates (``getNearbyByCoordinates``)."""
        return self._run(
            self._core.nearby_point(lat, lon, limit=limit, radius_km=radius_km, units=units)
        )

    def search(
        self,
        q: str,
        *,
        state: str | None = None,
        county: str | None = None,
        location_type: LocationType | str | None = None,
        limit: int | None = None,
    ) -> SearchLocationsResponse:
        """Search locations by name (``searchLocations``). Sent without the key."""
        return self._run(
            self._core.search(
                q, state=state, county=county, location_type=location_type, limit=limit
            )
        )

    def list_locations(
        self,
        state: str | None = None,
        *,
        location_type: LocationType | str | None = None,
        units: UnitsArg | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> LocationsResponse:
        """One page of locations, in one state or all (``getLocations`` / ``getAllLocations``).

        Pass the page's ``next_cursor`` back as ``cursor`` for the next page,
        or use :meth:`iter_locations`.
        """
        return self._run(
            self._core.locations(
                state, location_type=location_type, units=units, limit=limit, cursor=cursor
            )
        )

    def iter_locations(
        self,
        state: str | None = None,
        *,
        location_type: LocationType | str | None = None,
        units: UnitsArg | None = None,
        limit: int | None = None,
    ) -> Iterator[LocationSummary]:
        """Every location, fetching pages lazily as the iterator advances."""
        cursor: str | None = None
        while True:
            page = self.list_locations(
                state, location_type=location_type, units=units, limit=limit, cursor=cursor
            )
            yield from page.locations
            if not page.next_cursor:
                return
            cursor = page.next_cursor

    # -- catalog ---------------------------------------------------------------------

    def list_catalog_locations(
        self,
        *,
        admin1: str | None = None,
        country: str | None = None,
        location_type: LocationType | str | None = None,
        template: TemplateVariant | str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PublicCatalogLocationPage:
        """One page of the location catalog (``listCatalogLocations``)."""
        return self._run(
            self._core.catalog_locations(
                admin1=admin1,
                country=country,
                location_type=location_type,
                template=template,
                limit=limit,
                cursor=cursor,
            )
        )

    def iter_catalog_locations(
        self,
        *,
        admin1: str | None = None,
        country: str | None = None,
        location_type: LocationType | str | None = None,
        template: TemplateVariant | str | None = None,
        limit: int | None = None,
    ) -> Iterator[PublicCatalogLocation]:
        """Every catalog location, following ``next_cursor`` lazily."""
        cursor: str | None = None
        while True:
            page = self.list_catalog_locations(
                admin1=admin1,
                country=country,
                location_type=location_type,
                template=template,
                limit=limit,
                cursor=cursor,
            )
            yield from page.items
            if not page.next_cursor:
                return
            cursor = page.next_cursor

    def catalog_location(
        self, slug: str, *, include: StrList | None = None, locale: str | None = None
    ) -> PublicCatalogLocationDetail:
        """One catalog location (``getCatalogLocation``). Sent without the key."""
        return self._run(self._core.catalog_location(slug, include=include, locale=locale))

    def list_catalog_stations(
        self,
        *,
        admin1: str | None = None,
        country: str | None = None,
        network: StrList | None = None,
        capabilities: StrList | None = None,
        status: StationStatus | str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PublicCatalogStationPage:
        """One page of the station catalog (``listCatalogStations``).

        ``capabilities`` are all required (sent as one ``capability`` list).
        ``network`` and ``status`` take the snake_case names
        (:class:`~ensemble_weather.enums.StationNetwork`,
        :class:`~ensemble_weather.enums.StationStatus`).
        """
        return self._run(
            self._core.catalog_stations(
                admin1=admin1,
                country=country,
                network=network,
                capabilities=capabilities,
                status=status,
                limit=limit,
                cursor=cursor,
            )
        )

    def iter_catalog_stations(
        self,
        *,
        admin1: str | None = None,
        country: str | None = None,
        network: StrList | None = None,
        capabilities: StrList | None = None,
        status: StationStatus | str | None = None,
        limit: int | None = None,
    ) -> Iterator[PublicCatalogStation]:
        """Every catalog station, following ``next_cursor`` lazily."""
        cursor: str | None = None
        while True:
            page = self.list_catalog_stations(
                admin1=admin1,
                country=country,
                network=network,
                capabilities=capabilities,
                status=status,
                limit=limit,
                cursor=cursor,
            )
            yield from page.items
            if not page.next_cursor:
                return
            cursor = page.next_cursor

    def catalog_station(
        self, slug: str, *, include: StrList | None = None, locale: str | None = None
    ) -> PublicCatalogStationDetail:
        """One catalog station (``getCatalogStation``). Sent without the key."""
        return self._run(self._core.catalog_station(slug, include=include, locale=locale))

    # -- runs and attribution ---------------------------------------------------------

    def runs(self, *, limit: int | None = None, cursor: str | None = None) -> RunsResponse:
        """The served model run and recent runs (``getAvailableRuns``).

        Pass the page's ``next_cursor`` back as ``cursor`` for the next page.
        """
        return self._run(self._core.runs(limit=limit, cursor=cursor))

    def attribution(self) -> AttributionRegistry:
        """Every data provider and its licence (``getAttribution``). Sent without the key."""
        return self._run(self._core.attribution())
