"""A tiny local stand-in for the API, so the examples run without network or key.

It serves the shared vector bodies (``spec/vectors/bodies``) and answers
``prob=`` / ``totals=`` with placeholder values (it is a test double, not a
forecast). Run it by hand with::

    uv run python tests/stub_server.py   # prints the base URL to export
    OUREA_BASE_URL=http://127.0.0.1:<port> uv run python examples/quickstart.py
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

BODIES = Path(__file__).resolve().parent.parent / "spec" / "vectors" / "bodies"
START = "2026-11-15T00:00:00Z"


def _body(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((BODIES / name).read_text(encoding="utf-8"))
    return data


def _hours_after(hours: int) -> str:
    day, hour = divmod(hours, 24)
    return f"2026-11-{15 + day:02d}T{hour:02d}:00:00Z"


def _window(text: str) -> tuple[int, int]:
    span = text.removesuffix("h")
    if "-" in span:
        start, end = span.split("-")
        return int(start), int(end)
    return 0, int(span)


def _probabilities(spec: str) -> list[dict[str, Any]]:
    out = []
    for term in spec.split(","):
        parts = term.split(":")
        variable, op, threshold, window = parts[:4]
        amounts = variable in {"precipitation", "snowfall"}
        aggregation = parts[4] if len(parts) > 4 else ("total" if amounts else "any")
        start, end = _window(window)
        out.append(
            {
                "variable": variable,
                "op": op,
                "threshold": float(threshold),
                "window_start_hours": start,
                "window_end_hours": end,
                "aggregation": aggregation,
                "from": _hours_after(start),
                "to": _hours_after(end),
                "probability": 0.42,
                "members": 131,
            }
        )
    return out


def _totals(spec: str) -> list[dict[str, Any]]:
    out = []
    for item in spec.split(","):
        variable, window = item.split(":")
        start, end = _window(window)
        out.append(
            {
                "variable": variable,
                "window_start_hours": start,
                "window_end_hours": end,
                "from": _hours_after(start),
                "to": _hours_after(end),
                "quantiles": {
                    "mean": 31.0,
                    "p10": 12.0,
                    "p25": 20.0,
                    "p50": 29.0,
                    "p75": 40.0,
                    "p90": 52.0,
                },
                "members": 131,
            }
        )
    return out


def _alert() -> dict[str, Any]:
    return {
        "id": "urn:oid:2.49.0.1.840.0.example",
        "event": "Winter Storm Warning",
        "severity": "Severe",
        "urgency": "Expected",
        "headline": "Winter Storm Warning until Sunday 4 AM PST",
        "onset": START,
        "expires": "2026-11-16T12:00:00Z",
    }


def _current(location: dict[str, Any]) -> dict[str, Any]:
    forecast = _body("forecast-metric.json")
    return {
        "location": location,
        "alerts": [_alert()],
        "alerts_as_of": START,
        "sensor_count": 0,
        "sensors": [],
        "current": {
            "time": START,
            "temperature": -2.0,
            "condition": "snow",
            "condition_text": "Snow",
            "condition_icon": "night_snow",
            "wind_speed": 6.0,
            "wind_direction": 5.0,
            "source": "nowcast",
        },
        "as_of": START,
        "model_run_initialized_at": START,
        "nowcast_hours": None,
        "units": "metric",
        "attribution": forecast["attribution"],
    }


def _error(code: str, message: str) -> dict[str, Any]:
    return {"error": code, "message": message}


def route(path: str, query: dict[str, str], keyed: bool) -> tuple[int, dict[str, Any]]:
    """Answer one GET request: (status, JSON body)."""
    location = _body("forecast-metric.json")["location"]
    parts = [unquote(p) for p in path.split("/") if p][2:]  # drop "api", "v1"
    if parts[:1] == ["locations"] and len(parts) == 3:
        if parts[1:] != ["or", "mt-hood-meadows"]:
            return 404, _error("LOCATION_NOT_FOUND", f"No location {parts[1]}/{parts[2]}.")
        return 200, _forecast(query)
    if parts[:1] == ["locations"] and len(parts) == 4:
        if parts[3] == "current":
            return 200, _current(location)
        if parts[3] == "alerts":
            return 200, {
                "location": location,
                "alert_count": 1,
                "as_of": START,
                "alerts": [_alert()],
                "attribution": _body("forecast-metric.json")["attribution"],
            }
    if parts == ["forecast"]:
        if not keyed:
            return 403, _body("error-pro-required.json")
        if float(query["lon"]) > -60:
            return 400, _body("error-outside-coverage.json")
        return 200, _forecast(query)
    if parts == ["search", "locations"]:
        return 200, _body("search.json")
    if parts == ["catalog", "locations"]:
        page = "catalog-page-2.json" if query.get("cursor") else "catalog-page-1.json"
        return 200, _body(page)
    if parts == ["attribution"]:
        return 200, _body("attribution.json")
    return 404, _error("NOT_FOUND", f"No route {path}.")


def _forecast(query: dict[str, str]) -> dict[str, Any]:
    imperial = query.get("units") == "imperial"
    body = _body("forecast-imperial.json" if imperial else "forecast-metric.json")
    if "prob" in query:
        body["probabilities"] = _probabilities(query["prob"])
    if "totals" in query:
        body["window_totals"] = _totals(query["totals"])
    return body


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlsplit(self.path)
        query = dict(parse_qsl(url.query, keep_blank_values=True))
        keyed = "X-API-Key" in self.headers
        status, body = route(url.path, query, keyed)
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        if keyed:
            self.send_header("Cache-Control", "private, max-age=0")
            self.send_header("RateLimit-Limit", "60")
            self.send_header("RateLimit-Remaining", "59")
            self.send_header("RateLimit-Reset", "1")
            self.send_header("RateLimit-Policy", "60;w=60")
        else:
            self.send_header("Cache-Control", "public, max-age=0, s-maxage=60")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        """Keep test output quiet."""


class StubServer:
    """The stub on a free local port, in a background thread."""

    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host!s}:{port}"

    def __enter__(self) -> StubServer:  # noqa: PYI034
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()


if __name__ == "__main__":
    with StubServer() as stub:
        print(f"export OUREA_BASE_URL={stub.url}", flush=True)
        threading.Event().wait()
