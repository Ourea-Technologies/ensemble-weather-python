"""Exceptions raised by the SDK.

Everything the SDK raises derives from :class:`OureaError`. Errors that come
with an HTTP response derive from :class:`APIError` and carry its ``status``,
``code`` (the API's error string, verbatim, even when this SDK does not know
it), ``message`` and ``request_id``. Catch the subclass for the category you
care about::

    try:
        client.forecast_at(45.0, 10.0)
    except OutsideCoverageError as err:
        print(err.code, err.message)

The API key never appears in an error's message, ``str`` or ``repr``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from .models import RateLimit

__all__ = [
    "APIConnectionError",
    "APIError",
    "AuthenticationError",
    "InvalidRequestError",
    "NotFoundError",
    "OureaDeprecationWarning",
    "OureaError",
    "OutsideCoverageError",
    "PermissionDeniedError",
    "RateLimitError",
    "ResponseTooLargeError",
    "UnavailableError",
    "UnexpectedResponseError",
    "UsageError",
]


class OureaError(Exception):
    """Base class of every error the SDK raises."""

    category: ClassVar[str] = "error"
    """The BEHAVIOR.md section 8 category, in snake_case."""

    def __init__(self, message: str) -> None:
        """Create the error with a human-readable message."""
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        """Return the message."""
        return self.message


class UsageError(OureaError, ValueError):
    """The call was refused before anything was sent.

    For example an aggregation a variable does not support, a threshold unit
    of the wrong kind, or a quantile pair the server does not serve.
    """

    category = "usage"


class APIConnectionError(OureaError):
    """No HTTP response arrived: DNS, TLS, connection reset or timeout."""

    category = "connection"


class UnexpectedResponseError(OureaError):
    """A successful response could not be read as the documented model."""

    category = "unexpected_response"


class ResponseTooLargeError(UnexpectedResponseError):
    """A response body was over the SDK's size bound (64 MiB)."""

    def __init__(self, limit: int) -> None:
        """Record the bound that was exceeded."""
        super().__init__(f"the response body is larger than {limit // (1024 * 1024)} MiB")
        self.limit = limit


class OureaDeprecationWarning(FutureWarning):
    """The API marked an operation as deprecated (``Deprecation`` / ``Sunset``).

    Emitted once per operation per process. It is a :class:`FutureWarning`,
    so Python shows it by default.
    """


class APIError(OureaError):
    """The API answered with an error status.

    Attributes:
        status: The HTTP status code.
        code: The API's error code (``"LOCATION_NOT_FOUND"``), verbatim, or
            ``None`` when the body was not the API's JSON error shape.
        message: The API's message.
        request_id: The ``X-Request-Id`` response header, for support.
        retry_after: Seconds the server asked the client to wait, if it did.
        rate_limit: The rate-limit state the response reported, if any.
    """

    category = "api"

    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: str | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
        rate_limit: RateLimit | None = None,
    ) -> None:
        """Create the error from a response's parts."""
        super().__init__(message)
        self.status = status
        self.code = code
        self.request_id = request_id
        self.retry_after = retry_after
        self.rate_limit = rate_limit

    def __str__(self) -> str:
        """Return ``"<status> <code>: <message>"``."""
        label = f"{self.status} {self.code}" if self.code else str(self.status)
        text = f"{label}: {self.message}"
        if self.request_id:
            text += f" (request id {self.request_id})"
        return text

    def __repr__(self) -> str:
        """Return a debugging representation (never containing the key)."""
        return (
            f"{type(self).__name__}(status={self.status!r}, code={self.code!r}, "
            f"message={self.message!r}, request_id={self.request_id!r})"
        )


class AuthenticationError(APIError):
    """The API key is missing where required, unknown or revoked (401)."""

    category = "authentication"


class PermissionDeniedError(APIError):
    """The key's tier does not allow this request, e.g. ``PRO_REQUIRED`` (403)."""

    category = "permission"


class NotFoundError(APIError):
    """The location, run or report does not exist (404, 410)."""

    category = "not_found"


class InvalidRequestError(APIError):
    """The server refused the request's parameters (400)."""

    category = "invalid_request"


class OutsideCoverageError(APIError):
    """The coordinates are outside the forecast domain (``OUTSIDE_COVERAGE``)."""

    category = "outside_coverage"


class RateLimitError(APIError):
    """Too many requests (429). See :attr:`APIError.retry_after`."""

    category = "rate_limited"


class UnavailableError(APIError):
    """The API could not answer right now (5xx), e.g. ``FORECAST_UNAVAILABLE``."""

    category = "unavailable"


_BY_CODE: dict[str, type[APIError]] = {
    "INVALID_API_KEY": AuthenticationError,
    "UNAUTHORIZED": AuthenticationError,
    "PRO_REQUIRED": PermissionDeniedError,
    "FORBIDDEN": PermissionDeniedError,
    "LOCATION_NOT_FOUND": NotFoundError,
    "MODEL_RUN_NOT_FOUND": NotFoundError,
    "NOT_FOUND": NotFoundError,
    "GONE": NotFoundError,
    "BAD_REQUEST": InvalidRequestError,
    "INVALID_COORDINATES": InvalidRequestError,
    "INVALID_ELEVATION": InvalidRequestError,
    "INVALID_MAX_HOURS": InvalidRequestError,
    "ELEVATION_REQUIRED": InvalidRequestError,
    "AMBIGUOUS": InvalidRequestError,
    "FEELS_LIKE_UNAVAILABLE": InvalidRequestError,
    "OUTSIDE_COVERAGE": OutsideCoverageError,
    "TOO_MANY_REQUESTS": RateLimitError,
    "FORECAST_UNAVAILABLE": UnavailableError,
    "TIMEOUT": UnavailableError,
    "INTERNAL_ERROR": UnavailableError,
    "DATABASE_ERROR": UnavailableError,
}

_BY_STATUS: dict[int, type[APIError]] = {
    400: InvalidRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    410: NotFoundError,
    429: RateLimitError,
}


def error_class(status: int, code: str | None) -> type[APIError]:
    """Pick the exception class: by code first, then by status."""
    if code is not None and code in _BY_CODE:
        return _BY_CODE[code]
    if status in _BY_STATUS:
        return _BY_STATUS[status]
    if 500 <= status <= 599:
        return UnavailableError
    return APIError
