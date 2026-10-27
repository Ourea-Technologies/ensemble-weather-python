"""Several probability terms in one call, each with its window and member count.

The server computes every probability from the full ensemble; the SDK only
asks. Results come back in the order you asked, whatever order is sent.
"""

from ensemble_weather import Chance, Client, Window

terms = [
    Chance.at_least("snowfall", 6, "in"),  # the next 24 h
    Chance.at_least("snowfall", 12, "in", window=72),  # the next 72 h
    Chance.at_most("temperature", 32, "degF", window=Window(6, 18), aggregation="all"),
    Chance.at_least("wind_speed", 15, "m/s", window=Window(12, 36)),
]

with Client() as client:
    forecast = client.forecast("or/mt-hood-meadows", prob=terms)

for result in forecast.probabilities:
    chance = "n/a" if result.probability is None else f"{result.probability:.0%}"
    print(
        f"P({result.variable} {result.op} {result.threshold} ({forecast.units} units), "
        f"{result.window_start_hours}-{result.window_end_hours} h, {result.aggregation}) "
        f"= {chance} from {result.members} members"
    )
