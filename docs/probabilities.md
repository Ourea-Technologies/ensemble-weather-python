# Probabilities, not single numbers

The server computes every probability, window total and range from the full
ensemble. The SDK only asks for them; it never sums, averages or
interpolates quantiles, and never derives a probability from them. (The sum
of hourly medians is not the median storm total.)

## Chances

```python
from ensemble_weather import Chance, Window

Chance.at_least("snowfall", 6, "in")  # 0-24 h total >= 6 in
Chance.at_least("snowfall", 12, "in", window=72)  # 0-72 h total >= 12 in
Chance.at_most("temperature", 32, "degF", window=Window(6, 18), aggregation="all")
Chance.at_least("wind_speed", 15, "m/s", window=(12, 36))
```

A threshold with a unit is converted exactly into the request's units (1 in =
25.4 mm, 1 ft = 0.3048 m, 1 mph = 0.44704 m/s, °F = °C × 9/5 + 32,
K = °C + 273.15), then rounded the way the server rounds: half away from
zero on `value × 10^d` in doubles, `d` being the variable's served precision
(amounts 2 decimals metric, 3 imperial; temperature and wind 1; snow level 0).
Without a unit, the threshold is already in the request's units.

`aggregation` is `total` for precipitation and snowfall (their only choice),
and `any` (the default) or `all` for the others. Anything else raises
`UsageError` before a request is sent.

The terms are sent de-duplicated and in the server's canonical order (one
URL, one edge-cache entry), and `forecast.probabilities` lists the answers in
**your** order. Each [`ProbabilityResult`][ensemble_weather.ProbabilityResult]
carries its reference class: `variable`, `op`, `threshold`, the window,
`aggregation`, `from_`/`to` and `members`, plus `term` (the canonical
spelling the SDK sent, which the server echoes and the SDK matches your terms
by, never by position) and `request`, your `Chance`. A `probability` of
`None` is never 0: `null_reason` says why (`window_not_covered`,
`too_few_members`, `variable_unavailable`).

## Window totals

```python
from ensemble_weather import Total

forecast = client.forecast("or/mt-hood-meadows", totals=[Total("snowfall", 72)])
total = forecast.window_totals[0]
total.quantiles.p10, total.quantiles.median, total.quantiles.p90
```

Each [`WindowTotal`][ensemble_weather.WindowTotal] carries `term`,
`aggregation` (`total`) and `request`, your `Total`, and is matched by `term`
like a probability. `quantiles` is `None` when the window cannot be answered,
with the reason in `null_reason`.

## Quantiles

A [`Quantiles`][ensemble_weather.Quantiles] has `mean`, `p10`, `p25`, `p50`,
`p75`, `p90` and sometimes `min`, `max` and `probability`; a value the server
did not send is `None`. `median` is the p50. `range(10, 90)` and
`range(25, 75)` return the served pairs; any other pair is a `UsageError`
(there is no interpolation).

Wind direction is not a `Quantiles` but a
[`CircularStats`][ensemble_weather.models.CircularStats]: `mean`, `stddev`,
and the sectors `sector_50` and `sector_90`, each running clockwise from
`from_` to `to`, so `to` can be numerically less than `from_` (`350` to `20`
crosses north). The SDK leaves it as sent.
