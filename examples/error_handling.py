"""Catching errors by category or code, and reading the rate-limit state."""

from ensemble_weather import (
    APIError,
    Client,
    NotFoundError,
    OutsideCoverageError,
    PermissionDeniedError,
    RateLimitError,
)

with Client() as client:
    # Coordinates outside the forecast domain (CONUS).
    try:
        client.forecast_at(45.0, 10.0)
    except OutsideCoverageError as err:
        print(f"outside coverage: {err.code}: {err.message}")
    except PermissionDeniedError as err:  # no Pro key: PRO_REQUIRED comes first
        print(f"needs Pro: {err.code}: {err.message}")

    # Any API error carries the status, the code (verbatim) and a request id.
    try:
        client.forecast("or/no-such-place")
    except NotFoundError as err:
        print(f"{err.status} {err.code}: {err.message} (request id {err.request_id})")
    except RateLimitError as err:
        print(f"rate limited; retry after {err.retry_after} s")
    except APIError as err:
        print(f"API error {err.status} {err.code}")

    # Rate-limit state is what the server reported on the last response. It
    # is absent on anonymous responses the edge may share between callers.
    forecast = client.forecast("or/mt-hood-meadows")
    limit = forecast.rate_limit or client.rate_limit
    if limit is None:
        print("rate limit: not reported on this (edge-cacheable) response")
    else:
        print(f"rate limit: {limit.remaining} of {limit.limit} left, resets in {limit.reset} s")
