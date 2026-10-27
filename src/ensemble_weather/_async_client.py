"""The asynchronous client."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, TypeVar

import httpx

from ._core import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    MAX_REDIRECTS,
    BodyBuffer,
    Call,
    Core,
    LocationArg,
    RawResponse,
    Retry,
    StrList,
    UnitsArg,
    _coordinates,
    _location_path,
)
from ._query import Query

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
    from types import TracebackType

    from ._core import Prepared
    from .cache import Cache
    from .enums import LocationType
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
        StormReportCard,
        StormReportsResponse,
    )
    from .probabilities import Chance, Total

__all__ = ["AsyncClient"]

R = TypeVar("R", bound="Response")


class AsyncClient:
    """An asynchronous (asyncio) client for the Ourea probabilistic weather API.

    It has the same methods as :class:`~ensemble_weather.Client`, as
    coroutines. Use it as an async context manager::

        async with AsyncClient() as client:
            forecast = await client.forecast("or/mt-hood-meadows")

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
        transport: httpx.AsyncBaseTransport | None = None,
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
        self._http = httpx.AsyncClient(transport=transport, timeout=timeout, follow_redirects=False)
        self._sleep: Callable[[float], Awaitable[None]] = asyncio.sleep

    # -- lifecycle -----------------------------------------------------------------

    async def __aenter__(self) -> AsyncClient:  # noqa: PYI034 - Self needs Python 3.11
        """Enter the context: the client itself."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the client's connections."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the client's connections."""
        await self._http.aclose()

    def __repr__(self) -> str:
        """Describe the client without revealing the key."""
        return f"AsyncClient({self._core.describe()})"

    @property
    def rate_limit(self) -> RateLimit | None:
        """The rate-limit state of the last response, if it reported one."""
        return self._core.rate_limit

    @property
    def cache(self) -> Cache | None:
        """The ETag cache in use, or ``None`` when caching is disabled."""
        return self._core.cache

    # -- transport -------------------------------------------------------------------

    async def _run(self, call: Call[R]) -> R:
        prepared = self._core.prepare(call)
        fresh = self._core.fresh_from_cache(call, prepared)
        if fresh is not None:
            return fresh
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._send(prepared)
            except httpx.TransportError as exc:
                retry = self._core.connection_retry(exc, attempt)
                if retry is None:
                    raise self._core.connection_error(exc) from exc
                await self._sleep(retry.delay)
                continue
            outcome = self._core.handle(call, prepared, response, attempt)
            if isinstance(outcome, Retry):
                await self._sleep(outcome.delay)
                continue
            return outcome

    async def _send(self, prepared: Prepared) -> RawResponse:
        url, headers = prepared.url, prepared.headers
        for hop in range(MAX_REDIRECTS + 1):
            request = self._http.build_request("GET", url, headers=headers)
            response = await self._http.send(request, stream=True)
            try:
                if self._core.is_redirect(response.status_code, response.headers) and (
                    hop < MAX_REDIRECTS
                ):
                    url, headers = self._core.redirect(
                        prepared, url, response.headers, response.status_code
                    )
                    continue
                buffer = BodyBuffer(response.headers.get("content-length"))
                async for chunk in response.aiter_bytes():
                    buffer.add(chunk)
                return RawResponse(response.status_code, response.headers, buffer.getvalue())
            finally:
                await response.aclose()
        raise AssertionError("unreachable")  # pragma: no cover

    # -- forecasts -------------------------------------------------------------------

    async def forecast(
        self,
        location: LocationArg,
        name: str | None = None,
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
        feels_like: StrList | None = None,
    ) -> ForecastResponse:
        """The forecast for a named location (``getLocationForecast``). Anonymous OK.

        Args:
            location: ``"or/mt-hood-meadows"``, a state code with ``name``, or
                any object with ``state`` and ``slug`` (a search hit, a
                ``LocationRef``).
            name: The location slug, when ``location`` is just the state.
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
            diagnostics: Opt-in diagnostics: ``provenance``, ``ptype``.
            feels_like: Feels-like indices (default ``nws``).

        Raises:
            NotFoundError: The location does not exist.
            UsageError: An argument is invalid; nothing was sent.
        """
        call = self._core.location_forecast(
            location,
            name,
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
            feels_like=feels_like,
        )
        return await self._run(call)

    async def forecast_at(
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
            feels_like=feels_like,
        )
        return await self._run(call)

    # -- current conditions and alerts ------------------------------------------------

    async def current(
        self,
        location: LocationArg,
        name: str | None = None,
        *,
        units: UnitsArg | None = None,
        sources: StrList | None = None,
        exclude_sources: StrList | None = None,
        include_nowcast_hours: bool = False,
    ) -> CurrentResponse:
        """Current conditions at a named location (``getCurrentConditions``)."""
        path = _location_path(location, name) + "/current"
        return await self._run(
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

    async def current_at(
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
        return await self._run(
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

    async def alerts(self, location: LocationArg, name: str | None = None) -> AlertsResponse:
        """Active alerts at a named location (``getLocationAlerts``)."""
        path = _location_path(location, name) + "/alerts"
        return await self._run(self._core.alerts(path, Query(), "getLocationAlerts"))

    async def alerts_at(self, lat: float, lon: float) -> AlertsResponse:
        """Active alerts at coordinates (``getAlertsByCoordinates``). Pro."""
        query = _coordinates(lat, lon)
        return await self._run(self._core.alerts("/api/v1/alerts", query, "getAlertsByCoordinates"))

    # -- places ----------------------------------------------------------------------

    async def nearby(
        self,
        location: LocationArg,
        name: str | None = None,
        *,
        limit: int | None = None,
        radius_km: float | None = None,
        units: UnitsArg | None = None,
    ) -> NearbyLocationsResponse:
        """Locations near a named location (``getNearbyLocations``)."""
        return await self._run(
            self._core.nearby_location(
                location, name, limit=limit, radius_km=radius_km, units=units
            )
        )

    async def nearby_at(
        self,
        lat: float,
        lon: float,
        *,
        limit: int | None = None,
        radius_km: float | None = None,
        units: UnitsArg | None = None,
    ) -> NearbyPointResponse:
        """Locations near coordinates (``getNearbyByCoordinates``)."""
        return await self._run(
            self._core.nearby_point(lat, lon, limit=limit, radius_km=radius_km, units=units)
        )

    async def search(
        self,
        q: str,
        *,
        state: str | None = None,
        county: str | None = None,
        location_type: LocationType | str | None = None,
        limit: int | None = None,
    ) -> SearchLocationsResponse:
        """Search locations by name (``searchLocations``). Sent without the key."""
        return await self._run(
            self._core.search(
                q, state=state, county=county, location_type=location_type, limit=limit
            )
        )

    async def list_locations(
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
        return await self._run(
            self._core.locations(
                state, location_type=location_type, units=units, limit=limit, cursor=cursor
            )
        )

    async def iter_locations(
        self,
        state: str | None = None,
        *,
        location_type: LocationType | str | None = None,
        units: UnitsArg | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[LocationSummary]:
        """Every location, fetching pages lazily as the iterator advances."""
        cursor: str | None = None
        while True:
            page = await self.list_locations(
                state, location_type=location_type, units=units, limit=limit, cursor=cursor
            )
            for item in page.locations:
                yield item
            if not page.next_cursor:
                return
            cursor = page.next_cursor

    # -- catalog ---------------------------------------------------------------------

    async def list_catalog_locations(
        self,
        *,
        admin1: str | None = None,
        country: str | None = None,
        location_type: str | None = None,
        template: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PublicCatalogLocationPage:
        """One page of the location catalog (``listCatalogLocations``)."""
        return await self._run(
            self._core.catalog_locations(
                admin1=admin1,
                country=country,
                location_type=location_type,
                template=template,
                limit=limit,
                cursor=cursor,
            )
        )

    async def iter_catalog_locations(
        self,
        *,
        admin1: str | None = None,
        country: str | None = None,
        location_type: str | None = None,
        template: str | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[PublicCatalogLocation]:
        """Every catalog location, following ``next_cursor`` lazily."""
        cursor: str | None = None
        while True:
            page = await self.list_catalog_locations(
                admin1=admin1,
                country=country,
                location_type=location_type,
                template=template,
                limit=limit,
                cursor=cursor,
            )
            for item in page.items:
                yield item
            if not page.next_cursor:
                return
            cursor = page.next_cursor

    async def catalog_location(
        self, slug: str, *, include: StrList | None = None, locale: str | None = None
    ) -> PublicCatalogLocationDetail:
        """One catalog location (``getCatalogLocation``). Sent without the key."""
        return await self._run(self._core.catalog_location(slug, include=include, locale=locale))

    async def list_catalog_stations(
        self,
        *,
        admin1: str | None = None,
        country: str | None = None,
        network: StrList | None = None,
        capabilities: StrList | None = None,
        status: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PublicCatalogStationPage:
        """One page of the station catalog (``listCatalogStations``).

        ``capabilities`` are all required (sent as repeated ``capability``).
        """
        return await self._run(
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

    async def iter_catalog_stations(
        self,
        *,
        admin1: str | None = None,
        country: str | None = None,
        network: StrList | None = None,
        capabilities: StrList | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[PublicCatalogStation]:
        """Every catalog station, following ``next_cursor`` lazily."""
        cursor: str | None = None
        while True:
            page = await self.list_catalog_stations(
                admin1=admin1,
                country=country,
                network=network,
                capabilities=capabilities,
                status=status,
                limit=limit,
                cursor=cursor,
            )
            for item in page.items:
                yield item
            if not page.next_cursor:
                return
            cursor = page.next_cursor

    async def catalog_station(
        self, slug: str, *, include: StrList | None = None, locale: str | None = None
    ) -> PublicCatalogStationDetail:
        """One catalog station (``getCatalogStation``). Sent without the key."""
        return await self._run(self._core.catalog_station(slug, include=include, locale=locale))

    # -- runs, storm reports, attribution -----------------------------------------------

    async def runs(self, *, limit: int | None = None) -> RunsResponse:
        """The served model run and recent runs (``getAvailableRuns``)."""
        return await self._run(self._core.runs(limit=limit))

    async def storm_reports(self, *, limit: int | None = None) -> StormReportsResponse:
        """Recent verified storms (``getStormReports``)."""
        return await self._run(self._core.storm_reports(limit=limit))

    async def storm_report(self, report_id: int) -> StormReportCard:
        """One verified storm (``getStormReport``)."""
        return await self._run(self._core.storm_report(report_id))

    async def attribution(self) -> AttributionRegistry:
        """Every data provider and its licence (``getAttribution``). Sent without the key."""
        return await self._run(self._core.attribution())
