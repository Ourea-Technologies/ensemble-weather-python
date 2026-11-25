"""A short read-only contract run against the live API (nightly live.yml only).

It talks to ``OUREA_BASE_URL`` (default https://api.oureawx.com) with the
key in ``OUREA_API_KEY``. Never run it from tests or pull requests.
"""

from __future__ import annotations

import contextlib
import sys

from ensemble_weather import Chance, Client, NotFoundError, PermissionDeniedError, Total


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
        assert all(p.term for p in forecast.probabilities)  # matched by the echoed term
        assert forecast.series.timeseries[0].ensemble.wind_direction.sector_50 is not None
        hits = client.search("hood meadows")
        assert any(hit.slug == "mt-hood-meadows" for hit in hits.items)
        page = client.list_catalog_locations(limit=5)
        assert page.items
        assert client.attribution().providers
        client.current("or/mt-hood-meadows")
        client.alerts("or/mt-hood-meadows")
        client.runs(limit=2)
        client.list_catalog_stations(limit=2)  # may be empty: the shape is what is checked
        # The routes added with spec 40c2ae8 (server 256cd770).
        plume = client.forecast("or/mt-hood-meadows", members="plume", max_hours=12)
        assert plume.series.plume is not None
        ranked = client.explore("snow_5d", limit=3)
        assert ranked.items
        assert ranked.items[0].rank == 1
        sorted_hits = client.search("hood", sort="snow_5d", near=(45.33, -121.66))
        assert any(hit.explore is not None for hit in sorted_hits.items)
        assert client.composition().total_members > 0
        assert client.season("or/mt-hood-meadows").water_year >= 2027
        assert client.snowpack("or/mt-hood-meadows").beta
        assert client.snowpack_plume("or/mt-hood-meadows").beta
        assert client.alert_outlines(classes=["winter"]).type == "FeatureCollection"
        assert client.avalanche_zones().features
        with contextlib.suppress(PermissionDeniedError):  # Plus or Pro; else PLUS_REQUIRED
            assert client.snow_trend("or/mt-hood-meadows").grids
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
