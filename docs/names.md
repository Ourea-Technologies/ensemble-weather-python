# Names

A few JSON fields would read twice in Python (`forecast.forecast`,
`current.current`, `probability.probability`), so the SDK names them
differently: one table for every Ourea SDK (ensemble-weather-spec
BEHAVIOR.md 3.0). The decoder maps them, and `to_dict()` writes the JSON names
back. Every other field has its JSON name.

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
| `TimeSeriesPoint` | `valid_time` | `valid_at` |
| `TimeSeriesPoint` | `lead_time_hours` | `lead_hours` |
| `MemberGroup` | `members` | `items` |
| `MemberForecast` | `member_id` | `id` |
| `MemberPlume` | `members` | `pool` |
| `PrecipType` | `type` | `kind` |
| `FreezingLevel` | `above_freezing_layer_aloft` | `warm_layer_aloft` |
| `ModelRunInfo` | `models` | `contributors` |
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
| `SnowpackAspect` | `aspect` | `facing` |
