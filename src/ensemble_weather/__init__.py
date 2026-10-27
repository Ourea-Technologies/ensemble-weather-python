"""Official Python SDK for the Ourea probabilistic weather API.

Every forecast value is a distribution computed by the server from the full
ensemble; probabilities and window totals are asked for, never derived::

    from ensemble_weather import Chance, Client

    with Client() as client:
        forecast = client.forecast(
            "or/mt-hood-meadows", prob=[Chance.at_least("snowfall", 6, "in")]
        )
        print(forecast.probabilities[0].probability)

See https://docs.oureawx.com/python.
"""

from ._async_client import AsyncClient
from ._client import Client
from ._core import DEFAULT_BASE_URL, MAX_BODY_BYTES
from ._version import __version__
from .cache import Cache, CacheEntry, MemoryCache
from .enums import Aggregation, LocationType, Op, TotalVariable, Unit, UnitSystem, Variable
from .errors import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    InvalidRequestError,
    NotFoundError,
    OureaDeprecationWarning,
    OureaError,
    OutsideCoverageError,
    PermissionDeniedError,
    RateLimitError,
    ResponseTooLargeError,
    UnavailableError,
    UnexpectedResponseError,
    UsageError,
)
from .models import (
    ForecastResponse,
    ProbabilityResult,
    Quantiles,
    RateLimit,
    ResponseMeta,
    WindowTotal,
)
from .probabilities import Chance, Total, Window

__all__ = [
    "DEFAULT_BASE_URL",
    "MAX_BODY_BYTES",
    "APIConnectionError",
    "APIError",
    "Aggregation",
    "AsyncClient",
    "AuthenticationError",
    "Cache",
    "CacheEntry",
    "Chance",
    "Client",
    "ForecastResponse",
    "InvalidRequestError",
    "LocationType",
    "MemoryCache",
    "NotFoundError",
    "Op",
    "OureaDeprecationWarning",
    "OureaError",
    "OutsideCoverageError",
    "PermissionDeniedError",
    "ProbabilityResult",
    "Quantiles",
    "RateLimit",
    "RateLimitError",
    "ResponseMeta",
    "ResponseTooLargeError",
    "Total",
    "TotalVariable",
    "UnavailableError",
    "UnexpectedResponseError",
    "Unit",
    "UnitSystem",
    "UsageError",
    "Variable",
    "Window",
    "WindowTotal",
    "__version__",
]
