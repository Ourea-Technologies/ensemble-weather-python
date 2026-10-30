"""Runs every shared vector in spec/vectors/ (BEHAVIOR.md section 13).

Each vector runs twice: on :class:`Client` and on :class:`AsyncClient`, both
over an ``httpx.MockTransport`` that replays the vector's responses and
records the requests. A vector this runner cannot execute fails; nothing is
skipped.

The only per-language code is :func:`plan`, which maps a vector's semantic
operation and arguments onto this SDK's methods.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx
import pytest

from ensemble_weather import (
    AsyncClient,
    Chance,
    Client,
    OureaDeprecationWarning,
    OureaError,
    Total,
    Window,
)
from ensemble_weather._core import _reset_deprecation_warnings

VECTORS = Path(__file__).resolve().parent.parent / "spec" / "vectors"
CASES = sorted(p for p in VECTORS.rglob("*.json") if "bodies" not in p.relative_to(VECTORS).parts)
EXPECTED_VECTOR_COUNT = 43


def test_every_vector_is_collected() -> None:
    assert len(CASES) == EXPECTED_VECTOR_COUNT


# --- the mock transport -----------------------------------------------------------


class Replay:
    """Answers requests with the vector's responses, in order, and records them."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.responses:
            msg = f"unexpected request #{len(self.requests)}: {request.url}"
            raise AssertionError(msg)
        spec = self.responses.pop(0)
        if "body_file" in spec:
            content = (VECTORS / spec["body_file"]).read_bytes()
        else:
            content = spec.get("body", "").encode()
        return httpx.Response(spec["status"], headers=spec.get("headers", {}), content=content)


# --- mapping a vector call onto the SDK (the per-language part) --------------------


@dataclass
class Plan:
    method: str
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)
    iterate: bool = False


def _window(spec: dict[str, int] | None) -> int | Window:
    if spec is None:
        return 24
    if "hours" in spec:
        return spec["hours"]
    return Window(spec["start_hours"], spec["end_hours"])


def _chance(term: dict[str, Any]) -> Chance:
    threshold = term["threshold"]
    return Chance(
        term["variable"],
        term["op"],
        threshold["value"],
        threshold.get("unit"),
        window=_window(term.get("window")),
        aggregation=term.get("aggregation"),
    )


_METHODS = {
    "getLocationForecast": "forecast",
    "getPointForecast": "get_point_forecast",
    "getCurrentConditions": "current",
    "getCurrentByCoordinates": "get_point_current",
    "getLocationAlerts": "alerts",
    "getAlertsByCoordinates": "get_point_alerts",
    "getNearbyLocations": "nearby",
    "getNearbyByCoordinates": "get_point_nearby",
    "searchLocations": "search",
    "getAllLocations": "list_locations",
    "getLocations": "list_locations",
    "listCatalogLocations": "list_catalog_locations",
    "getCatalogLocation": "catalog_location",
    "listCatalogStations": "list_catalog_stations",
    "getCatalogStation": "catalog_station",
    "getAvailableRuns": "runs",
    "getAttribution": "attribution",
}

_ITERATORS = {
    "list_locations": "iter_locations",
    "list_catalog_locations": "iter_catalog_locations",
    "list_catalog_stations": "iter_catalog_stations",
}

_POSITIONAL = ("location", "state", "slug", "lat", "lon", "q")
_RENAMED: dict[str, str] = {"type": "location_type", "capability": "capabilities"}


def plan(call: dict[str, Any]) -> Plan:
    """Map ``{"operation", "args"}`` to a method call on this SDK."""
    method = _METHODS[call["operation"]]
    args = dict(call.get("args", {}))
    result = Plan(method)
    if args.pop("iterate", False):
        result.method = _ITERATORS[method]
        result.iterate = True
    for name in _POSITIONAL:
        if name in args:
            result.args.append(args.pop(name))
    if "prob" in args:
        result.kwargs["prob"] = [_chance(t) for t in args.pop("prob")]
    if "totals" in args:
        result.kwargs["totals"] = [
            Total(t["variable"], _window(t.get("window"))) for t in args.pop("totals")
        ]
    for key, value in args.items():
        result.kwargs[_RENAMED.get(str(key), str(key))] = value
    return result


# --- checking -------------------------------------------------------------------


_TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")
_ATTRIBUTES = {"from": "from_"}


def resolve(result: Any, path: str) -> Any:
    value = result
    first = True
    for name, index in _TOKEN.findall(path):
        if value is None:
            return None
        if index:
            value = value[int(index)]
        elif first and name in {"revalidated", "rate_limit"}:
            value = getattr(value.meta, name)
        else:
            value = getattr(value, _ATTRIBUTES.get(name, name))
        first = False
    return value


def check_value(path: str, actual: Any, expected: Any) -> None:
    if isinstance(expected, dict) and set(expected) == {"unknown"}:
        assert getattr(actual, "is_unknown", False), f"{path}: {actual!r} is not unknown"
        assert actual.value == expected["unknown"], path
    elif expected is None:
        assert actual is None, f"{path}: expected absent, got {actual!r}"
    elif isinstance(expected, bool):
        assert actual is expected, f"{path}: expected {expected!r}, got {actual!r}"
    elif isinstance(expected, (int, float)):
        assert isinstance(actual, (int, float)), f"{path}: {actual!r} is not a number"
        assert math.isclose(actual, expected, rel_tol=1e-12), f"{path}: {actual!r} != {expected!r}"
    else:
        assert actual == expected, f"{path}: expected {expected!r}, got {actual!r}"


def check_result(result: Any, expected: dict[str, Any]) -> None:
    for path, value in expected.items():
        check_value(path, resolve(result, path), value)


def _query_pairs(request: httpx.Request) -> list[tuple[str, str]]:
    raw = request.url.query.decode()
    pairs = []
    for part in raw.split("&") if raw else []:
        name, _, value = part.partition("=")
        pairs.append((unquote(name), unquote(value)))
    return pairs


def check_request(request: httpx.Request, expected: dict[str, Any]) -> None:
    label = f"{request.method} {request.url}"
    if "method" in expected:
        assert request.method == expected["method"], label
    if "path" in expected:
        assert request.url.raw_path.split(b"?")[0].decode() == expected["path"], label
    if "url_prefix" in expected:
        assert str(request.url).startswith(expected["url_prefix"]), label
    if "query_string" in expected:
        assert request.url.query.decode() == expected["query_string"], label
    pairs = _query_pairs(request)
    names = [n for n, _ in pairs]
    assert len(names) == len(set(names)), f"{label}: a parameter is repeated"
    for name, value in expected.get("query", {}).items():
        assert (name, value) in pairs, f"{label}: expected {name}={value!r}"
    for name in expected.get("query_absent", []):
        assert name not in names, f"{label}: {name} must be absent"
    for name, value in expected.get("headers", {}).items():
        assert request.headers.get(name) == value, f"{label}: header {name}"
    for name in expected.get("headers_absent", []):
        assert name not in request.headers, f"{label}: header {name} must be absent"
    for name, pattern in expected.get("headers_match", {}).items():
        assert re.match(pattern, request.headers.get(name, "")), f"{label}: header {name}"


def check_error(error: OureaError, expected: dict[str, Any]) -> None:
    assert error.category == expected["category"], f"{type(error).__name__}: {error}"
    for key in ("code", "status", "retry_after"):
        if key in expected:
            check_value(key, getattr(error, key, None), expected[key])
    secret = expected.get("string_excludes")
    if secret:
        for text in (str(error), repr(error), error.message, *map(str, error.args)):
            assert secret not in text


# --- running ----------------------------------------------------------------------


@dataclass
class Outcome:
    results: list[Any]
    error: OureaError | None
    delays: list[float]


def _client_kwargs(spec: dict[str, Any], replay: Replay, *, asynchronous: bool) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "transport": httpx.MockTransport(replay),
    }
    for key in ("api_key", "base_url", "max_retries", "cache", "send_key_on_open_routes"):
        if key in spec:
            kwargs[key] = spec[key]
    del asynchronous
    return kwargs


def run_sync(case: dict[str, Any], replay: Replay) -> Outcome:
    spec = case.get("client", {})
    delays: list[float] = []
    clients: list[Client] = []

    def make(**overrides: Any) -> Client:
        client = Client(**{**_client_kwargs(spec, replay, asynchronous=False), **overrides})
        client._sleep = delays.append
        client._core.random = lambda: 1.0
        clients.append(client)
        return client

    main = make()
    results: list[Any] = []
    try:
        for call in case.get("calls") or [case["call"]]:
            client = main
            if "with_api_key" in call:
                client = make(api_key=call["with_api_key"], cache=main.cache or False)
            p = plan(call)
            value = getattr(client, p.method)(*p.args, **p.kwargs)
            results.append(list(value) if p.iterate else value)
    except OureaError as exc:
        return Outcome(results, exc, delays)
    finally:
        for client in clients:
            client.close()
    return Outcome(results, None, delays)


async def run_async(case: dict[str, Any], replay: Replay) -> Outcome:
    spec = case.get("client", {})
    delays: list[float] = []
    clients: list[AsyncClient] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    def make(**overrides: Any) -> AsyncClient:
        client = AsyncClient(**{**_client_kwargs(spec, replay, asynchronous=True), **overrides})
        client._sleep = sleep
        client._core.random = lambda: 1.0
        clients.append(client)
        return client

    main = make()
    results: list[Any] = []
    try:
        for call in case.get("calls") or [case["call"]]:
            client = main
            if "with_api_key" in call:
                client = make(api_key=call["with_api_key"], cache=main.cache or False)
            p = plan(call)
            if p.iterate:
                results.append(
                    [item async for item in getattr(client, p.method)(*p.args, **p.kwargs)]
                )
            else:
                results.append(await getattr(client, p.method)(*p.args, **p.kwargs))
    except OureaError as exc:
        return Outcome(results, exc, delays)
    finally:
        for client in clients:
            await client.aclose()
    return Outcome(results, None, delays)


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("path", CASES, ids=[str(p.relative_to(VECTORS))[:-5] for p in CASES])
def test_vector(path: Path, mode: str, monkeypatch: pytest.MonkeyPatch) -> None:
    case = json.loads(path.read_text(encoding="utf-8"))
    monkeypatch.delenv("OUREA_API_KEY", raising=False)
    monkeypatch.delenv("OUREA_BASE_URL", raising=False)
    for name, value in case.get("client", {}).get("env", {}).items():
        monkeypatch.setenv(name, value)
    _reset_deprecation_warnings()
    replay = Replay(case.get("responses", []))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        outcome = run_sync(case, replay) if mode == "sync" else asyncio.run(run_async(case, replay))

    expect = case.get("expect", {})
    if "error" in expect:
        assert outcome.error is not None, "expected an error"
        check_error(outcome.error, expect["error"])
    elif outcome.error is not None:
        raise outcome.error

    requests = replay.requests
    if "expect_request" in case:
        if case["expect_request"] is None:
            assert requests == []
        else:
            assert requests, "no request was sent"
            for request in requests:
                check_request(request, case["expect_request"])
    if "expect_requests" in case:
        assert len(requests) == len(case["expect_requests"])
        for request, expected in zip(requests, case["expect_requests"], strict=True):
            check_request(request, expected)
    if "requests" in expect:
        assert len(requests) == expect["requests"]
    if "delays_s" in expect:
        assert outcome.delays == pytest.approx(expect["delays_s"])
    if "result" in expect:
        check_result(outcome.results[0], expect["result"])
    for result, expected in zip(outcome.results, expect.get("results", []), strict=False):
        check_result(result, expected)
    if "results" in expect:
        assert len(outcome.results) == len(expect["results"])
    if "items" in expect:
        assert [item.slug for item in outcome.results[-1]] == expect["items"]
    deprecations = [w for w in caught if issubclass(w.category, OureaDeprecationWarning)]
    expected_warnings = expect.get("warnings", [])
    assert len(deprecations) == len(expected_warnings)
    for warning, wanted in zip(deprecations, expected_warnings, strict=True):
        assert wanted["contains"] in str(warning.message)
