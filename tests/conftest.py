"""Shared fixtures: a recording mock transport and clients wired to it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from ensemble_weather import AsyncClient, Client

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

BODIES = Path(__file__).resolve().parent.parent / "spec" / "vectors" / "bodies"


def body(name: str) -> bytes:
    return (BODIES / name).read_bytes()


def json_body(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(body(name))
    return data


class Recorder:
    """A transport handler: queued responses out, requests recorded."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.queue: list[httpx.Response | Callable[[httpx.Request], httpx.Response]] = []

    def add(self, status: int = 200, *, name: str | None = None, **kwargs: Any) -> None:
        if name is not None:
            kwargs.setdefault("content", body(name))
            kwargs.setdefault("headers", {"Content-Type": "application/json"})
        self.queue.append(httpx.Response(status, **kwargs))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        item = self.queue.pop(0)
        return item(request) if callable(item) else item


@pytest.fixture(autouse=True)
def _no_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OUREA_API_KEY", raising=False)
    monkeypatch.delenv("OUREA_BASE_URL", raising=False)


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def make_client(recorder: Recorder) -> Iterator[Callable[..., Client]]:
    made: list[Client] = []

    def make(**kwargs: Any) -> Client:
        client = Client(transport=httpx.MockTransport(recorder), **kwargs)
        client._sleep = lambda _delay: None
        made.append(client)
        return client

    yield make
    for client in made:
        client.close()


@pytest.fixture
def make_async_client(recorder: Recorder) -> Callable[..., AsyncClient]:
    def make(**kwargs: Any) -> AsyncClient:
        client = AsyncClient(transport=httpx.MockTransport(recorder), **kwargs)

        async def no_sleep(_delay: float) -> None:
            return None

        client._sleep = no_sleep
        return client

    return make
