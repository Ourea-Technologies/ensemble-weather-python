"""Transport behaviour beyond the shared vectors: cache, retries, paging, errors."""

from __future__ import annotations

import asyncio
import email.utils
import warnings
from typing import TYPE_CHECKING

import httpx
import pytest

from ensemble_weather import (
    APIConnectionError,
    AsyncClient,
    CacheEntry,
    Chance,
    Client,
    MemoryCache,
    OureaDeprecationWarning,
    RateLimitError,
    UnexpectedResponseError,
    UsageError,
    __version__,
)
from ensemble_weather._core import _reset_deprecation_warnings, parse_retry_after, user_agent

if TYPE_CHECKING:
    from collections.abc import Callable

    from conftest import Recorder

# --- configuration -------------------------------------------------------------------


def test_user_agent_names_the_sdk_and_runtime() -> None:
    assert user_agent().startswith(f"ensemble-weather-python/{__version__} (")
    assert user_agent("my-app/1.2").endswith(") my-app/1.2")


def test_base_url_from_environment(
    monkeypatch: pytest.MonkeyPatch, recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    monkeypatch.setenv("OUREA_BASE_URL", "http://127.0.0.1:9/")
    recorder.add(200, name="attribution.json")
    make_client().attribution()
    assert str(recorder.requests[0].url) == "http://127.0.0.1:9/api/v1/attribution"


@pytest.mark.parametrize(
    "kwargs", [{"units": "si"}, {"timeout": 0}, {"max_retries": -1}, {"timeout": float("inf")}]
)
def test_bad_configuration(kwargs: dict[str, object]) -> None:
    with pytest.raises(UsageError):
        Client(**kwargs)  # type: ignore[arg-type]


# --- cache ------------------------------------------------------------------------------


def test_memory_cache_is_bounded() -> None:
    cache = MemoryCache(max_entries=2, max_bytes=10)
    for key in "abc":
        cache.set(key, CacheEntry(body=b"12", etag='"e"', headers=(), stored_at=0))
    assert len(cache) == 2
    assert cache.get("a") is None
    cache.set("big", CacheEntry(body=b"x" * 11, etag=None, headers=(), stored_at=0))
    assert cache.get("big") is None
    cache.set("d", CacheEntry(body=b"123456", etag=None, headers=(), stored_at=0))
    assert cache.size_bytes <= 10


def test_positive_max_age_serves_without_a_request(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    recorder.add(
        200,
        name="attribution.json",
        headers={"Content-Type": "application/json", "Cache-Control": "max-age=300"},
    )
    client = make_client()
    client.attribution()
    second = client.attribution()
    assert len(recorder.requests) == 1
    assert second.meta.from_cache
    assert not second.meta.revalidated


def test_s_maxage_is_ignored(recorder: Recorder, make_client: Callable[..., Client]) -> None:
    cache_control = "public, max-age=0, s-maxage=3600, stale-while-revalidate=300"
    headers = {"Content-Type": "application/json", "Cache-Control": cache_control, "ETag": '"a"'}
    recorder.add(200, name="attribution.json", headers=headers)
    recorder.add(304, headers={"ETag": '"a"'})
    client = make_client()
    client.attribution()
    again = client.attribution()
    assert len(recorder.requests) == 2
    assert recorder.requests[1].headers["If-None-Match"] == '"a"'
    assert again.revalidated


def test_retry_keeps_if_none_match(recorder: Recorder, make_client: Callable[..., Client]) -> None:
    recorder.add(200, name="attribution.json", headers={"ETag": '"a"'})
    recorder.add(503, name="error-unavailable.json")
    recorder.add(304, headers={"ETag": '"a"'})
    client = make_client()
    client.attribution()
    client.attribution()
    assert [r.headers.get("If-None-Match") for r in recorder.requests] == [None, '"a"', '"a"']


def test_custom_cache(recorder: Recorder, make_client: Callable[..., Client]) -> None:
    class DictCache:
        def __init__(self) -> None:
            self.data: dict[str, CacheEntry] = {}

        def get(self, key: str) -> CacheEntry | None:
            return self.data.get(key)

        def set(self, key: str, entry: CacheEntry) -> None:
            self.data[key] = entry

        def delete(self, key: str) -> None:
            self.data.pop(key, None)

    store = DictCache()
    recorder.add(200, name="attribution.json", headers={"ETag": '"z"'})
    make_client(cache=store).attribution()
    assert len(store.data) == 1


# --- retries ---------------------------------------------------------------------------


def test_retry_after_http_date() -> None:
    now = 1_800_000_000.0
    date = email.utils.formatdate(now + 7, usegmt=True)
    assert parse_retry_after(date, now) == pytest.approx(7)
    assert parse_retry_after("5", now) == 5
    assert parse_retry_after("soon", now) is None


def test_backoff_is_capped_full_jitter(recorder: Recorder) -> None:
    for _ in range(6):
        recorder.add(502, content=b"bad gateway")
    recorder.add(200, name="attribution.json")
    delays: list[float] = []
    client = Client(transport=httpx.MockTransport(recorder), max_retries=6)
    client._sleep = delays.append
    client._core.random = lambda: 1.0
    client.attribution()
    assert delays == [0.5, 1.0, 2.0, 4.0, 8.0, 8.0]
    client.close()


def test_connection_errors_are_retried() -> None:
    attempts = 0

    def flaky(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("reset", request=request)
        return httpx.Response(200, content=b'{"providers": []}')

    client = Client(transport=httpx.MockTransport(flaky))
    client._sleep = lambda _d: None
    assert client.attribution().providers == []
    assert attempts == 3
    client.close()


def test_connection_error_after_retries() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = Client(transport=httpx.MockTransport(down), max_retries=1)
    client._sleep = lambda _d: None
    with pytest.raises(APIConnectionError) as caught:
        client.attribution()
    assert caught.value.category == "connection"
    client.close()


def test_rate_limit_error_carries_state(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    headers = {
        "Content-Type": "application/json",
        "Retry-After": "120",
        "RateLimit-Remaining": "0",
        "X-Request-Id": "req-1",
    }
    recorder.add(429, name="error-rate-limited.json", headers=headers)
    client = make_client()
    with pytest.raises(RateLimitError) as caught:
        client.attribution()
    error = caught.value
    assert error.retry_after == 120
    assert error.request_id == "req-1"
    assert error.rate_limit is not None
    assert error.rate_limit.remaining == 0
    assert client.rate_limit is not None


# --- responses -----------------------------------------------------------------------


def test_missing_answer_is_an_error(recorder: Recorder, make_client: Callable[..., Client]) -> None:
    recorder.add(200, name="forecast-prob-snow.json")
    with pytest.raises(UnexpectedResponseError):
        make_client().forecast(
            "or/mt-hood-meadows", units="imperial", prob=[Chance.at_least("snowfall", 7, "in")]
        )


def test_results_carry_the_callers_term(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    recorder.add(200, name="forecast-prob-snow.json")
    term = Chance.at_least("snowfall", 6, "in")
    forecast = make_client().forecast("or/mt-hood-meadows", units="imperial", prob=[term])
    assert forecast.probabilities[0].term is term
    assert forecast.probabilities[0].window.to_query() == "24h"


def test_malformed_body_is_unexpected(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    recorder.add(200, content=b'{"providers": "nope"}')
    with pytest.raises(UnexpectedResponseError):
        make_client().attribution()


def test_deprecation_warns_once_per_operation(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    _reset_deprecation_warnings()
    headers = {"Content-Type": "application/json", "Sunset": "Wed, 01 Dec 2027 00:00:00 GMT"}
    for _ in range(3):
        recorder.add(200, name="attribution.json", headers=headers)
    client = make_client(cache=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client.attribution()
        client.attribution()
        client.attribution()
    found = [w for w in caught if issubclass(w.category, OureaDeprecationWarning)]
    assert len(found) == 1
    assert "getAttribution" in str(found[0].message)


# --- the async client and paging ---------------------------------------------------------


def test_async_iterator_follows_cursor(
    recorder: Recorder, make_async_client: Callable[..., AsyncClient]
) -> None:
    recorder.add(200, name="catalog-page-1.json")
    recorder.add(200, name="catalog-page-2.json")

    async def main() -> list[str]:
        async with make_async_client() as client:
            return [item.slug async for item in client.iter_catalog_locations()]

    assert asyncio.run(main()) == ["mt-hood-meadows", "timberline-lodge"]


def test_sync_location_iterator(recorder: Recorder, make_client: Callable[..., Client]) -> None:
    row = {
        "slug": "a",
        "state": "co",
        "name": "A",
        "lat": 39.0,
        "lon": -105.0,
        "elevation_m": 3000.0,
        "type": "summit",
        "timezone": "America/Denver",
        "county": "Summit",
    }
    recorder.add(200, json={"state": "co", "count": 1, "locations": [row], "next_cursor": "a"})
    recorder.add(200, json={"state": "co", "count": 1, "locations": [{**row, "slug": "b"}]})
    slugs = [loc.slug for loc in make_client().iter_locations("co", limit=1)]
    assert slugs == ["a", "b"]
    assert recorder.requests[1].url.query == b"cursor=a&limit=1"
