"""A short read-only contract run against the live API (nightly live.yml only).

It talks to ``OUREA_BASE_URL`` (default https://api.oureawx.com) with the
key in ``OUREA_API_KEY``. Never run it from tests or pull requests.
"""

from __future__ import annotations

import sys

from ensemble_weather import Chance, Client, NotFoundError, Total


def main() -> int:
    """Exercise one call per route family; exit 1 on the first failure."""
    with Client(user_agent="ensemble-weather-ci/live") as client:
        forecast = client.forecast(
            "or/mt-hood-meadows",
            prob=[Chance.at_least("snowfall", 6, "in"), Chance.at_most("temperature", 0)],
            totals=[Total("snowfall", 72)],
        )
        assert forecast.location.slug == "mt-hood-meadows"
        assert len(forecast.probabilities) == 2
        assert len(forecast.window_totals) == 1
        hits = client.search("hood meadows")
        assert any(hit.slug == "mt-hood-meadows" for hit in hits.items)
        page = client.list_catalog_locations(limit=5)
        assert page.items
        assert client.attribution().providers
        client.current("or/mt-hood-meadows")
        client.alerts("or/mt-hood-meadows")
        client.runs(limit=2)
        try:
            client.forecast("or/this-location-does-not-exist")
        except NotFoundError:
            pass
        else:
            raise AssertionError("an unknown location must be a NotFoundError")
    print("live contract: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
