# SDK behaviour spec (v1)

What every official ensemble-weather SDK does, whatever the language. This
document defines **semantics only**: which quantities exist, how requests are
built, and how transport, errors and caching behave. Names, structure, async
model and error style follow each language's idiom (see
[SDK-STANDARD.md](SDK-STANDARD.md)). The shared test vectors in
[`vectors/`](vectors/) are the executable form of this document: where the
two disagree, the vectors win and this document gets fixed.

The contract is [`openapi/v1/openapi.yaml`](openapi/v1/openapi.yaml)
(`info.version` 1.x).

## 1. Principles

1. **The server computes, the SDK carries.** Every probability, window total
   and range comes from the server, computed from the full ensemble. An SDK
   never sums, averages or interpolates quantiles, and never derives a
   probability from quantiles. (Summing per-hour quantiles gives a wrong
   window total, bug KAN-1044.) A helper that seems to need client math is a
   request for a new server query instead.
2. **Probabilities are the default, not an add-on.** A forecast value is a
   distribution (`Quantiles`), not a bare number. An SDK may offer a
   convenience accessor for the median, but documents it as the median, never
   as "the forecast".
3. **A probability carries its reference class.** Every probability result
   exposes its `variable`, `op`, `threshold` (with unit), window (`from`,
   `to`, and start/end hours) and `members`. Nothing returns a bare
   probability number on its own.
4. **No silent downgrades.** An unavailable answer is an error or an explicit
   null/absent value, never a substituted default.
5. **Forward compatible.** Unknown response fields are ignored. Unknown enum
   values parse to the language's "unknown/other" case and keep the raw
   string. Neither is ever an error.

## 2. Client configuration

| Setting | Default | Notes |
|---|---|---|
| API key | `OUREA_API_KEY` from the environment, else none | Sent as `X-API-Key`, except on the open routes in section 3.2. With no key, calls are anonymous (Free tier), which is valid and never an error by itself. |
| Base URL | `https://api.oureawx.com` | Overridable (tests, proxies). A trailing slash is ignored. |
| Units | `metric` | `metric`, `imperial`, `kelvin`. Sent as `units=`, on every request that accepts it. |
| Timeout | 30 s per attempt | Total including retries is bounded by `max_retries`. |
| Max retries | 2 (3 attempts in all) | 0 disables retrying. |
| Cache | on: in-memory LRU, 256 entries / 32 MiB | Section 10. Can be disabled or replaced by the caller's own store. |
| User-Agent | `ensemble-weather-<lang>/<sdk version> (<runtime>/<version>)` | e.g. `ensemble-weather-python/0.1.0 (CPython/3.12.4)`. An app may append its own product token. It never contains user data. |

The API key is never logged, never included in an error message or `repr`,
and never sent to any host other than the configured base URL (redirects to
another host drop it).

## 3. Operations

One SDK method (or idiomatic equivalent) per OpenAPI operation, except
`getMapsToken` (a web-map credential, out of SDK scope for 0.x):

| operationId | Route | Notes |
|---|---|---|
| `getLocationForecast` | `GET /api/v1/locations/{state}/{name}` | named location. Anonymous OK. |
| `getPointForecast` | `GET /api/v1/forecast` | coordinates (+ optional `elevation_m`). Pro. |
| `getCurrentConditions` / `getCurrentByCoordinates` | `.../current`, `/api/v1/current` | |
| `getLocationAlerts` / `getAlertsByCoordinates` | `.../alerts`, `/api/v1/alerts` | |
| `getNearbyLocations` / `getNearbyByCoordinates` | `.../nearby`, `/api/v1/nearby` | |
| `searchLocations` | `GET /api/v1/search/locations` | |
| `getAllLocations` / `getLocations` | `GET /api/v1/locations[/{state}]` | cursor paging |
| `listCatalogLocations` / `getCatalogLocation` | `/api/v1/catalog/locations[/{slug}]` | cursor paging |
| `listCatalogStations` / `getCatalogStation` | `/api/v1/catalog/stations[/{slug}]` | cursor paging |
| `getAvailableRuns` | `GET /api/v1/runs` | |
| `getStormReports` / `getStormReport` | `/api/v1/storm-reports[/{id}]` | |
| `getAttribution` | `GET /api/v1/attribution` | |

A named location is the pair (state, slug). An SDK may accept `"or/mt-hood-meadows"`
as one string (split on its one `/`), but it sends the two path segments
percent-encoded.

### 3.1 Canonical URLs: one request, one edge-cache entry

Cloudflare sits in front of the API and keys its cache on the **URL alone**.
Two spellings of the same request are two cache entries: each one a miss, and
on the location routes each non-canonical spelling costs a `301` round trip
(KAN-1313). So the SDK only ever sends the canonical URL:

1. **State:** lowercase USPS code (`or`). The SDK lowercases a two-letter
   code. It does not translate state names; it passes them through, and the
   server answers with a 301 (which the SDK follows, section 3.3).
2. **No parameter at its default.** A parameter the caller did not set, or set
   to the route's default, is omitted. The defaults are the OpenAPI `default`
   of each parameter (for example `units=metric`, `max_hours=24`,
   `nowcast=true`, `format=json`, `feels_like=nws`, and on nearby `limit=3`,
   `radius_km=50`). Booleans are `true`/`false`.
3. **Each parameter under its own name** (`units`, never the alias
   `unit_system`), at most once, and no parameter the route does not
   define. An unknown parameter is a `400` (KAN-1308), never ignored.
4. **Alphabetical order by parameter name.**
5. **Encoding:** each value is percent-encoded with RFC 3986 rules
   (unreserved characters `A-Z a-z 0-9 - . _ ~` as they are, everything else
   `%XX` in uppercase hex, space as `%20`, never `+`). There is one
   exception: in `prob` and `totals`, `:` and `,` are sent as literal
   characters. The language's standard query encoder usually encodes them,
   so the SDK builds those two values itself.
6. **Numbers:** the shortest decimal that round-trips, never an exponent.
   Coordinates are sent exactly as given (the SDK never rounds them).
   Thresholds follow section 4.

### 3.2 Credentials on open routes

The edge cache serves only requests that carry **no credential**. Routes that
need no credentials (`security: []` in the spec) are therefore sent **without
`X-API-Key`, even when the client has a key**, so every caller shares one edge
entry:

- keyless: `searchLocations`, `getCatalogLocation`, `getCatalogStation`,
  `getAttribution`;
- with the key: `listCatalogLocations`, `listCatalogStations` (anonymous
  list pages are capped and catalog walks are slowed per address, so a keyed
  client keeps its own budget there), and every other route.

The SDK documents this. It keeps an option to always send the key, for a
caller who needs every request attributed to the key.

### 3.3 Redirects

The SDK follows `301`, `302`, `307` and `308` on the same host (at most 5).
It drops the API key on a redirect to any other host. A 301 it followed from a
URL the SDK built itself is a bug in the SDK's canonical form; debug builds
or logs may report it.

## 4. Probabilities (`prob=`)

A probability query is built from typed terms and serialised to the wire
syntax `<variable>:<ge|le>:<threshold>:<window>[:<aggregation>]`:

- `variable`: `temperature`, `wind_speed`, `snow_level`, `precipitation`,
  `snowfall`.
- `op`: `ge` (at least) or `le` (at most).
- `threshold`: a number **in the request's units**. If the caller gives a
  threshold with an explicit unit (for example 6 inches) on a metric request,
  the SDK converts it with the exact factors in section 7. This converts the
  caller's input; it is not statistics. It is then rounded exactly as the
  server does: `r = round_half_away_from_zero(v × 10^d) / 10^d` in IEEE-754
  double arithmetic (so 1.005 at d = 2 gives 1.00, because 1.005 × 100 is
  100.49999…). Then `-0` becomes `0`, and `r` is printed with exactly `d`
  decimals. Banker's rounding (Python `round`, .NET's default
  `Math.Round`) is wrong here. `d` is the variable's served precision:

  | variable | metric / kelvin | imperial |
  |---|---|---|
  | `precipitation`, `snowfall` | 2 (mm) | 3 (in) |
  | `temperature`, `wind_speed` | 1 | 1 |
  | `snow_level` | 0 | 0 |

- `window`: always sent: `<N>h` (hours 0..N from the first served hour) or
  `<A>-<B>h` when it does not start at 0. `0-24h` is written `24h`. The
  default is 24 h, and the maximum is 360 h.
- `aggregation`: `total` (precipitation and snowfall, the only one allowed
  for them), `any` (the default for the others) or `all`. **The default is
  omitted.** The SDK refuses `any`/`all` for precipitation or snowfall, and
  `total` for the others, before sending (vector `prob/invalid-aggregation`).

**Canonical list:** the terms are de-duplicated and sorted by variable name,
then op (`ge` before `le`), then window (start, then end), then aggregation
(`total`, `any`, `all`), then threshold; they are joined by `,`. This is the
server's own order (KAN-1313), so the URL is the shared cache key.

**Results:** the server answers in the order sent, so after sorting the SDK
maps each `ProbabilityResult` back to the caller's own term by its key
(variable, op, rounded threshold, window, aggregation), and returns the results
in the caller's order (duplicates share one result). A `null` `probability`
(the series does not reach the window's end) is surfaced as an absent value,
never as 0.

## 5. Window totals (`totals=`)

`<precipitation|snowfall>:<window>` (window as in section 4, always sent),
de-duplicated, sorted by variable then window, comma-joined with literal `,`.
The answers come back in `window_totals` as `WindowTotal` with `quantiles`
(`null` when the window is not covered) and are mapped back to the caller's
order like probabilities. This is the only "storm total" an SDK offers.

## 6. Quantiles

`Quantiles` is the one distribution shape. Its fields are optional, and a
missing field is absent, not 0. An SDK exposes the percentiles the server sent
and may offer named views:

- `range(low, high)`: only for pairs the server serves (p10..p90 and p25..p75
  where present). Any other pair is a usage error. There is no interpolation.
- `median`: p50.

`wind_direction` quantiles are circular: `max` may be numerically less than
`min`. The SDK documents this and does not "fix" it.

## 7. Units

The SDK labels every quantity with its unit for the request's unit system
(the README's units table: metric = °C, mm, m/s, m; imperial = °F, in, mph,
ft; kelvin = metric with K). Converting a caller's threshold uses exact
factors: 1 in = 25.4 mm, 1 ft = 0.3048 m, 1 mph = 0.44704 m/s, °F = °C × 9/5 + 32,
K = °C + 273.15. Response values are never converted client-side: to get other
units, the SDK asks the server.

## 8. Errors

Every non-2xx JSON response is `{"error": "<CODE>", "message": "..."}`. The SDK
raises/returns one error type per language (with subtypes where the idiom
calls for them) carrying:

- `status` (HTTP status), `code` (the string, kept verbatim even when
  unknown), `message`;
- `request_id` if the response carries `X-Request-Id`;
- for 429: `retry_after` (seconds).

Required categories (as subtypes or a discriminant), mapped by code first and
by status when the code is unknown or the body is not JSON:

| Category | Codes | Status fallback |
|---|---|---|
| authentication | `INVALID_API_KEY`, `UNAUTHORIZED` | 401 |
| permission | `PRO_REQUIRED`, `FORBIDDEN` | 403 |
| not found | `LOCATION_NOT_FOUND`, `MODEL_RUN_NOT_FOUND`, `NOT_FOUND`, `GONE` | 404, 410 |
| invalid request | `BAD_REQUEST`, `INVALID_COORDINATES`, `INVALID_ELEVATION`, `INVALID_MAX_HOURS`, `ELEVATION_REQUIRED`, `AMBIGUOUS`, `FEELS_LIKE_UNAVAILABLE` | 400 |
| outside coverage | `OUTSIDE_COVERAGE` | (code only) |
| rate limited | `TOO_MANY_REQUESTS` | 429 |
| unavailable | `FORECAST_UNAVAILABLE`, `TIMEOUT`, `INTERNAL_ERROR`, `DATABASE_ERROR` | 5xx |
| connection | (no response: DNS, TLS, reset, timeout) | n/a |
| usage | (raised by the SDK before sending: an invalid term, an unserved quantile pair) | n/a |

## 9. Retries

Retried automatically, up to `max_retries`: connection errors (except TLS
verification failures), 429, 502, 503, 504. Nothing else is retried.
Requests are all GET, so retrying is safe.

The delay before retry `n` (1-based) is:

- after a 429 or 503 with `Retry-After` (delta-seconds or HTTP-date): exactly
  that, capped at 60 s. If it is over 60 s, the SDK does not retry and
  returns the error with `retry_after` set;
- otherwise: full jitter, a random value in `[0, min(8 s, 0.5 s × 2^(n-1))]`.

The SDK exposes the last response's rate-limit state (`RateLimit-Limit`,
`-Remaining`, `-Reset`, `-Policy`) on the result or client, and never
hard-codes limits.

## 10. Caching

What the server sends (KAN-879):

- **Credential-free requests** get `Cache-Control: public, max-age=0,
  s-maxage=N, stale-while-revalidate=M`. Cloudflare keeps the body for `N`
  seconds (the time until the next expected model cycle, at most to the next
  hour boundary, since the hourly series starts at the current hour). No
  rate-limit headers are sent on these.
- **Requests with a key** get `Cache-Control: private, max-age=0` and are
  never stored at the edge.
- **Every representation has a strong `ETag`.** The server answers a matching
  `If-None-Match` with `304` (it compares weakly, because Cloudflare weakens
  tags when it compresses). On a credential-free request the edge itself can
  answer the 304.

What the SDK does:

1. **Always canonical, keyless where allowed** (sections 3.1, 3.2). This is
   where most of the savings come from: shared edge entries and no 301s.
2. **A local ETag cache, on by default:** an in-memory LRU bounded to 256
   entries and 32 MiB, keyed by the full URL plus a hash of the API key (never
   the key itself; keyless and keyed entries never mix). For a cached entry the
   SDK sends `If-None-Match` with the ETag **byte for byte** as received
   (including any `W/`). On `304` it returns the cached body, marked as
   revalidated, and takes the fresh headers. A response with `no-store` is
   never stored.
3. **Freshness:** the SDK is a private cache (RFC 9111). It uses `max-age`
   (which the API sets to 0, so every call revalidates) and **ignores
   `s-maxage` and `stale-while-revalidate`**, which are for the edge. It never
   serves a stored body without revalidating unless `max-age` allows it.
4. **Revalidation on retry:** a retried request keeps its `If-None-Match`.
5. **Pluggable:** the caller can disable the cache or provide their own store
   through the language's usual interface (a `Cache` protocol, interface, or
   trait), for example to share across processes.
6. **Nothing breaks the cache key:** the SDK adds no timestamps, nonces or
   cache-busting parameters. `Accept-Encoding` is left to the HTTP stack.

## 11. Deprecation

If a response carries `Deprecation` or `Sunset`, the SDK surfaces it once per
operation per process through the language's warning channel (Python
`warnings`, a logger elsewhere), including the `Link rel="deprecation"` URL.

## 12. Paging

List operations return a page plus `next_cursor`. Each SDK offers the page call
and an idiomatic lazy iterator (generator, async iterator, `Iterator`,
`AsyncSequence`, ...) that follows the cursor until it is null.

## 13. Test vectors

`vectors/<area>/<name>.json`, one case per file, all generated by
`scripts/build_vectors.py` (edit the cases there, never the JSON). Each case is
one of two kinds:

- a **single call**: `call` + `expect_request` (or `null` when nothing may be
  sent);
- a **sequence**: `calls` (made in order on one client) + `expect_requests`.

Keys:

| Key | Meaning |
|---|---|
| `client` | Client config: `api_key`, `base_url`, `max_retries`, `cache` (bool), `send_key_on_open_routes` (bool), `env` (environment variables visible to it). Missing = the defaults in section 2. |
| `call` / `calls` | `{"operation": <operationId>, "args": {...}}`. The args use this document's semantic names, and each SDK's runner maps them to its own API: **that mapping is the only per-language code.** A `threshold` is `{"value", "unit"}` with unit one of `mm in degC degF K m ft m/s mph`; a `window` is `{"hours": N}` or `{"start_hours": A, "end_hours": B}`; `"location": "or/slug"` is the combined form; `"iterate": true` on a list operation means "use the lazy iterator and collect everything". A call may carry `"with_api_key"`: make it with that key instead (a per-request override, or a second client sharing the first one's cache). |
| `expect_request(s)` | `method`; `path` (exact, as sent, still percent-encoded); `query` (decoded values, compared per parameter); `query_string` (the raw query string, **exact**: this pins the canonical form, section 3.1); `query_absent`; `headers` (exact); `headers_absent`; `headers_match` (regex); `url_prefix`. |
| `responses` | Consumed in order: `status`, `headers`, and `body_file` (relative to `vectors/`) or `body` (raw text). The runner injects a fake clock, so no vector sleeps. |
| `expect.result` / `expect.results` | Path → value over the semantic model (dot and `[i]` paths). `null` means absent. `{"unknown": "<raw>"}` means "the unknown-enum case, keeping this raw string". `rate_limit.*` reads the rate-limit state and `revalidated` the 304 flag. |
| `expect.error` | `category` (section 8, snake_case), `code`, `status`, `retry_after`, `string_excludes` (a substring that must not appear in the error's message or string form). |
| `expect.requests` | Exact number of HTTP requests made. |
| `expect.delays_s` | The retry delays chosen, with jitter seeded to its upper bound (1.0). |
| `expect.items` | For `iterate`: the slugs collected, in order. |
| `expect.warnings` | Deprecation warnings emitted (`contains` a substring), exactly this many. |
