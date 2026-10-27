# ensemble-weather

The official Python SDK for the [Ourea](https://oureawx.com) probabilistic
weather API. Guides for every language live at
[docs.oureawx.com](https://docs.oureawx.com); this site is the Python API
reference ([docs.oureawx.com/python](https://docs.oureawx.com/python) is the
Python guide).

```sh
pip install ensemble-weather
```

```python
from ensemble_weather import Chance, Client

with Client() as client:  # no key: anonymous calls use the Free tier
    forecast = client.forecast(
        "or/mt-hood-meadows",
        units="imperial",
        prob=[Chance.at_least("snowfall", 6, "in")],
    )

for hour in forecast.forecast.timeseries[:24]:
    print(hour.valid_time, hour.ensemble.temperature.range(10, 90))
print(forecast.probabilities[0].probability)
```

- [`Client`][ensemble_weather.Client] and
  [`AsyncClient`][ensemble_weather.AsyncClient] have one method per API
  operation, and both work as context managers.
- Every value is a [`Quantiles`][ensemble_weather.models.Quantiles]
  distribution computed by the server.
- Ask for probabilities with [`Chance`][ensemble_weather.Chance] and storm
  totals with [`Total`][ensemble_weather.Total]; the SDK never computes them.
- Errors derive from [`OureaError`][ensemble_weather.OureaError].

The API key comes from `Client(api_key=...)` or `OUREA_API_KEY`; the base URL
from `Client(base_url=...)`, `OUREA_BASE_URL`, or `https://api.oureawx.com`.
