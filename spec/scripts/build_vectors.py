#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Write the shared SDK test vectors (vectors/) from the cases below.

Run from the repository root: ``python3 scripts/build_vectors.py``. CI runs it
with ``--check`` and fails if the committed files differ, so the vectors are
only ever edited here. BEHAVIOR.md section 13 defines the format.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "vectors"


def q(mean: float, p10: float, p25: float, p50: float, p75: float, p90: float, **extra: float) -> dict:
    return {"mean": mean, "p10": p10, "p25": p25, "p50": p50, "p75": p75, "p90": p90, **extra}


LOCATION = {
    "slug": "mt-hood-meadows",
    "state": "or",
    "name": "Mt. Hood Meadows",
    "lat": 45.3311,
    "lon": -121.6649,
    "elevation_m": 1661.0,
    "type": "ski_area",
    "timezone": "America/Los_Angeles",
}

ATTRIBUTION = {
    "sources": ["ecmwf-ifs-ens", "noaa-gefs"],
    "credit": "Forecast by Ourea from ECMWF and NOAA ensemble data.",
    "url": "https://oureawx.com/attribution",
}


def hour(i: int, units: str) -> dict:
    imperial = units == "imperial"
    t = q(-2.0 + i, -4.0 + i, -3.0 + i, -2.0 + i, -1.0 + i, 0.0 + i, min=-6.0 + i, max=2.0 + i)
    if imperial:
        t = {k: round(v * 9 / 5 + 32, 1) for k, v in t.items()}
    return {
        "valid_time": f"2026-11-15T{i:02d}:00:00Z",
        "lead_time_hours": i,
        "is_night": True,
        "condition": "snow",
        "condition_text": "Snow",
        "condition_icon": "night_snow",
        "ensemble": {
            "temperature": t,
            "dewpoint": t,
            "precipitation": q(0.8, 0.0, 0.2, 0.6, 1.2, 2.0, min=0.0, max=3.1, probability=0.71),
            "wind_speed": q(6.0, 3.0, 4.5, 6.0, 7.5, 9.0, min=1.5, max=11.0),
            # Circular (CircularStats): each sector runs clockwise from `from`
            # to `to`, so `from` may be numerically greater than `to`.
            "wind_direction": {"mean": 5.0, "stddev": 12.0, "sector_50": {"from": 355.0, "to": 15.0}, "sector_90": {"from": 340.0, "to": 30.0}},
            "snow_level": q(900.0, 600.0, 750.0, 900.0, 1050.0, 1200.0, min=450.0, max=1400.0),
        },
    }


def forecast(units: str = "metric", hours: int = 3, **extra: object) -> dict:
    return {
        "location": LOCATION,
        "model_run": {
            "initialized_at": "2026-11-15T00:00:00Z",
            "total_members": 131,
            "models": [{"id": "ifs_ens"}, {"id": "gefs"}],
        },
        "units": units,
        "forecast": {"max_hours": hours, "interval_hours": 1, "timeseries": [hour(i, units) for i in range(hours)]},
        "nowcast_applied": True,
        "attribution": ATTRIBUTION,
        **extra,
    }


def prob(variable: str, op: str, threshold: float, start: int, end: int, aggregation: str, p: float | None, members: int = 131, term: str | None = None) -> dict:
    # `term` is the canonical spelling the server echoes (the request's own).
    return {
        "term": term,
        "variable": variable,
        "op": op,
        "threshold": threshold,
        "window_start_hours": start,
        "window_end_hours": end,
        "aggregation": aggregation,
        "from": f"2026-11-15T{start:02d}:00:00Z" if p is not None else None,
        "to": f"2026-11-{15 + end // 24}T{end % 24:02d}:00:00Z" if p is not None else None,
        "probability": p,
        "members": members,
        "null_reason": None if p is not None else "window_not_covered",
    }


def error(code: str, message: str) -> dict:
    return {
        "error": code,
        "message": message,
        "request_id": "01JBQ6ZK3V8M4T2N7XQH5R9W0C",
        "doc_url": f"https://docs.oureawx.com/features/errors/#{code.lower()}",
    }


FC_PATH = "/api/v1/locations/or/mt-hood-meadows"
FC_CALL = {"operation": "getLocationForecast", "args": {"state": "or", "slug": "mt-hood-meadows"}}

BODIES: dict[str, object] = {
    "forecast-metric.json": forecast(),
    "forecast-imperial.json": forecast("imperial"),
    "forecast-prob-snow.json": forecast(
        "imperial",
        probabilities=[
            # In the order SENT (canonical), not the caller's order.
            prob("snowfall", "ge", 6, 0, 24, "total", 0.42, term="snowfall:ge:6.000:24h"),
            prob("snowfall", "ge", 12, 0, 240, "total", None, members=0, term="snowfall:ge:12.000:240h"),
            prob("temperature", "le", 32, 0, 12, "any", 0.97, term="temperature:le:32.0:12h"),
        ],
    ),
    "forecast-totals.json": forecast(
        "metric",
        window_totals=[
            {
                "term": "precipitation:48h",
                "variable": "precipitation",
                "window_start_hours": 0,
                "window_end_hours": 48,
                "from": "2026-11-15T00:00:00Z",
                "to": "2026-11-17T00:00:00Z",
                "aggregation": "total",
                "quantiles": q(31.0, 12.0, 20.0, 29.0, 40.0, 52.0, min=4.0, max=88.0),
                "members": 131,
                "null_reason": None,
            },
            {
                "term": "snowfall:240h",
                "variable": "snowfall",
                "window_start_hours": 0,
                "window_end_hours": 240,
                "from": None,
                "to": None,
                "aggregation": "total",
                "quantiles": None,
                "members": 0,
                "null_reason": "window_not_covered",
            },
        ],
    ),
    "forecast-prob-mixed.json": forecast(
        probabilities=[
            # In the order SENT (canonical).
            prob("snow_level", "le", 1524, 0, 24, "any", 0.8, term="snow_level:le:1524:24h"),
            prob("temperature", "ge", -5.0, 0, 24, "any", 0.7, term="temperature:ge:-5.0:24h"),
            prob("temperature", "le", -5.0, 0, 24, "any", 0.3, term="temperature:le:-5.0:24h"),
            prob("wind_speed", "ge", 15.0, 0, 24, "any", 0.05, term="wind_speed:ge:15.0:24h"),
            prob("wind_speed", "ge", 15.0, 12, 36, "any", 0.11, term="wind_speed:ge:15.0:12-36h"),
        ],
    ),
    "catalog-detail.json": {**LOCATION, "elevations": [], "photos": [], "webcams": [], "nearby_stations": []},
    "attribution.json": {
        "providers": [
            {
                "id": "ecmwf",
                "name": "ECMWF",
                "credit": "Contains modified ECMWF data.",
                "licence": "CC-BY-4.0",
                "licence_url": "https://creativecommons.org/licenses/by/4.0/",
                "terms_url": "https://www.ecmwf.int/en/terms-use",
                "modified": True,
                "notices": [],
                "sources": [{"id": "ecmwf-ifs-ens", "name": "IFS ENS", "kind": "model", "provider": "ecmwf"}],
            }
        ]
    },
    "forecast-unknown-fields.json": {
        **forecast(),
        "a_field_added_in_v1_9": {"nested": [1, 2, 3]},
        "location": {**LOCATION, "type": "a_location_type_added_later"},
    },
    "search.json": {
        "items": [
            {**LOCATION, "key": "or/mt-hood-meadows", "county": "Hood River"},
        ],
        "count": 1,
    },
    "catalog-page-1.json": {"items": [LOCATION], "next_cursor": "c2"},
    "catalog-page-2.json": {"items": [{**LOCATION, "slug": "timberline-lodge", "name": "Timberline Lodge"}], "next_cursor": None},
    "error-outside-coverage.json": error("OUTSIDE_COVERAGE", "45.0,10.0 is outside the forecast domain (CONUS)."),
    "error-pro-required.json": error("PRO_REQUIRED", "Forecasts at arbitrary coordinates need a Pro API key."),
    "error-invalid-key.json": error("INVALID_API_KEY", "The API key is not valid."),
    "error-not-found.json": error("LOCATION_NOT_FOUND", "No location or/nowhere."),
    "error-bad-request.json": error("BAD_REQUEST", "prob term 'snowfall:gt:6' has an unknown op 'gt'."),
    "error-rate-limited.json": error("TOO_MANY_REQUESTS", "Rate limit exceeded."),
    "error-unavailable.json": error("FORECAST_UNAVAILABLE", "No forecast is available for this location yet."),
    "error-unknown-code.json": error("A_CODE_ADDED_LATER", "Something new."),
}

RL = {"RateLimit-Limit": "60", "RateLimit-Remaining": "59", "RateLimit-Reset": "1", "RateLimit-Policy": "60;w=60"}


def ok(body: str, **headers: str) -> dict:
    return {"status": 200, "headers": {"Content-Type": "application/json", **headers}, "body_file": f"bodies/{body}"}


def fail(status: int, body: str | None, **headers: str) -> dict:
    r: dict = {"status": status, "headers": {"Content-Type": "application/json" if body else "text/plain", **headers}}
    if body:
        r["body_file"] = f"bodies/{body}"
    else:
        r["body"] = "upstream connect error"
    return r


def fc(args: dict | None = None) -> dict:
    return {"operation": "getLocationForecast", "args": {**FC_CALL["args"], **(args or {})}}


CASES: list[dict] = [
    # --- requests: paths, auth, units, User-Agent ---
    {
        "name": "request/anonymous-location-forecast",
        "description": "A client with no API key calls anonymously: no X-API-Key header, no query at all (every default omitted), User-Agent names the SDK.",
        "client": {},
        "call": fc(),
        "expect_request": {
            "method": "GET",
            "path": FC_PATH,
            "query_string": "",
            "headers_absent": ["X-API-Key"],
            "headers_match": {"User-Agent": "^ensemble-weather-[a-z]+/\\d+\\.\\d+\\.\\d+(-[0-9A-Za-z.]+)? \\(.+\\)"},
        },
        "responses": [ok("forecast-metric.json", **RL)],
        "expect": {"result": {"location.slug": "mt-hood-meadows", "units": "metric", "forecast.timeseries[0].ensemble.temperature.p50": -2.0}},
    },
    {
        "name": "request/api-key-header",
        "description": "A configured key is sent as X-API-Key, and never anywhere else.",
        "client": {"api_key": "ow_test_0123456789abcdef"},
        "call": fc(),
        "expect_request": {"method": "GET", "path": FC_PATH, "headers": {"X-API-Key": "ow_test_0123456789abcdef"}, "query_absent": ["api_key", "key"]},
        "responses": [ok("forecast-metric.json")],
        "expect": {"result": {"location.slug": "mt-hood-meadows"}},
    },
    {
        "name": "request/api-key-from-environment",
        "description": "With no key passed, OUREA_API_KEY from the environment is used.",
        "client": {"env": {"OUREA_API_KEY": "ow_env_key"}},
        "call": fc(),
        "expect_request": {"method": "GET", "path": FC_PATH, "headers": {"X-API-Key": "ow_env_key"}},
        "responses": [ok("forecast-metric.json")],
        "expect": {"result": {"location.slug": "mt-hood-meadows"}},
    },
    {
        "name": "request/base-url-trailing-slash",
        "description": "A base URL with a trailing slash and a path prefix joins without a double slash.",
        "client": {"base_url": "https://proxy.example.test/ourea/"},
        "call": fc(),
        "expect_request": {"method": "GET", "url_prefix": "https://proxy.example.test/ourea/api/v1/", "path": "/ourea" + FC_PATH},
        "responses": [ok("forecast-metric.json")],
        "expect": {"result": {"location.slug": "mt-hood-meadows"}},
    },
    {
        "name": "request/imperial-units",
        "description": "units=imperial is sent, and the result reports imperial.",
        "client": {},
        "call": fc({"units": "imperial"}),
        "expect_request": {"method": "GET", "path": FC_PATH, "query_string": "units=imperial"},
        "responses": [ok("forecast-imperial.json")],
        "expect": {"result": {"units": "imperial", "forecast.timeseries[0].ensemble.temperature.p50": 28.4}},
    },
    {
        "name": "request/path-segments-encoded",
        "description": "State and slug are separate, percent-encoded path segments; a combined 'state/slug' string is split on its one slash.",
        "client": {},
        "call": {"operation": "getLocationForecast", "args": {"location": "or/a b&c"}},
        "expect_request": {"method": "GET", "path": "/api/v1/locations/or/a%20b%26c"},
        "responses": [fail(404, "error-not-found.json")],
        "expect": {"error": {"category": "not_found", "code": "LOCATION_NOT_FOUND", "status": 404}},
    },
    {
        "name": "request/point-forecast",
        "description": "Coordinates and elevation go in the query; the key is required server-side (Pro).",
        "client": {"api_key": "ow_pro"},
        "call": {"operation": "getPointForecast", "args": {"lat": 45.3311, "lon": -121.6649, "elevation_m": 1661, "max_hours": 48}},
        "expect_request": {"method": "GET", "path": "/api/v1/forecast", "query_string": "elevation_m=1661&lat=45.3311&lon=-121.6649&max_hours=48"},
        "responses": [ok("forecast-metric.json")],
        "expect": {"result": {"location.slug": "mt-hood-meadows"}},
    },
    # --- probabilities ---
    {
        "name": "prob/three-terms-imperial",
        "description": "Terms are sent in canonical order (sorted; default aggregation omitted; imperial amounts at 3 decimals, temperature at 1) with literal ':' and ','. The server answers in the order sent; results come back in the CALLER's order with their reference class. A null probability stays absent, never 0.",
        "client": {},
        "call": fc(
            {
                "units": "imperial",
                "prob": [
                    {"variable": "snowfall", "op": "ge", "threshold": {"value": 6, "unit": "in"}, "window": {"hours": 24}},
                    {"variable": "temperature", "op": "le", "threshold": {"value": 32, "unit": "degF"}, "window": {"hours": 12}, "aggregation": "any"},
                    {"variable": "snowfall", "op": "ge", "threshold": {"value": 12, "unit": "in"}, "window": {"hours": 240}},
                ],
            }
        ),
        "expect_request": {"method": "GET", "path": FC_PATH, "query_string": "prob=snowfall:ge:6.000:24h,snowfall:ge:12.000:240h,temperature:le:32.0:12h&units=imperial"},
        "responses": [ok("forecast-prob-snow.json")],
        "expect": {
            "result": {
                "probabilities[0].probability": 0.42,
                "probabilities[0].variable": "snowfall",
                "probabilities[0].op": "ge",
                "probabilities[0].threshold": 6,
                "probabilities[0].window_end_hours": 24,
                "probabilities[0].members": 131,
                "probabilities[1].probability": 0.97,
                "probabilities[2].probability": None,
            }
        },
    },
    {
        "name": "prob/threshold-converted-to-request-units",
        "description": "A 6 in threshold on a metric request is sent as 152.40 (mm, 2 decimals), using 1 in = 25.4 mm exactly; the window is sent even at its 24 h default.",
        "client": {},
        "call": fc({"prob": [{"variable": "snowfall", "op": "ge", "threshold": {"value": 6, "unit": "in"}}]}),
        "expect_request": {"method": "GET", "path": FC_PATH, "query_string": "prob=snowfall:ge:152.40:24h"},
        "responses": [ok("forecast-metric.json")],
        "expect": {"result": {"location.slug": "mt-hood-meadows"}},
    },
    {
        "name": "prob/temperature-fahrenheit-on-metric",
        "description": "32 degF on a metric request is sent as 0.0 (degC); a window not starting at 0 is A-Bh; a non-default aggregation is kept.",
        "client": {},
        "call": fc({"prob": [{"variable": "temperature", "op": "le", "threshold": {"value": 32, "unit": "degF"}, "window": {"start_hours": 6, "end_hours": 18}, "aggregation": "all"}]}),
        "expect_request": {"method": "GET", "path": FC_PATH, "query_string": "prob=temperature:le:0.0:6-18h:all"},
        "responses": [ok("forecast-metric.json")],
        "expect": {"result": {"location.slug": "mt-hood-meadows"}},
    },
    {
        "name": "prob/invalid-aggregation",
        "description": "'any' on a precipitation term is refused before any request is sent.",
        "client": {},
        "call": fc({"prob": [{"variable": "precipitation", "op": "ge", "threshold": {"value": 10, "unit": "mm"}, "aggregation": "any"}]}),
        "expect_request": None,
        "responses": [],
        "expect": {"error": {"category": "usage"}, "requests": 0},
    },
    # --- window totals ---
    {
        "name": "totals/precip-and-snow",
        "description": "totals are sent sorted (precipitation before snowfall); results come back in the caller's order; an uncovered window has null quantiles, surfaced as absent.",
        "client": {},
        "call": fc({"totals": [{"variable": "snowfall", "window": {"hours": 240}}, {"variable": "precipitation", "window": {"hours": 48}}]}),
        "expect_request": {"method": "GET", "path": FC_PATH, "query_string": "totals=precipitation:48h,snowfall:240h"},
        "responses": [ok("forecast-totals.json")],
        "expect": {
            "result": {
                "window_totals[0].variable": "snowfall",
                "window_totals[0].quantiles": None,
                "window_totals[1].quantiles.p10": 12.0,
                "window_totals[1].quantiles.p90": 52.0,
                "window_totals[1].members": 131,
            }
        },
    },
    # --- forward compatibility ---
    {
        "name": "compat/unknown-fields-and-enums",
        "description": "Unknown fields are ignored; an unknown enum value parses to the 'unknown' case and keeps its raw string.",
        "client": {},
        "call": fc(),
        "expect_request": {"method": "GET", "path": FC_PATH},
        "responses": [ok("forecast-unknown-fields.json")],
        "expect": {"result": {"location.slug": "mt-hood-meadows", "location.type": {"unknown": "a_location_type_added_later"}}},
    },
    # --- errors ---
    *[
        {
            "name": f"error/{name}",
            "description": desc,
            "client": {},
            "call": call,
            "expect_request": {"method": "GET"},
            "responses": [fail(status, body)],
            "expect": {"error": {"category": cat, "code": code, "status": status}, "requests": 1},
        }
        for name, desc, call, status, body, cat, code in [
            ("outside-coverage", "OUTSIDE_COVERAGE maps by code, not status.", {"operation": "getPointForecast", "args": {"lat": 45.0, "lon": 10.0}}, 404, "error-outside-coverage.json", "outside_coverage", "OUTSIDE_COVERAGE"),
            ("pro-required", "PRO_REQUIRED is a permission error.", {"operation": "getPointForecast", "args": {"lat": 45.3, "lon": -121.7}}, 403, "error-pro-required.json", "permission", "PRO_REQUIRED"),
            ("invalid-key", "INVALID_API_KEY is an authentication error, not retried.", fc(), 401, "error-invalid-key.json", "authentication", "INVALID_API_KEY"),
            ("bad-request", "BAD_REQUEST is an invalid-request error.", fc(), 400, "error-bad-request.json", "invalid_request", "BAD_REQUEST"),
            ("unknown-code-falls-back-to-status", "An unknown code keeps its string and maps by status.", fc(), 404, "error-unknown-code.json", "not_found", "A_CODE_ADDED_LATER"),
            ("non-json-body", "A non-JSON 500 body still produces a typed error, by status, with no code.", fc(), 500, None, "unavailable", None),
        ]
    ],
    {
        "name": "error/api-key-never-in-message",
        "description": "The key does not appear in the error's message or string form.",
        "client": {"api_key": "ow_secret_do_not_print"},
        "call": fc(),
        "expect_request": {"method": "GET"},
        "responses": [fail(401, "error-invalid-key.json")],
        "expect": {"error": {"category": "authentication", "code": "INVALID_API_KEY", "status": 401, "string_excludes": "ow_secret_do_not_print"}},
    },
    # --- retries ---
    {
        "name": "retry/503-then-ok",
        "description": "503 without Retry-After is retried with full-jitter backoff (jitter seeded to its upper bound: 0.5 s).",
        "client": {},
        "call": fc(),
        "expect_request": {"method": "GET"},
        "responses": [fail(503, "error-unavailable.json"), ok("forecast-metric.json")],
        "expect": {"result": {"location.slug": "mt-hood-meadows"}, "requests": 2, "delays_s": [0.5]},
    },
    {
        "name": "retry/429-honours-retry-after",
        "description": "429 with Retry-After: 3 waits exactly 3 s.",
        "client": {},
        "call": fc(),
        "expect_request": {"method": "GET"},
        "responses": [fail(429, "error-rate-limited.json", **{"Retry-After": "3"}), ok("forecast-metric.json", **RL)],
        "expect": {"result": {"location.slug": "mt-hood-meadows", "rate_limit.remaining": 59, "rate_limit.limit": 60}, "requests": 2, "delays_s": [3]},
    },
    {
        "name": "retry/429-retry-after-too-long",
        "description": "Retry-After over 60 s is not waited out: the error is returned with retry_after set.",
        "client": {},
        "call": fc(),
        "expect_request": {"method": "GET"},
        "responses": [fail(429, "error-rate-limited.json", **{"Retry-After": "3600"})],
        "expect": {"error": {"category": "rate_limited", "code": "TOO_MANY_REQUESTS", "status": 429, "retry_after": 3600}, "requests": 1, "delays_s": []},
    },
    {
        "name": "retry/exhausted",
        "description": "Default max_retries = 2: three attempts, backoff 0.5 s then 1 s, then the last error is returned.",
        "client": {},
        "call": fc(),
        "expect_request": {"method": "GET"},
        "responses": [fail(502, None), fail(502, None), fail(502, None)],
        "expect": {"error": {"category": "unavailable", "status": 502}, "requests": 3, "delays_s": [0.5, 1.0]},
    },
    {
        "name": "retry/disabled",
        "description": "max_retries = 0 makes exactly one attempt.",
        "client": {"max_retries": 0},
        "call": fc(),
        "expect_request": {"method": "GET"},
        "responses": [fail(503, "error-unavailable.json")],
        "expect": {"error": {"category": "unavailable", "code": "FORECAST_UNAVAILABLE", "status": 503}, "requests": 1, "delays_s": []},
    },
    {
        "name": "retry/4xx-not-retried",
        "description": "A 400 is never retried.",
        "client": {},
        "call": fc(),
        "expect_request": {"method": "GET"},
        "responses": [fail(400, "error-bad-request.json")],
        "expect": {"error": {"category": "invalid_request", "code": "BAD_REQUEST", "status": 400}, "requests": 1, "delays_s": []},
    },
    # --- caching ---
    {
        "name": "cache/etag-revalidates",
        "description": "The cache is on by default: a repeated call sends If-None-Match and a 304 returns the cached body.",
        "client": {},
        "calls": [fc(), fc()],
        "expect_requests": [
            {"method": "GET", "path": FC_PATH, "headers_absent": ["If-None-Match"]},
            {"method": "GET", "path": FC_PATH, "headers": {"If-None-Match": '"v1-abc"'}},
        ],
        "responses": [ok("forecast-metric.json", ETag='"v1-abc"', **{"Cache-Control": "private, max-age=0"}), {"status": 304, "headers": {"ETag": '"v1-abc"'}}],
        "expect": {"results": [{"location.slug": "mt-hood-meadows"}, {"location.slug": "mt-hood-meadows", "revalidated": True}], "requests": 2},
    },
    {
        "name": "cache/disabled",
        "description": "With the cache disabled, a repeated call never sends If-None-Match.",
        "client": {"cache": False},
        "calls": [fc(), fc()],
        "expect_requests": [
            {"method": "GET", "headers_absent": ["If-None-Match"]},
            {"method": "GET", "headers_absent": ["If-None-Match"]},
        ],
        "responses": [ok("forecast-metric.json", ETag='"v1-abc"'), ok("forecast-metric.json", ETag='"v1-abc"')],
        "expect": {"requests": 2},
    },
    # --- deprecation ---
    {
        "name": "deprecation/warns-once",
        "description": "Deprecation/Sunset headers raise one warning per operation per process, with the Link URL.",
        "client": {},
        "calls": [fc(), fc()],
        "expect_requests": [{"method": "GET"}, {"method": "GET"}],
        "responses": [
            ok("forecast-metric.json", Deprecation="@1798761600", Sunset="Wed, 01 Dec 2027 00:00:00 GMT", Link='<https://docs.oureawx.com/changelog#v1-deprecations>; rel="deprecation"'),
            ok("forecast-metric.json", Deprecation="@1798761600", Sunset="Wed, 01 Dec 2027 00:00:00 GMT", Link='<https://docs.oureawx.com/changelog#v1-deprecations>; rel="deprecation"'),
        ],
        "expect": {"warnings": [{"contains": "https://docs.oureawx.com/changelog#v1-deprecations"}], "requests": 2},
    },
    # --- paging ---
    {
        "name": "paging/iterator-follows-cursor",
        "description": "The lazy iterator follows next_cursor until it is null.",
        "client": {},
        "call": {"operation": "listCatalogLocations", "args": {"iterate": True}},
        "expect_requests": [
            {"method": "GET", "path": "/api/v1/catalog/locations", "query_absent": ["cursor"]},
            {"method": "GET", "path": "/api/v1/catalog/locations", "query": {"cursor": "c2"}},
        ],
        "responses": [ok("catalog-page-1.json"), ok("catalog-page-2.json")],
        "expect": {"items": ["mt-hood-meadows", "timberline-lodge"], "requests": 2},
    },
    {
        "name": "search/basic",
        "description": "search sends q and returns typed hits.",
        "client": {},
        "call": {"operation": "searchLocations", "args": {"q": "hood meadows"}},
        "expect_request": {"method": "GET", "path": "/api/v1/search/locations", "query": {"q": "hood meadows"}},
        "responses": [ok("search.json")],
        "expect": {"result": {"count": 1, "items[0].slug": "mt-hood-meadows", "items[0].county": "Hood River"}},
    },
    # --- canonical URLs: one request, one edge-cache entry (BEHAVIOR.md 3.1) ---
    {
        "name": "canonical/defaults-omitted",
        "description": "Parameters set explicitly to their defaults are not sent; the state is lowercased.",
        "client": {},
        "call": {"operation": "getLocationForecast", "args": {"state": "OR", "slug": "mt-hood-meadows", "units": "metric", "max_hours": 24, "nowcast": True, "daily": True, "hourly": True, "include_past": False, "members": False, "models": False}},
        "expect_request": {"method": "GET", "path": FC_PATH, "query_string": ""},
        "responses": [ok("forecast-metric.json")],
        "expect": {"result": {"location.slug": "mt-hood-meadows"}},
    },
    {
        "name": "canonical/alphabetical-order",
        "description": "Non-default parameters are sent in alphabetical order by name; booleans as true/false.",
        "client": {},
        "call": fc({"units": "imperial", "members": True, "max_hours": 72, "nowcast": False, "include_past": True}),
        "expect_request": {"method": "GET", "path": FC_PATH, "query_string": "include_past=true&max_hours=72&members=true&nowcast=false&units=imperial"},
        "responses": [ok("forecast-imperial.json")],
        "expect": {"result": {"units": "imperial"}},
    },
    {
        "name": "canonical/prob-dedup-sort-precision",
        "description": "Duplicate terms are sent once; ge sorts before le; a window starting later sorts after; snow_level has 0 decimals, wind 1; negative thresholds keep their sign; results map back to the caller's order (duplicates share one result).",
        "client": {},
        "call": fc(
            {
                "prob": [
                    {"variable": "wind_speed", "op": "ge", "threshold": {"value": 15, "unit": "m/s"}, "window": {"start_hours": 12, "end_hours": 36}},
                    {"variable": "snow_level", "op": "le", "threshold": {"value": 1524.4, "unit": "m"}},
                    {"variable": "wind_speed", "op": "ge", "threshold": {"value": 15, "unit": "m/s"}},
                    {"variable": "temperature", "op": "le", "threshold": {"value": -5, "unit": "degC"}},
                    {"variable": "temperature", "op": "ge", "threshold": {"value": -5, "unit": "degC"}},
                    {"variable": "snow_level", "op": "le", "threshold": {"value": 1524.4, "unit": "m"}},
                ]
            }
        ),
        "expect_request": {"method": "GET", "path": FC_PATH, "query_string": "prob=snow_level:le:1524:24h,temperature:ge:-5.0:24h,temperature:le:-5.0:24h,wind_speed:ge:15.0:24h,wind_speed:ge:15.0:12-36h"},
        "responses": [ok("forecast-prob-mixed.json")],
        "expect": {
            "result": {
                "probabilities[0].probability": 0.11,
                "probabilities[0].window_start_hours": 12,
                "probabilities[1].probability": 0.8,
                "probabilities[1].threshold": 1524,
                "probabilities[2].probability": 0.05,
                "probabilities[3].probability": 0.3,
                "probabilities[4].probability": 0.7,
                "probabilities[5].probability": 0.8,
            }
        },
    },
    {
        "name": "canonical/threshold-rounding",
        "description": "Rounding is round-half-away-from-zero on (v * 10^d) in doubles: 0.0625 in -> 0.063 (banker's rounding would give 0.062), and 1.005 mm -> 1.00 (1.005 * 100 = 100.4999...).",
        "client": {},
        "calls": [
            fc({"units": "imperial", "prob": [{"variable": "precipitation", "op": "ge", "threshold": {"value": 0.0625, "unit": "in"}}]}),
            fc({"prob": [{"variable": "precipitation", "op": "ge", "threshold": {"value": 1.005, "unit": "mm"}}]}),
        ],
        "expect_requests": [
            {"method": "GET", "path": FC_PATH, "query_string": "prob=precipitation:ge:0.063:24h&units=imperial"},
            {"method": "GET", "path": FC_PATH, "query_string": "prob=precipitation:ge:1.00:24h"},
        ],
        "responses": [ok("forecast-imperial.json"), ok("forecast-metric.json")],
        "expect": {"requests": 2},
    },
    {
        "name": "canonical/value-encoding",
        "description": "Query values use RFC 3986 percent-encoding (space as %20, never +; uppercase hex); prob/totals keep ':' and ',' literal.",
        "client": {},
        "call": {"operation": "searchLocations", "args": {"q": "Mt. Hood & co/ñ"}},
        "expect_request": {"method": "GET", "path": "/api/v1/search/locations", "query_string": "q=Mt.%20Hood%20%26%20co%2F%C3%B1"},
        "responses": [ok("search.json")],
        "expect": {"result": {"count": 1}},
    },
    # --- credentials on open routes (BEHAVIOR.md 3.2) ---
    {
        "name": "credentials/open-routes-keyless",
        "description": "With a key configured, search, catalog detail and attribution are sent WITHOUT X-API-Key (edge-cacheable); catalog list pages and forecasts keep it.",
        "client": {"api_key": "ow_pro"},
        "calls": [
            {"operation": "searchLocations", "args": {"q": "hood"}},
            {"operation": "getCatalogLocation", "args": {"slug": "mt-hood-meadows"}},
            {"operation": "getAttribution", "args": {}},
            {"operation": "listCatalogLocations", "args": {}},
            fc(),
        ],
        "expect_requests": [
            {"method": "GET", "path": "/api/v1/search/locations", "headers_absent": ["X-API-Key"]},
            {"method": "GET", "path": "/api/v1/catalog/locations/mt-hood-meadows", "headers_absent": ["X-API-Key"]},
            {"method": "GET", "path": "/api/v1/attribution", "headers_absent": ["X-API-Key"]},
            {"method": "GET", "path": "/api/v1/catalog/locations", "headers": {"X-API-Key": "ow_pro"}},
            {"method": "GET", "path": FC_PATH, "headers": {"X-API-Key": "ow_pro"}},
        ],
        "responses": [ok("search.json"), ok("catalog-detail.json"), ok("attribution.json"), ok("catalog-page-2.json"), ok("forecast-metric.json")],
        "expect": {"requests": 5},
    },
    {
        "name": "credentials/send-key-everywhere-option",
        "description": "send_key_on_open_routes = true sends the key on open routes too.",
        "client": {"api_key": "ow_pro", "send_key_on_open_routes": True},
        "call": {"operation": "searchLocations", "args": {"q": "hood"}},
        "expect_request": {"method": "GET", "path": "/api/v1/search/locations", "headers": {"X-API-Key": "ow_pro"}},
        "responses": [ok("search.json")],
        "expect": {"result": {"count": 1}},
    },
    # --- redirects (BEHAVIOR.md 3.3) ---
    {
        "name": "redirect/follows-same-host",
        "description": "A 301 on the same host is followed, keeping the key.",
        "client": {"api_key": "ow_pro"},
        "call": {"operation": "getLocationForecast", "args": {"state": "oregon", "slug": "mt-hood-meadows"}},
        "expect_requests": [
            {"method": "GET", "path": "/api/v1/locations/oregon/mt-hood-meadows", "headers": {"X-API-Key": "ow_pro"}},
            {"method": "GET", "path": FC_PATH, "headers": {"X-API-Key": "ow_pro"}},
        ],
        "responses": [{"status": 301, "headers": {"Location": FC_PATH, "Cache-Control": "public, max-age=3600, s-maxage=3600"}}, ok("forecast-metric.json")],
        "expect": {"result": {"location.slug": "mt-hood-meadows"}, "requests": 2},
    },
    {
        "name": "redirect/cross-host-drops-key",
        "description": "A redirect to another host is followed without the API key.",
        "client": {"api_key": "ow_secret"},
        "call": fc(),
        "expect_requests": [
            {"method": "GET", "path": FC_PATH, "headers": {"X-API-Key": "ow_secret"}},
            {"method": "GET", "url_prefix": "https://elsewhere.example.test/", "headers_absent": ["X-API-Key"]},
        ],
        "responses": [{"status": 302, "headers": {"Location": "https://elsewhere.example.test" + FC_PATH}}, ok("forecast-metric.json")],
        "expect": {"result": {"location.slug": "mt-hood-meadows"}, "requests": 2},
    },
    # --- more caching (BEHAVIOR.md 10) ---
    {
        "name": "cache/etag-sent-verbatim",
        "description": "A weak ETag (as Cloudflare sends after compressing) is sent back byte for byte, W/ included.",
        "client": {},
        "calls": [fc(), fc()],
        "expect_requests": [
            {"method": "GET", "headers_absent": ["If-None-Match"]},
            {"method": "GET", "headers": {"If-None-Match": 'W/"v1-abc"'}},
        ],
        "responses": [ok("forecast-metric.json", ETag='W/"v1-abc"'), {"status": 304, "headers": {"ETag": 'W/"v1-abc"'}}],
        "expect": {"results": [{"revalidated": False}, {"revalidated": True, "location.slug": "mt-hood-meadows"}], "requests": 2},
    },
    {
        "name": "cache/no-store-not-stored",
        "description": "A no-store response is never cached, so the next call sends no If-None-Match.",
        "client": {},
        "calls": [fc(), fc()],
        "expect_requests": [
            {"method": "GET", "headers_absent": ["If-None-Match"]},
            {"method": "GET", "headers_absent": ["If-None-Match"]},
        ],
        "responses": [ok("forecast-metric.json", ETag='"v1-abc"', **{"Cache-Control": "no-store"}), ok("forecast-metric.json")],
        "expect": {"requests": 2},
    },
    {
        "name": "cache/keys-never-mix",
        "description": "An entry stored under one API key is never revalidated or served under another (or keyless).",
        "client": {"api_key": "ow_a"},
        "calls": [fc(), {"operation": "getLocationForecast", "args": {"state": "or", "slug": "mt-hood-meadows"}, "with_api_key": "ow_b"}],
        "expect_requests": [
            {"method": "GET", "headers": {"X-API-Key": "ow_a"}, "headers_absent": ["If-None-Match"]},
            {"method": "GET", "headers": {"X-API-Key": "ow_b"}, "headers_absent": ["If-None-Match"]},
        ],
        "responses": [ok("forecast-metric.json", ETag='"v1-abc"'), ok("forecast-metric.json", ETag='"v1-abc"')],
        "expect": {"requests": 2},
    },
]


def render() -> dict[Path, str]:
    files: dict[Path, str] = {}
    for name, body in BODIES.items():
        files[OUT / "bodies" / name] = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
    for case in CASES:
        files[OUT / f"{case['name']}.json"] = json.dumps(case, indent=2, ensure_ascii=False) + "\n"
    return files


def main() -> int:
    files = render()
    if "--check" in sys.argv:
        stale = [p for p, text in files.items() if not p.exists() or p.read_text() != text]
        extra = [p for p in OUT.rglob("*.json") if p not in files]
        for p in stale + extra:
            print(f"out of date: {p.relative_to(ROOT)}", file=sys.stderr)
        return 1 if stale or extra else 0
    for p, text in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    print(f"wrote {len(CASES)} vectors and {len(BODIES)} bodies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
