"""Window totals: the distribution of each member's storm total.

Never add up hourly quantiles to get a total: the sum of hourly medians is not
the median total. Ask the server for the window total instead.
"""

from ensemble_weather import Client, Total, Window

with Client() as client:
    forecast = client.forecast(
        "or/mt-hood-meadows",
        units="imperial",
        totals=[Total("snowfall", 72), Total("precipitation", Window(24, 72))],
    )

for total in forecast.window_totals:
    span = f"{total.window_start_hours}-{total.window_end_hours} h"
    if total.quantiles is None:
        print(f"{total.variable} {span}: no distribution ({total.null_reason})")
        continue
    q = total.quantiles
    print(f"{total.variable} {span}: median {q.median} in, p10-p90 {q.range(10, 90)} in")
