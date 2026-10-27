"""The local ETag cache (BEHAVIOR 10).

The cache is on by default: an in-memory LRU of 256 entries and 32 MiB. For a
stored entry the client sends ``If-None-Match`` with the ETag exactly as
received, and a ``304 Not Modified`` answer returns the stored body. Entries
are keyed by the full URL plus a hash of the API key (never the key itself),
so keyless and keyed entries never mix.

The SDK is a private cache: it honours ``max-age`` (which the API sets to 0,
so every call revalidates) and ignores ``s-maxage`` and
``stale-while-revalidate``, which are for the edge. A ``no-store`` response is
never stored.

To share a cache across processes, implement :class:`Cache` over your own
store and pass it as ``Client(cache=...)``. Pass ``cache=False`` to disable
caching.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = ["DEFAULT_MAX_BYTES", "DEFAULT_MAX_ENTRIES", "Cache", "CacheEntry", "MemoryCache"]

DEFAULT_MAX_ENTRIES = 256
DEFAULT_MAX_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class CacheEntry:
    """One stored response.

    Attributes:
        body: The response body, as received.
        etag: The ``ETag`` header, byte for byte (``W/`` included).
        headers: The response headers, as ``(name, value)`` pairs.
        stored_at: When the entry was stored or last revalidated (Unix seconds).
        max_age: The ``max-age`` freshness lifetime in seconds, if any.
    """

    body: bytes
    etag: str | None
    headers: tuple[tuple[str, str], ...]
    stored_at: float
    max_age: float | None = None

    def is_fresh(self, now: float) -> bool:
        """Whether the entry may be served without revalidating."""
        return self.max_age is not None and self.max_age > 0 and now - self.stored_at < self.max_age


@runtime_checkable
class Cache(Protocol):
    """A store for cached responses. Implementations must be thread-safe.

    Methods are synchronous and should be fast; both :class:`Client` and
    :class:`AsyncClient` call them inline.
    """

    def get(self, key: str) -> CacheEntry | None:
        """Return the entry stored under ``key``, if any."""
        ...

    def set(self, key: str, entry: CacheEntry) -> None:
        """Store ``entry`` under ``key``, replacing any previous one."""
        ...

    def delete(self, key: str) -> None:
        """Remove the entry under ``key``, if any."""
        ...


class MemoryCache:
    """A thread-safe in-memory LRU cache bounded by entries and bytes."""

    def __init__(
        self, max_entries: int = DEFAULT_MAX_ENTRIES, max_bytes: int = DEFAULT_MAX_BYTES
    ) -> None:
        """Create an empty cache holding at most ``max_entries`` / ``max_bytes``."""
        if max_entries < 1 or max_bytes < 1:
            raise ValueError("cache bounds must be positive")
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def __len__(self) -> int:
        """The number of stored entries."""
        return len(self._entries)

    @property
    def size_bytes(self) -> int:
        """The total size of the stored bodies."""
        return self._bytes

    def get(self, key: str) -> CacheEntry | None:
        """Return the entry under ``key`` and mark it most recently used."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
            return entry

    def set(self, key: str, entry: CacheEntry) -> None:
        """Store ``entry``, evicting the least recently used to stay in bounds."""
        size = len(entry.body)
        with self._lock:
            self._remove(key)
            if size > self.max_bytes:
                return
            self._entries[key] = entry
            self._bytes += size
            while len(self._entries) > self.max_entries or self._bytes > self.max_bytes:
                oldest = next(iter(self._entries))
                self._remove(oldest)

    def delete(self, key: str) -> None:
        """Remove the entry under ``key``, if any."""
        with self._lock:
            self._remove(key)

    def clear(self) -> None:
        """Remove every entry."""
        with self._lock:
            self._entries.clear()
            self._bytes = 0

    def _remove(self, key: str) -> None:
        old = self._entries.pop(key, None)
        if old is not None:
            self._bytes -= len(old.body)
