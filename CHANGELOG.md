# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The SDK
version is independent of the API version; this release targets API
contract v1.

## [Unreleased]

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
