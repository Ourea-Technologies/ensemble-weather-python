"""The SDK-side security guarantees (SDK-STANDARD "Security")."""

from __future__ import annotations

import asyncio
import inspect
import logging
import ssl
from typing import TYPE_CHECKING

import httpx
import pytest

from ensemble_weather import (
    MAX_BODY_BYTES,
    APIConnectionError,
    AsyncClient,
    AuthenticationError,
    Client,
    ResponseTooLargeError,
    UnavailableError,
)
from ensemble_weather.models import ForecastResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from conftest import Recorder

SECRET = "ow_secret_do_not_print_0123456789"


# --- the key never leaks ------------------------------------------------------------


def test_key_not_in_client_repr(make_client: Callable[..., Client]) -> None:
    client = make_client(api_key=SECRET)
    assert SECRET not in repr(client)
    assert SECRET not in str(client)
    assert "api_key=set" in repr(client)


def test_key_not_in_async_client_repr() -> None:
    client = AsyncClient(api_key=SECRET)
    assert SECRET not in repr(client)
    asyncio.run(client.aclose())


def test_key_not_in_errors_even_when_echoed(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    echo = f'{{"error": "INVALID_API_KEY", "message": "key {SECRET} is unknown"}}'
    recorder.add(401, content=echo.encode(), headers={"Content-Type": "application/json"})
    client = make_client(api_key=SECRET)
    with pytest.raises(AuthenticationError) as caught:
        client.forecast("or/mt-hood-meadows")
    error = caught.value
    for text in (str(error), repr(error), error.message, *map(str, error.args)):
        assert SECRET not in text


def test_key_not_in_connection_errors(make_client: Callable[..., Client]) -> None:
    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"refused {SECRET}")

    client = Client(api_key=SECRET, transport=httpx.MockTransport(fail), max_retries=0)
    with pytest.raises(APIConnectionError) as caught:
        client.forecast("or/mt-hood-meadows")
    assert SECRET not in str(caught.value)
    assert SECRET not in repr(caught.value)
    client.close()
    del make_client


def test_key_not_in_logs(
    recorder: Recorder, make_client: Callable[..., Client], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    recorder.add(301, headers={"Location": "/api/v1/locations/or/mt-hood-meadows"})
    recorder.add(200, name="forecast-metric.json")
    recorder.add(503, name="error-unavailable.json")
    client = make_client(api_key=SECRET, max_retries=0)
    client.forecast("oregon/mt-hood-meadows")
    with pytest.raises(UnavailableError):
        client.forecast("or/mt-hood-meadows", max_hours=48)
    assert caplog.records, "the SDK logs requests at DEBUG"
    assert SECRET not in caplog.text


def test_key_not_in_response_meta_or_model_repr(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    recorder.add(200, name="forecast-metric.json")
    result = make_client(api_key=SECRET).forecast("or/mt-hood-meadows")
    assert SECRET not in repr(result)
    assert SECRET not in repr(result.meta)


def test_cache_key_never_holds_the_key(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    recorder.add(200, name="forecast-metric.json", headers={"ETag": '"v1"'})
    client = make_client(api_key=SECRET)
    client.forecast("or/mt-hood-meadows")
    cache = client.cache
    assert cache is not None
    keys = list(cache._entries)  # type: ignore[attr-defined]
    assert keys
    assert all(SECRET not in key for key in keys)


# --- redirects ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "location",
    [
        "https://elsewhere.example.test/api/v1/locations/or/mt-hood-meadows",
        "http://api.oureawx.com/api/v1/locations/or/mt-hood-meadows",  # downgrade
        "https://api.oureawx.com:8443/api/v1/locations/or/mt-hood-meadows",  # other port
    ],
)
def test_key_dropped_on_redirect_off_origin(
    location: str, recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    recorder.add(302, headers={"Location": location})
    recorder.add(200, name="forecast-metric.json")
    make_client(api_key=SECRET).forecast("or/mt-hood-meadows")
    first, second = recorder.requests
    assert first.headers["X-API-Key"] == SECRET
    assert "X-API-Key" not in second.headers
    assert str(second.url) == location


def test_key_not_restored_after_bouncing_through_another_host(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    recorder.add(302, headers={"Location": "https://elsewhere.example.test/x"})
    recorder.add(302, headers={"Location": "https://evil.example.test/y"})
    recorder.add(200, name="forecast-metric.json")
    make_client(api_key=SECRET).forecast("or/mt-hood-meadows")
    assert [("X-API-Key" in r.headers) for r in recorder.requests] == [True, False, False]


def test_redirects_are_bounded(recorder: Recorder, make_client: Callable[..., Client]) -> None:
    for _ in range(10):
        recorder.add(302, headers={"Location": "/api/v1/locations/or/mt-hood-meadows"})
    with pytest.raises(Exception):  # noqa: B017, PT011 - a 302 that is not followed is an error
        make_client().forecast("or/mt-hood-meadows")
    assert len(recorder.requests) == 6  # the first request and 5 redirects


# --- TLS ------------------------------------------------------------------------------


@pytest.mark.parametrize("cls", [Client, AsyncClient])
def test_no_option_disables_tls(cls: type[Client | AsyncClient]) -> None:
    parameters = set(inspect.signature(cls.__init__).parameters)
    for forbidden in ("verify", "insecure", "ssl", "ssl_context", "verify_ssl", "http_client"):
        assert forbidden not in parameters


def test_default_transport_verifies_certificates() -> None:
    client = Client()
    transport = client._http._transport
    assert isinstance(transport, httpx.HTTPTransport)
    context = transport._pool._ssl_context
    assert context is not None
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    client.close()


def test_tls_verification_failure_is_not_retried() -> None:
    attempts = 0

    def fail(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        cause = ssl.SSLCertVerificationError("certificate verify failed")
        raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]") from cause

    client = Client(transport=httpx.MockTransport(fail))
    client._sleep = lambda _d: None
    with pytest.raises(Exception, match="CERTIFICATE_VERIFY_FAILED"):
        client.forecast("or/mt-hood-meadows")
    assert attempts == 1
    client.close()


# --- body size bound ---------------------------------------------------------------


def test_declared_oversize_body_is_refused(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    def huge(_request: httpx.Request) -> httpx.Response:
        def stream() -> Iterator[bytes]:
            yield b"{}"

        headers = {"Content-Length": str(MAX_BODY_BYTES + 1)}
        return httpx.Response(200, headers=headers, content=stream())

    recorder.queue.append(huge)
    with pytest.raises(ResponseTooLargeError):
        make_client().forecast("or/mt-hood-meadows")


def test_streamed_oversize_body_is_refused(
    recorder: Recorder, make_client: Callable[..., Client]
) -> None:
    chunk = b" " * (1024 * 1024)

    def endless(_request: httpx.Request) -> httpx.Response:
        def stream() -> Iterator[bytes]:
            for _ in range(65):
                yield chunk

        return httpx.Response(200, content=stream())

    recorder.queue.append(endless)
    with pytest.raises(ResponseTooLargeError):
        make_client().forecast("or/mt-hood-meadows")


def test_streamed_oversize_body_is_refused_async() -> None:
    chunk = b" " * (1024 * 1024)

    async def stream() -> AsyncIterator[bytes]:
        for _ in range(65):
            yield chunk

    def endless(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=stream())

    async def main() -> None:
        async with AsyncClient(transport=httpx.MockTransport(endless)) as client:
            await client.forecast("or/mt-hood-meadows")

    with pytest.raises(ResponseTooLargeError):
        asyncio.run(main())


# --- JSON is data, never code -------------------------------------------------------


def test_json_never_selects_types(recorder: Recorder, make_client: Callable[..., Client]) -> None:
    import json  # noqa: PLC0415

    from conftest import json_body  # noqa: PLC0415

    data = json_body("forecast-metric.json")
    data["__class__"] = "os.system"
    data["location"]["__init__"] = "boom"
    data["$type"] = "System.Diagnostics.Process"
    recorder.add(200, content=json.dumps(data).encode())
    result = make_client().forecast("or/mt-hood-meadows")
    assert type(result) is ForecastResponse
    assert not hasattr(result, "$type")
