"""Canonical request building: numbers, rounding, terms, parameters, locations."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import pytest

from ensemble_weather import Chance, Client, Total, UsageError, Window
from ensemble_weather._query import format_number
from ensemble_weather._units import convert, format_rounded
from ensemble_weather.enums import Unit, UnitSystem
from ensemble_weather.probabilities import prob_query, totals_query

if TYPE_CHECKING:
    from collections.abc import Callable

    from conftest import Recorder


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (0.0625, 3, "0.063"),  # banker's rounding would give 0.062
        (1.005, 2, "1.00"),  # 1.005 * 100 == 100.4999...
        (2.5, 0, "3"),  # half away from zero, not to even
        (-2.5, 0, "-3"),
        (-0.04, 1, "0.0"),  # -0 prints as 0
        (-0.0, 2, "0.00"),
        (152.39999999999998, 2, "152.40"),
        (1524.4, 0, "1524"),
        (-5, 1, "-5.0"),
        (0.0005, 3, "0.001"),
    ],
)
def test_rounding_is_half_away_from_zero(value: float, decimals: int, expected: str) -> None:
    assert format_rounded(value, decimals) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (45.3311, "45.3311"),
        (-121.6649, "-121.6649"),
        (1661, "1661"),
        (1661.0, "1661"),
        (0.1, "0.1"),
        (1e-05, "0.00001"),
        (1.5e16, "15000000000000000"),
        (123456789.125, "123456789.125"),
    ],
)
def test_numbers_are_shortest_without_exponent(value: float, expected: str) -> None:
    assert format_number(value) == expected


def test_unit_conversion_uses_exact_factors() -> None:
    assert convert(6, Unit.IN, Unit.MM) == 6 * 25.4
    assert convert(32, Unit.DEG_F, Unit.DEG_C) == 0
    assert convert(0, Unit.DEG_C, Unit.K) == 273.15
    assert convert(5000, Unit.FT, Unit.M) == 5000 * 0.3048
    assert convert(10, Unit.MPH, Unit.M_PER_S) == 10 * 0.44704
    assert convert(273.15, Unit.K, Unit.DEG_F) == pytest.approx(32)


def test_prob_query_kelvin_and_order() -> None:
    wire, keys = prob_query(
        [
            Chance.at_most("temperature", 32, "degF"),
            Chance.at_least("precipitation", 0.5, "in", window=Window(24, 48)),
            Chance.at_least("precipitation", 0.5, "in"),
        ],
        UnitSystem.KELVIN,
    )
    assert (
        wire == "precipitation:ge:12.70:24h,precipitation:ge:12.70:24-48h,temperature:le:273.2:24h"
    )  # 273.15 * 10 == 2731.5 in doubles
    assert [k[0] for k in keys] == ["temperature", "precipitation", "precipitation"]


def test_prob_sort_by_aggregation_then_threshold() -> None:
    wire, _ = prob_query(
        [
            Chance.at_least("temperature", 5),
            Chance.at_least("temperature", -3, aggregation="all"),
            Chance.at_least("temperature", -3),
        ],
        UnitSystem.METRIC,
    )
    assert wire == "temperature:ge:-3.0:24h,temperature:ge:5.0:24h,temperature:ge:-3.0:24h:all"


def test_totals_query_sorted_and_deduplicated() -> None:
    wire, keys = totals_query(
        [Total("snowfall", 48), Total("precipitation", Window(24, 48)), Total("snowfall", 48)]
    )
    assert wire == "precipitation:24-48h,snowfall:48h"
    assert len(keys) == 3


@pytest.mark.parametrize(
    "build",
    [
        lambda: Chance.at_least("snowfall", 6, aggregation="any"),
        lambda: Chance.at_least("temperature", 6, aggregation="total"),
        lambda: Chance.at_least("snowfall", 6, "degF"),
        lambda: Chance.at_least("humidity", 6),
        lambda: Chance("snowfall", "gt", 6),
        lambda: Chance.at_least("snowfall", float("nan")),
        lambda: Chance.at_least("snowfall", True),
        lambda: Chance.at_least("snowfall", 6, window=361),
        lambda: Chance.at_least("snowfall", 6, window=Window(12, 6)),
        lambda: Total("temperature", 24),
        lambda: Window(0, 0),
    ],
)
def test_invalid_terms_are_usage_errors(build: Callable[[], object]) -> None:
    with pytest.raises(UsageError):
        build()


def test_usage_errors_are_value_errors() -> None:
    with pytest.raises(ValueError, match="aggregation"):
        Chance.at_least("precipitation", 1, aggregation="all")


def _query(recorder: Recorder) -> str:
    return recorder.requests[-1].url.query.decode()


def test_forecast_options_are_canonical(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    recorder.add(200, name="forecast-metric.json")
    make_client().forecast(
        "OR",
        "mt-hood-meadows",
        sources=["snotel", "ski_resort"],
        run=dt.datetime(2026, 11, 15, tzinfo=dt.timezone.utc),
        feels_like=["nws"],
        diagnostics="provenance",
        elevations="all",
        max_days=5,
    )
    path = recorder.requests[-1].url.raw_path.split(b"?")[0]
    assert path == b"/api/v1/locations/or/mt-hood-meadows"
    assert _query(recorder) == (
        "diagnostics=provenance&elevations=all&max_days=5"
        "&run=2026-11-15T00%3A00%3A00Z&sources=snotel%2Cski_resort"
    )


def test_client_units_apply_to_every_route(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    recorder.add(200, name="forecast-imperial.json")
    client = make_client(units="imperial")
    client.forecast("or/mt-hood-meadows")
    assert _query(recorder) == "units=imperial"
    recorder.add(200, name="forecast-metric.json")
    client.forecast("or/mt-hood-meadows", units="metric")
    assert _query(recorder) == ""


def test_naive_datetime_is_refused(make_client: Callable[..., Client]) -> None:
    with pytest.raises(UsageError):
        make_client().forecast("or/mt-hood-meadows", run=dt.datetime(2026, 11, 15))  # noqa: DTZ001


def test_repeated_capability_is_sorted_once(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    recorder.add(200, name="catalog-page-2.json")
    make_client().list_catalog_stations(capabilities=["swe", "air_temp", "swe"], network="Snotel")
    assert _query(recorder) == "capability=air_temp&capability=swe&network=Snotel"


def test_location_from_an_object(recorder: Recorder, make_client: Callable[..., Client]) -> None:
    recorder.add(200, name="search.json")
    recorder.add(200, name="forecast-metric.json")
    client = make_client()
    hit = client.search("hood").items[0]
    client.forecast(hit)
    assert recorder.requests[-1].url.path == "/api/v1/locations/or/mt-hood-meadows"


@pytest.mark.parametrize("bad", ["mt-hood-meadows", "or/a/b", "/x", "or/"])
def test_bad_location_strings(bad: str, make_client: Callable[..., Client]) -> None:
    with pytest.raises(UsageError):
        make_client().forecast(bad)


@pytest.mark.parametrize(("lat", "lon"), [(91, 0), (0, -181), (float("nan"), 0)])
def test_bad_coordinates(lat: float, lon: float, make_client: Callable[..., Client]) -> None:
    with pytest.raises(UsageError):
        make_client().forecast_at(lat, lon)


def test_every_route_builds_its_path(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    client = make_client()
    calls: list[tuple[Callable[[], object], str, str]] = [
        (
            lambda: client.current("or/x", include_nowcast_hours=True),
            "/api/v1/locations/or/x/current",
            "include=nowcast_hours",
        ),
        (
            lambda: client.current_at(45.5, -122.5, elevation_m=100),
            "/api/v1/current",
            "elevation_m=100&lat=45.5&lon=-122.5",
        ),
        (lambda: client.alerts("or", "x"), "/api/v1/locations/or/x/alerts", ""),
        (lambda: client.alerts_at(45.5, -122.5), "/api/v1/alerts", "lat=45.5&lon=-122.5"),
        (
            lambda: client.nearby("or/x", limit=3, radius_km=25),
            "/api/v1/locations/or/x/nearby",
            "radius_km=25",
        ),
        (
            lambda: client.nearby_at(45.5, -122.5, limit=5),
            "/api/v1/nearby",
            "lat=45.5&limit=5&lon=-122.5",
        ),
        (client.list_locations, "/api/v1/locations", ""),
        (
            lambda: client.list_locations("CO", location_type="summit", limit=100),
            "/api/v1/locations/co",
            "limit=100&type=summit",
        ),
        (
            lambda: client.catalog_location("a b", include=["content", "ads"], locale="en"),
            "/api/v1/catalog/locations/a%20b",
            "include=content%2Cads",
        ),
        (lambda: client.catalog_station("snotel-651"), "/api/v1/catalog/stations/snotel-651", ""),
        (lambda: client.runs(limit=10), "/api/v1/runs", ""),
        (lambda: client.storm_reports(limit=5), "/api/v1/storm-reports", "limit=5"),
        (lambda: client.storm_report(42), "/api/v1/storm-reports/42", ""),
    ]
    for call, path, query in calls:
        recorder.add(404, name="error-not-found.json")
        with pytest.raises(Exception):  # noqa: B017, PT011 - only the request matters here
            call()
        request = recorder.requests[-1]
        assert request.url.raw_path.split(b"?")[0].decode() == path
        assert request.url.query.decode() == query
