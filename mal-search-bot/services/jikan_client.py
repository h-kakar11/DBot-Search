"""Async wrapper around the Jikan API (https://docs.api.jikan.moe/).

Provides a rate-limited, retrying HTTP client for the endpoints needed by
mal-search-bot: anime search, manga search, seasonal anime, and full
anime/manga lookups by ID.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Optional

import aiohttp

logger = logging.getLogger("mal_search_bot.services.jikan_client")


class JikanAPIError(Exception):
    """Raised when the Jikan API returns an error or cannot be reached."""


class RateLimiter:
    """Leaky-bucket style rate limiter for Jikan's request limits.

    Tracks request timestamps in rolling windows and awaits until a new
    request is allowed, respecting both a short-window limit (e.g. 3 req/sec)
    and a longer rolling-minute limit (e.g. 60 req/min).
    """

    def __init__(self, per_second: float = 3, per_minute: int = 60) -> None:
        """Initialize the limiter with per-second and per-minute request caps."""
        self.per_second = per_second
        self.per_minute = per_minute
        self._second_window: deque[float] = deque()
        self._minute_window: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a new outgoing request is permitted under both limits."""
        async with self._lock:
            while True:
                now = time.monotonic()
                self._evict(self._second_window, now, 1.0)
                self._evict(self._minute_window, now, 60.0)

                wait_times = []
                if len(self._second_window) >= self.per_second:
                    wait_times.append(1.0 - (now - self._second_window[0]))
                if len(self._minute_window) >= self.per_minute:
                    wait_times.append(60.0 - (now - self._minute_window[0]))

                if not wait_times:
                    break

                await asyncio.sleep(max(wait_times))

            now = time.monotonic()
            self._second_window.append(now)
            self._minute_window.append(now)

    @staticmethod
    def _evict(window: deque[float], now: float, span: float) -> None:
        """Drop timestamps older than `span` seconds from the front of `window`."""
        while window and now - window[0] >= span:
            window.popleft()


class JikanClient:
    """Thin async wrapper around the Jikan v4 API with rate limiting and retries."""

    def __init__(
        self,
        base_url: str = "https://api.jikan.moe/v4",
        rate_limit_per_second: float = 3,
        rate_limit_per_minute: int = 60,
        max_retries: int = 3,
    ) -> None:
        """Configure the client. Call `start()` before making requests."""
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._rate_limiter = RateLimiter(rate_limit_per_second, rate_limit_per_minute)
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Create the shared aiohttp session. Call once during bot startup."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        """Close the shared aiohttp session. Call once during bot shutdown."""
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def _request(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        """Perform a rate-limited GET request with 429/5xx retry handling.

        Raises:
            JikanAPIError: If the session isn't started, the request keeps
                failing past `max_retries`, or the API returns an unexpected
                non-2xx/404 status.
        """
        if self._session is None or self._session.closed:
            raise JikanAPIError("Jikan client session is not started.")

        url = f"{self.base_url}{path}"
        attempt = 0
        backoff = 1.0

        while True:
            attempt += 1
            await self._rate_limiter.acquire()

            try:
                async with self._session.get(url, params=params) as resp:
                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After")
                        try:
                            delay = float(retry_after) if retry_after else backoff
                        except ValueError:
                            delay = backoff
                        logger.warning(
                            "Jikan rate limited (429) on %s, retrying after %.1fs", url, delay
                        )
                        await asyncio.sleep(delay)
                        continue

                    if 500 <= resp.status < 600:
                        if attempt > self.max_retries:
                            raise JikanAPIError(
                                f"Jikan API returned {resp.status} for {url} after "
                                f"{attempt} attempts."
                            )
                        logger.warning(
                            "Jikan server error %s on %s, retrying in %.1fs (attempt %d/%d)",
                            resp.status,
                            url,
                            backoff,
                            attempt,
                            self.max_retries,
                        )
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue

                    if resp.status == 404:
                        return None

                    if resp.status != 200:
                        raise JikanAPIError(
                            f"Jikan API returned unexpected status {resp.status} for {url}."
                        )

                    return await resp.json()

            except asyncio.TimeoutError as exc:
                if attempt > self.max_retries:
                    raise JikanAPIError(f"Jikan API request to {url} timed out.") from exc
                logger.warning(
                    "Jikan request timeout on %s, retrying in %.1fs (attempt %d/%d)",
                    url,
                    backoff,
                    attempt,
                    self.max_retries,
                )
                await asyncio.sleep(backoff)
                backoff *= 2
            except aiohttp.ClientError as exc:
                if attempt > self.max_retries:
                    raise JikanAPIError(f"Jikan API request to {url} failed: {exc}") from exc
                logger.warning(
                    "Jikan client error on %s (%s), retrying in %.1fs (attempt %d/%d)",
                    url,
                    exc,
                    backoff,
                    attempt,
                    self.max_retries,
                )
                await asyncio.sleep(backoff)
                backoff *= 2

    async def search_anime(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for anime by name. Returns a list of result entries (possibly empty)."""
        data = await self._request("/anime", params={"q": query, "limit": limit})
        if not data:
            return []
        return data.get("data", [])

    async def search_manga(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for manga by name. Returns a list of result entries (possibly empty)."""
        data = await self._request("/manga", params={"q": query, "limit": limit})
        if not data:
            return []
        return data.get("data", [])

    async def get_seasonal(self, year: int, season: str) -> list[dict[str, Any]]:
        """Fetch the full seasonal anime list for the given year/season."""
        data = await self._request(f"/seasons/{year}/{season}")
        if not data:
            return []
        return data.get("data", [])

    async def get_full_anime(self, anime_id: int) -> Optional[dict[str, Any]]:
        """Fetch full details for a single anime by MAL ID, or None if not found."""
        data = await self._request(f"/anime/{anime_id}/full")
        if not data:
            return None
        return data.get("data")

    async def get_full_manga(self, manga_id: int) -> Optional[dict[str, Any]]:
        """Fetch full details for a single manga by MAL ID, or None if not found."""
        data = await self._request(f"/manga/{manga_id}/full")
        if not data:
            return None
        return data.get("data")
