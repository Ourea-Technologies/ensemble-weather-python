"""Where is it snowing? Rank places, then read one place's season and snow trend.

``explore`` ranks places by a metric the server computes (here the next five
days' snowfall); ``season`` is the observed season to date; ``snow_trend``
(Plus or Pro) shows each recent run's daily snowfall, so you can see a storm
firm up or fade. Anonymous and Free callers get the first two.
"""

from ensemble_weather import Client, PermissionDeniedError

with Client(units="imperial") as client:
    ranked = client.explore("snow_5d", limit=5)
    print(f"Most snow in the next 5 days ({ranked.unit}):")
    for item in ranked.items:
        low_high = "" if item.p10 is None else f" ({item.p10:.1f} to {item.p90:.1f})"
        print(
            f"  {item.rank}. {item.location.name}, {item.location.state.upper()}: "
            f"{item.value:.1f}{low_high}"
        )

    season = client.season("or/mt-hood-meadows")
    total = season.precipitation
    print(f"\nWater year {season.water_year} at {season.location.name}, through {season.through}:")
    if total is not None:
        normal = (
            "" if total.percent_of_normal is None else f", {total.percent_of_normal}% of normal"
        )
        print(f"  precipitation {total.total} {total.unit}{normal}")

    try:
        trend = client.snow_trend("or/mt-hood-meadows")
    except PermissionDeniedError:
        print("\nThe snow trend is part of Plus and Pro (set OUREA_API_KEY).")
    else:
        grid = trend.grids[0]
        newest = grid.runs[-1]
        print(f"\nSnow trend ({grid.source}), newest run {newest.initialized_at:%a %H:%MZ}:")
        for day in newest.days:
            if day is not None:
                print(f"  {day.date}: {day.snow}")
