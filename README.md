# ensemble-weather

Official Python SDK for the [Ourea](https://oureawx.com) probabilistic weather API.

[![CI](https://github.com/Ourea-Technologies/ensemble-weather-python/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Ourea-Technologies/ensemble-weather-python/actions/workflows/ci.yml)
[![Security](https://github.com/Ourea-Technologies/ensemble-weather-python/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/Ourea-Technologies/ensemble-weather-python/actions/workflows/security.yml)
[![PyPI](https://img.shields.io/pypi/v/ensemble-weather)](https://pypi.org/project/ensemble-weather/)
[![Python versions](https://img.shields.io/pypi/pyversions/ensemble-weather)](https://pypi.org/project/ensemble-weather/)
[![Licence: BSD-2-Clause](https://img.shields.io/badge/licence-BSD--2--Clause-blue)](LICENSE)
[![Docs](https://readthedocs.org/projects/ensemble-weather/badge/?version=latest)](https://ensemble-weather.readthedocs.io)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Ourea-Technologies/ensemble-weather-python/badge)](https://scorecard.dev/viewer/?uri=github.com/Ourea-Technologies/ensemble-weather-python)

## Install

```sh
pip install ensemble-weather
```

## Quickstart

No signup and no API key: anonymous calls use the Free tier.

```python
from ensemble_weather import Chance, Client

with Client() as client:  # no key: anonymous calls use the Free tier
    forecast = client.forecast(
        "or/mt-hood-meadows",
        units="imperial",
        prob=[Chance.at_least("snowfall", 6, "in")],  # window: the next 24 h
    )

print(forecast.location.name)
for hour in forecast.forecast.timeseries[:24]:
    temp = hour.ensemble.temperature
    print(f"{hour.valid_time:%a %H:%M} UTC  {temp.p10} to {temp.p90} °F (p10-p90)")

snow = forecast.probabilities[0]
chance = "not available" if snow.probability is None else f"{snow.probability:.0%}"
print(f"Chance of at least 6 in of snow in the next 24 h: {chance} ({snow.members} members)")
```

This is [`examples/quickstart.py`](examples/quickstart.py); CI runs it.

## Authentication

Pass a key to the constructor, or set `OUREA_API_KEY`:

```sh
export OUREA_API_KEY=ow_...   # or: Client("ow_...")
```

- **Anonymous** (no key): forecasts, current conditions and alerts for named
  locations at the Free tier (10-day horizon, latest run, the members'
  plume view), plus search and the catalog.
- **Free key**: the same, with your own rate-limit budget.
- **Pro key**: the 15-day horizon, forecasts and current conditions at any
  coordinates (`get_point_forecast`, `get_point_current`), every member variable,
  per-model breakdowns and historical runs.

See [pricing](https://oureawx.com/pricing). The key is sent only as
`X-API-Key`, only to the API's own host, and never on the open routes
(search, catalog detail, attribution), so those share the edge cache with
everyone; pass `send_key_on_open_routes=True` to attribute every request to
your key. The key never appears in logs, errors or `repr`.

## Probabilities, not single numbers

Every forecast value is a distribution (`Quantiles`) computed by the server
from the full ensemble. Ask for a **chance** of crossing a threshold:

```python
from ensemble_weather import Chance, Client, Total, Window

client = Client()
terms = [
    Chance.at_least("snowfall", 12, "in", window=72),  # P(0-72 h snowfall >= 12 in)
    Chance.at_most("temperature", 32, "degF", window=Window(6, 18), aggregation="all"),
]
forecast = client.forecast("or/mt-hood-meadows", prob=terms)
for p in forecast.probabilities:  # in your order, each with its reference class
    print(p.variable, p.op, p.threshold, p.window, p.aggregation, p.probability, p.members)
```

For a **storm total**, ask for the window total's distribution:

```python
forecast = client.forecast("or/mt-hood-meadows", totals=[Total("snowfall", 72)])
storm = forecast.window_totals[0].quantiles  # None (see null_reason) when not covered
```

Read **quantiles** directly; `median` is the p50, not "the forecast":

```python
temp = forecast.forecast.timeseries[0].ensemble.temperature
print(temp.p10, temp.median, temp.p90, temp.range(25, 75))
```

The SDK never sums, averages or interpolates quantiles, and never derives a
probability from them: the sum of hourly medians is not the median total.
A threshold you give in another unit is converted exactly into the
request's units before sending; response values are never converted. More in
[Probabilities](https://docs.oureawx.com/concepts/probabilities).

## More examples

| Example | Shows |
|---|---|
| [`quickstart.py`](examples/quickstart.py) | the program above, anonymous |
| [`point_forecast.py`](examples/point_forecast.py) | a forecast at coordinates and an elevation (Pro key from `OUREA_API_KEY`) |
| [`chance_of_snow.py`](examples/chance_of_snow.py) | several `prob` terms in one call, with windows and member counts |
| [`storm_total.py`](examples/storm_total.py) | `totals` window distributions for precipitation and snowfall |
| [`search_and_catalog.py`](examples/search_and_catalog.py) | search, then page through the catalog with the cursor |
| [`current_and_alerts.py`](examples/current_and_alerts.py) | current conditions and active alerts for a location |
| [`error_handling.py`](examples/error_handling.py) | catching an out-of-coverage error, the keyless alternative to `PRO_REQUIRED`; reading rate-limit state |
| [`units.py`](examples/units.py) | the same forecast in metric and imperial |
| [`async_forecast.py`](examples/async_forecast.py) | `AsyncClient` with `asyncio.gather` |

## Errors, retries and rate limits

Every error derives from `OureaError`. HTTP errors are `APIError`s with
`status`, `code` (the API's string, verbatim), `message`, `request_id` and
`doc_url`, in one subclass per category: `AuthenticationError`, `PermissionDeniedError`,
`NotFoundError`, `InvalidRequestError`, `OutsideCoverageError`,
`RateLimitError` (with `retry_after`) and `UnavailableError`. With no
response at all you get `APIConnectionError`; a call refused before sending
(an invalid term, say) raises `UsageError`, which is also a `ValueError`.

```python
from ensemble_weather import OutsideCoverageError

try:
    client.get_point_forecast(45.0, 10.0)
except OutsideCoverageError as err:
    print(err.code, err.message)
```

Connection errors, 429, 502, 503 and 504 are retried up to `max_retries`
(default 2) with full-jitter backoff, honouring `Retry-After` (on 429, 503
and 504) up to 60 s.
Nothing else is retried. The rate-limit state the server reported is on
`result.rate_limit` and `client.rate_limit` (`limit`, `remaining`, `reset`,
`policy`); the SDK never hard-codes limits.

Responses are cached locally by `ETag` (in memory, 256 entries / 32 MiB) and
revalidated on every call, so an unchanged forecast costs a `304`. Pass
`cache=False` to disable it, or your own `Cache` to share one.

## Documentation

- Guides: https://docs.oureawx.com
- This SDK's guide: https://docs.oureawx.com/python
- API reference: https://ensemble-weather.readthedocs.io
- The OpenAPI contract: [ensemble-weather-spec](https://github.com/Ourea-Technologies/ensemble-weather-spec/blob/main/openapi/v1/openapi.yaml)
  (a pinned copy is in [`spec/`](spec/))

This SDK targets API contract **v1**.

## Supported versions

CPython 3.10, 3.11, 3.12, 3.13 and 3.14, tested in CI. The one runtime
dependency is [httpx](https://www.python-httpx.org/); pandas is an optional
extra (`pip install "ensemble-weather[pandas]"`) for `to_dataframe()`.

## Contributing, security, licence

- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).
- Security: report privately, as [SECURITY.md](SECURITY.md) describes.
- Licence: [BSD-2-Clause](LICENSE), Copyright (c) 2026 Ourea Technologies.
