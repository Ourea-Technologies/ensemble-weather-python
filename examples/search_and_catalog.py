"""Search for a location, then page through the catalog with the cursor."""

from ensemble_weather import Client

with Client() as client:
    hits = client.search("hood meadows")
    for hit in hits.items:
        print(f"{hit.key}: {hit.name} ({hit.type}), {hit.county} County")

    if hits.items:  # any hit can be passed straight to forecast()
        forecast = client.forecast(hits.items[0])
        print(f"{forecast.location.name}: {len(forecast.forecast.timeseries)} hours")

    # The lazy iterator follows next_cursor until the last page.
    for entry in client.iter_catalog_locations(limit=20):
        print(f"catalog: {entry.state}/{entry.slug} {entry.name}")

    # Or one page at a time:
    page = client.list_catalog_locations(limit=20)
    print(f"first page: {len(page.items)} entries, next cursor {page.next_cursor!r}")
