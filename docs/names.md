# Names

A JSON field that repeats a word of the type holding it would read twice in
Python (`forecast.forecast`, `current.current`, `probability.probability`),
so the SDK names it differently. There is one table for every Ourea SDK
(ensemble-weather-spec BEHAVIOR.md 3.0). The decoder maps the names, and
`to_dict()` writes the JSON names back. Every other field keeps its JSON
name, and the GeoJSON routes (`alert_outlines`, `avalanche_zones`) are
passed through untouched: an avalanche zone's `properties.forecast_url`
stays `forecast_url`.

| Type | JSON field | SDK attribute |
|---|---|---|
| `ForecastResponse` | `forecast` | `series` |
| `ForecastResponse` | `elevation_forecasts` | `elevations` |
| `CurrentResponse` | `current` | `now` |
| `CurrentConditions` | `condition` | `code` |
| `CurrentConditions` | `condition_text` | `text` |
| `CurrentConditions` | `condition_icon` | `icon` |
| `CurrentStation` | `station_id` | `id` |
| `ProbabilityResult` | `probability` | `value` |
| `ProbabilityThresholds` | `daily_precipitation_probability` | `daily_precipitation` |
| `ProbabilityThresholds` | `daily_precipitation_occurrence_probability` | `daily_precipitation_occurrence` |
| `ProbabilityThresholds` | `daily_snow_probability` | `daily_snow` |
| `WindowTotal` | `window_start_hours` | `start_hours` |
| `WindowTotal` | `window_end_hours` | `end_hours` |
| `MemberGroup` | `members` | `items` |
| `MemberForecast` | `member_id` | `id` |
| `MemberPlume` | `members` | `pool` |
| `AlertsResponse` | `alerts` | `items` |
| `AlertsResponse` | `alert_count` | `count` |
| `LocationsResponse` | `locations` | `items` |
| `NearbyLocationsResponse` | `location` | `origin` |
| `NearbyLocationsResponse` | `locations` | `items` |
| `NearbyPointResponse` | `locations` | `items` |
| `RunsResponse` | `runs` | `items` |
| `ElevationForecast` | `elevation` | `height` |
| `ElevationSummary` | `elevation` | `height` |
| `SnowTrendResponseElevation` | `elevation` | `height` |
| `PublicCatalogElevation` | `elevation_m` | `height_m` |
| `PublicCatalogStation` | `source_station_id` | `source_id` |
| `PublicCatalogStation` | `station_status` | `status` |
| `PublicCatalogStation` | `station_url` | `url` |
| `PublicCatalogNearbyStation` | `station_status` | `status` |
| `CatalogTemplateSummary` | `template_variant` | `variant` |
| `CatalogResolvedEntry` | `resolved_locale` | `locale` |
| `SensorObservation` | `observation_time` | `observed_at` |
| `PassHour` | `snow_level_above_pass` | `snow_level_margin` |
| `PassStatusSegment` | `status` | `state` |
| `PassStatusSegment` | `status_text` | `text` |
| `AvalancheForecast` | `forecast_url` | `url` |
| `SeasonTotal` | `total` | `amount` |
| `SnowTrendDay` | `snow` | `amount` |
