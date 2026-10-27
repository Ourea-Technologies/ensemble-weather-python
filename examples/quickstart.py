"""Quickstart: an anonymous forecast for Mt. Hood Meadows, with no API key.

Prints each of the next 24 hours' temperature as a range (p10-p90) and the
chance of at least 6 in (15 cm) of snow in the next 24 hours.
"""

from ensemble_weather import Chance, Client

with Client() as client:  # no key: anonymous calls use the Free tier
    forecast = client.forecast(
        "or/mt-hood-meadows",
        units="imperial",
        prob=[Chance.at_least("snowfall", 6, "in")],  # window: the next 24 h
    )

print(forecast.location.name)
for hour in forecast.forecast.timeseries[:24]:
    temp = hour.ensemble.temperature
    print(f"{hour.valid_time:%a %H:%M} UTC  {temp.p10} to {temp.p90} °F (p10-p90)")

snow = forecast.probabilities[0]
chance = "not available" if snow.probability is None else f"{snow.probability:.0%}"
print(f"Chance of at least 6 in of snow in the next 24 h: {chance} ({snow.members} members)")
