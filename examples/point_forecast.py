"""A forecast at coordinates and a chosen elevation (needs a Pro key).

Reads the key from OUREA_API_KEY; without one it says so and exits 0.
"""

import os
import sys

from ensemble_weather import Client

if not os.environ.get("OUREA_API_KEY"):
    print("point_forecast: set OUREA_API_KEY to a Pro key to run this example.")
    sys.exit(0)

with Client() as client:
    forecast = client.forecast_at(45.3311, -121.6649, elevation_m=2000, max_hours=48)

point = forecast.point
if point is not None:
    print(f"Forecast at {point.lat}, {point.lon}, {point.elevation} m ({point.elevation_source})")
for hour in forecast.forecast.timeseries:
    wind = hour.ensemble.wind_speed
    print(f"{hour.valid_time:%a %H:%M} UTC  median wind {wind.median} m/s, p90 {wind.p90} m/s")
