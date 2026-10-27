"""The same forecast in metric and imperial units.

The server converts; the SDK never converts response values. Ask for the
units you want to show.
"""

from ensemble_weather import Client

with Client() as client:
    metric = client.forecast("or/mt-hood-meadows")
    imperial = client.forecast("or/mt-hood-meadows", units="imperial")

for m, i in zip(metric.forecast.timeseries, imperial.forecast.timeseries, strict=True):
    print(
        f"{m.valid_time:%H:%M} UTC  median {m.ensemble.temperature.median} °C"
        f" = {i.ensemble.temperature.median} °F"
    )
