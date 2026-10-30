# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The SDK
version is independent of the API version; this release targets API
contract v1.

## [Unreleased]

Targets the v1 contract as deployed (ensemble-weather-spec 8b85fea, the
server's public spec byte for byte). Breaking, as 0.x allows.

### Changed

- `forecast_at` is renamed `get_point_forecast` (on `Client` and
  `AsyncClient`), matching the operation `getPointForecast`; there is no
  alias.
- The location argument of `forecast`, `current`, `alerts` and `nearby` is
  `slug` (was `name`), as the path parameter `{slug}`.
- `precip_*` fields are `precipitation_*`: `DailyForecast`
  `total_precipitation`, `total_precipitation_if_wet`,
  `precipitation_probability`, `precipitation_occurrence_probability`,
  `precipitation_type`, `precipitation_display`; `TimeSeriesPoint`
  `precipitation_type`; `CurrentConditions.precipitation_probability`;
  `SensorObservation.precipitation_rate`; `ProbabilityThresholds`
  `daily_precipitation_probability` and
  `daily_precipitation_occurrence_probability`.
- `EnsembleStats.wind_direction` and `ModelStats.wind_direction` are
  `CircularStats` (`mean`, `stddev`, `sector_50`, `sector_90`), not
  `Quantiles`.
- `ProbabilityResult.term` and `WindowTotal.term` are the server's
  canonical term string, and results are matched to the caller's terms by
  it; the caller's `Chance` / `Total` moved to `.request`.
- One `ConditionIcon` enum replaces `HourlyConditionIcon` and
  `DailyConditionIcon` (also on `CurrentConditions.condition_icon`).
- Alert `severity` and `urgency` are the snake_case enums `AlertSeverity`
  and `AlertUrgency`; catalog `network`, `station_status` and
  `template.template_variant` / `location_type` are the snake_case enums
  `StationNetwork`, `StationStatus`, `TemplateVariant` and `LocationType`.
- `LocationRef.slug` and `.type` may be `None` (a coordinate forecast's
  location).
- Comma lists (`sources`, `include`, `network`, `capability`, ...) are sent
  sorted, de-duplicated and joined by a literal `,`, the server's canonical
  form; `capability` is one list, not a repeated parameter.
- Error categories follow the 16 public error codes: `AUTH_UNAVAILABLE` is
  unavailable; `FORBIDDEN`, `GONE`, `MODEL_RUN_NOT_FOUND`, `AMBIGUOUS`,
  `INVALID_MAX_HOURS` and `FEELS_LIKE_UNAVAILABLE` are no longer special-cased
  (an unknown code still maps by status). `OUTSIDE_COVERAGE` is a 404.
- `Retry-After` is honoured on 504 as well as 429 and 503.

### Added

- `include=` on `forecast` / `get_point_forecast` (`skin_temperature`, `mslp`:
  served only when asked for).
- `ProbabilityResult.null_reason` and `WindowTotal.null_reason`
  (`NullReason`), `WindowTotal.aggregation`.
- `APIError.doc_url` and `.param`; `request_id` is read from the error
  body first. `PermissionDeniedError.nearest_location` (`NearestLocation`):
  the keyless named location near a refused coordinate.
- `ActiveAlert.certainty`, `CurrentStation.station_id`.
- `runs(cursor=...)` and `RunsResponse.next_cursor`.

### Removed

- `storm_reports` / `storm_report` and `StormReportCard` /
  `StormReportsResponse`: storm reports are not in the public API.
- `EnsembleStats.wind_direction_circular`, `.feels_like_utci`, `.ptype`;
  `DailyForecast.feels_like_utci_high` / `_low`;
  `ElevationForecast.default` and `.timeseries` (`LegacyHourlyPoint`); the
  catalog `ads` fields and their models (`CatalogResolvedAdSlot`,
  `CatalogHousePlacement`, `CatalogThirdPartyPlacement`,
  `CmsAdCreativeContent`, `AdSlotKind`, `AdProvider`).

## [0.1.0] - 2026-10-26

### Added

- `Client` and `AsyncClient` (httpx), usable as (async) context managers,
  with one method per v1 operation except `getMapsToken`: `forecast`,
  `forecast_at`, `current`, `current_at`, `alerts`, `alerts_at`, `nearby`,
  `nearby_at`, `search`, `list_locations`, `list_catalog_locations`,
  `catalog_location`, `list_catalog_stations`, `catalog_station`, `runs`,
  `storm_reports`, `storm_report` and `attribution`, plus lazy `iter_*`
  iterators that follow `next_cursor`.
- `Chance`, `Total` and `Window` to ask for probabilities (`prob=`) and
  window totals (`totals=`), sent in canonical order and answered in the
  caller's order; thresholds in other units are converted exactly and
  rounded half away from zero as the server does.
- Frozen dataclass models for every schema the operations reach, with open
  enums that keep unknown values.
- Canonical URLs, keyless open routes, same-origin redirects, retries with
  full jitter and `Retry-After`, an in-memory ETag cache (pluggable),
  deprecation warnings, rate-limit state and a 64 MiB response bound.
- `OureaError` hierarchy, one subclass per error category.
- Optional `pandas` extra for `to_dataframe()`.
- The shared spec pinned in `spec/` (12e904b) and all 43 vectors in the tests.

[Unreleased]: https://github.com/Ourea-Technologies/ensemble-weather-python/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ourea-Technologies/ensemble-weather-python/releases/tag/v0.1.0
