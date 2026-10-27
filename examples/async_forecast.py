"""The async client: several forecasts concurrently with asyncio."""

import asyncio

from ensemble_weather import AsyncClient


async def main() -> None:
    """Fetch two views of a forecast at once."""
    async with AsyncClient() as client:
        metric, imperial = await asyncio.gather(
            client.forecast("or/mt-hood-meadows"),
            client.forecast("or/mt-hood-meadows", units="imperial"),
        )
    print(metric.location.name, metric.units, imperial.units)


asyncio.run(main())
