# Errors, retries and caching

## Errors

| Exception | When |
|---|---|
| `AuthenticationError` | `INVALID_API_KEY`, `UNAUTHORIZED`, or 401 |
| `PermissionDeniedError` | `PRO_REQUIRED`, or 403 |
| `NotFoundError` | `LOCATION_NOT_FOUND`, `NOT_FOUND`, or 404/410 |
| `InvalidRequestError` | `BAD_REQUEST`, `INVALID_COORDINATES`, `INVALID_ELEVATION`, `ELEVATION_REQUIRED`, or 400 |
| `OutsideCoverageError` | `OUTSIDE_COVERAGE` (a 404) |
| `RateLimitError` | `TOO_MANY_REQUESTS`, or 429 |
| `UnavailableError` | `FORECAST_UNAVAILABLE`, `TIMEOUT`, `INTERNAL_ERROR`, `DATABASE_ERROR`, `AUTH_UNAVAILABLE`, or 5xx |
| `APIError` | any other error status |
| `APIConnectionError` | no response: DNS, TLS, reset, timeout |
| `UsageError` | refused before sending (also a `ValueError`) |
| `UnexpectedResponseError` | a 2xx body that is not the documented model, or over 64 MiB |

All derive from `OureaError`. `APIError` carries `status`, `code` (verbatim,
even when this SDK does not know it), `message`, `request_id` (the body's,
else the `X-Request-Id` header), `doc_url`, `param` (the query parameter a
400 is about, when it names one), `retry_after` and `rate_limit`. The code is
matched first, then the status, so a code this SDK does not know still lands
in the right category.

A `PRO_REQUIRED` refusal of a coordinate request carries `nearest_location`
on the `PermissionDeniedError` when a named location is close enough (within
10 km and 300 m of elevation): its forecast answers without a key.

## Retries

Connection errors (except TLS verification failures), 429, 502, 503 and 504
are retried up to `max_retries` (default 2). After a 429, 503 or 504 with
`Retry-After` (the API sends it on every 503 and 504) the SDK waits exactly that long, up to 60 s; over 60 s it raises
the error with `retry_after` set instead. Otherwise the delay is full jitter,
`random() × min(8, 0.5 × 2^(n-1))` seconds.

## Rate limits

`result.rate_limit` and `client.rate_limit` hold what the server reported
(`RateLimit-Limit`, `-Remaining`, `-Reset`, `-Policy`). They are `None` on
anonymous responses the edge may share between callers.

## Caching

On by default: an in-memory LRU of 256 entries / 32 MiB, keyed by the URL and
a hash of the key. Each call revalidates with `If-None-Match`; a `304` returns
the stored body with `result.revalidated` set. `no-store` responses are never
stored; `s-maxage` and `stale-while-revalidate` are for the edge and ignored.
Pass `cache=False`, or any object implementing
[`Cache`][ensemble_weather.Cache].

## Deprecations

A response with `Deprecation` or `Sunset` emits one
`OureaDeprecationWarning` (a `FutureWarning`) per operation per process, with
the `Link rel="deprecation"` URL.
