"""Thin async wrapper around the Jikan (https://docs.api.jikan.moe/) REST API.

Jikan is an unofficial, free REST wrapper around MyAnimeList that requires no
API key / OAuth. Its public instance enforces a rate limit of roughly
3 requests/second and 60 requests/minute, so all requests here go through a
small in-process rate limiter, and 429/5xx responses are retried with
backoff.
"""

import asyncio
import time
from collections import deque
from typing import Any, Optional

import aiohttp


class JikanAPIError(Exception):
    """Raised when a Jikan request ultimately fails (timeout, 5xx, rate limit exhausted, ...)."""


class JikanNotFoundError(JikanAPIError):
    """Raised when Jikan returns a 404 (e.g. unknown MAL id or no search matches)."""


class RateLimiter:
    """Simple leaky-bucket limiter respecting both a per-second and per-minute cap."""

    def __init__(self, max_per_second: int = 3, max_per_minute: int = 60):
        self.max_per_second = max_per_second
        self.max_per_minute = max_per_minute
        self._lock = asyncio.Lock()
        self._timestamps: deque = deque()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                # Drop timestamps older than the 60s window.
                while self._timestamps and now - self._timestamps[0] > 60:
                    self._timestamps.popleft()

                if len(self._timestamps) >= self.max_per_minute:
                    await asyncio.sleep(60 - (now - self._timestamps[0]))
                    continue

                recent = [t for t in self._timestamps if now - t < 1]
                if len(recent) >= self.max_per_second:
                    await asyncio.sleep(1 - (now - recent[0]))
                    continue

                self._timestamps.append(now)
                return


class JikanClient:
    BASE_URL = "https://api.jikan.moe/v4"

    def __init__(self, max_retries: int = 3):
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = RateLimiter()
        self.max_retries = max_retries

    async def start(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, path: str, params: Optional[dict] = None) -> dict:
        if self._session is None or self._session.closed:
            raise JikanAPIError("Jikan client session is not started")

        url = f"{self.BASE_URL}{path}"
        attempt = 0
        while True:
            await self._rate_limiter.acquire()
            try:
                async with self._session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 404:
                        raise JikanNotFoundError(f"{path} returned 404")

                    if resp.status == 429:
                        attempt += 1
                        if attempt > self.max_retries:
                            raise JikanAPIError("Rate limited by Jikan too many times")
                        retry_after = float(resp.headers.get("Retry-After", 1))
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status >= 500:
                        attempt += 1
                        if attempt > self.max_retries:
                            raise JikanAPIError(f"Jikan server error: {resp.status}")
                        await asyncio.sleep(2 ** attempt)
                        continue

                    if resp.status != 200:
                        raise JikanAPIError(f"Unexpected Jikan status {resp.status} for {path}")

                    return await resp.json()
            except asyncio.TimeoutError as e:
                attempt += 1
                if attempt > self.max_retries:
                    raise JikanAPIError("Timed out contacting Jikan API") from e
                await asyncio.sleep(2 ** attempt)
            except aiohttp.ClientError as e:
                attempt += 1
                if attempt > self.max_retries:
                    raise JikanAPIError(f"Error contacting Jikan API: {e}") from e
                await asyncio.sleep(2 ** attempt)

    async def _get_paginated(
        self, path: str, params: Optional[dict] = None, max_pages: int = 3
    ) -> list:
        params = dict(params or {})
        results: list = []
        page = 1
        while page <= max_pages:
            params["page"] = page
            data = await self._request(path, params)
            results.extend(data.get("data", []))
            pagination = data.get("pagination") or {}
            if not pagination.get("has_next_page"):
                break
            page += 1
        return results

    # --- Public API ------------------------------------------------------

    async def search_anime(self, query: str, limit: int = 10) -> list:
        data = await self._request("/anime", {"q": query, "limit": limit})
        return data.get("data", [])

    async def search_manga(self, query: str, limit: int = 10) -> list:
        data = await self._request("/manga", {"q": query, "limit": limit})
        return data.get("data", [])

    async def get_season(self, year: int, season: str, max_pages: int = 3) -> list:
        return await self._get_paginated(f"/seasons/{year}/{season}", max_pages=max_pages)

    async def get_upcoming(self, max_pages: int = 3) -> list:
        return await self._get_paginated("/seasons/upcoming", max_pages=max_pages)

    async def get_schedules(self, day: str, max_pages: int = 3) -> list:
        return await self._get_paginated("/schedules", {"filter": day}, max_pages=max_pages)

    async def get_anime_full(self, mal_id: int) -> dict:
        data = await self._request(f"/anime/{mal_id}/full")
        return data.get("data", {})
