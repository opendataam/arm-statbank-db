"""Minimal client for the Statbank PXWeb API v1 (``/api/v1/{lang}/ArmStatBank/...``).

The statbank-parser exports were downloaded from the PXWeb *web interface* in English.
This client uses the PXWeb *JSON API* to read the same tables in Armenian. Both
interfaces share variable codes and value codes, so labels can be joined by code.

API reference: https://www.scb.se/en/services/open-data-api/api-for-the-statistical-database/
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from urllib.parse import quote, unquote

import requests

from .config import API_BASE, DATABASE_ID, STATBANK_BASE

log = logging.getLogger(__name__)

USER_AGENT = "armstat-db/0.1 (+https://github.com/opendataam/arm-statbank-db)"


def web_url_to_api_path(url: str) -> str:
    """Convert a PXWeb web-interface URL into an API path relative to the database.

    >>> web_url_to_api_path(
    ...     "https://statbank.armstat.am/pxweb/en/ArmStatBank/"
    ...     "ArmStatBank__1 Econnomy and finance__12 Consumer Prices/EF-cpi-mi1.px/")
    '1 Econnomy and finance/12 Consumer Prices/EF-cpi-mi1.px'
    """
    url = unquote(url).rstrip("/")
    marker = f"/{DATABASE_ID}/"
    if marker not in url:
        raise ValueError(f"Not a {DATABASE_ID} URL: {url}")
    tail = url.split(marker, 1)[1]
    folder, _, table = tail.rpartition("/")
    if not table.lower().endswith(".px"):
        raise ValueError(f"URL does not point to a .px table: {url}")
    segments = [s for s in folder.split("__") if s]
    if segments and segments[0] == DATABASE_ID:
        segments = segments[1:]
    return "/".join([*segments, table])


def api_path_to_web_url(api_path: str, lang: str) -> str:
    """Inverse of :func:`web_url_to_api_path` (unquoted, as published by the parser)."""
    *folders, table = api_path.split("/")
    folder = "__".join([DATABASE_ID, *folders])
    return f"{STATBANK_BASE}/pxweb/{lang}/{DATABASE_ID}/{folder}/{table}/"


class RateLimiter:
    """Sliding-window limiter shared by all threads of a client.

    PXWeb's default limit is 30 requests per 10 seconds per IP; HTTP 429 is returned above it.
    """

    def __init__(self, max_calls: int = 25, period: float = 10.0):
        self.max_calls = max_calls
        self.period = period
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def wait(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.period:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                sleep_for = self.period - (now - self._calls[0]) + 0.05
            time.sleep(sleep_for)


class PxWebClient:
    """Small, polite HTTP client with a shared rate limit and retries."""

    def __init__(self, base: str = API_BASE, max_calls: int = 25, period: float = 10.0,
                 retries: int = 6, timeout: tuple[float, float] = (10, 120)):
        self.base = base.rstrip("/")
        self.limiter = RateLimiter(max_calls, period)
        self.retries = retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def url(self, lang: str, path: str = "") -> str:
        quoted = "/".join(quote(p, safe=",()'") for p in path.split("/") if p)
        return f"{self.base}/{lang}/{DATABASE_ID}/{quoted}"

    def _request(self, method: str, url: str, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 1):
            self.limiter.wait()
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:  # ValueError: bad JSON
                last_exc = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and 400 <= status < 500 and status != 429:
                    break
                wait = min(60, 5 * attempt)
                log.warning("%s %s failed (%s), retry %d in %ss", method, url, exc, attempt, wait)
                time.sleep(wait)
        raise RuntimeError(f"{method} {url} failed: {last_exc}") from last_exc

    def list(self, lang: str, path: str = "") -> list[dict]:
        """List child nodes of a folder: ``[{id, type: 'l'|'t', text, updated?}]``."""
        return self._request("GET", self.url(lang, path))

    def metadata(self, lang: str, path: str) -> dict:
        """Table metadata: ``{title, variables: [{code, text, values, valueTexts, ...}]}``."""
        return self._request("GET", self.url(lang, path))

    def jsonstat(self, lang: str, path: str, query: list[dict]) -> dict:
        body = {"query": query, "response": {"format": "json-stat2"}}
        return self._request("POST", self.url(lang, path), json=body)

    def walk(self, lang: str, path: str = ""):
        """Depth-first traversal yielding ``(parent_path, position, node)`` tuples."""
        for position, node in enumerate(self.list(lang, path)):
            yield path, position, node
            if node.get("type") == "l":
                child = f"{path}/{node['id']}" if path else node["id"]
                yield from self.walk(lang, child)


def head_query(metadata: dict) -> list[dict]:
    """A query selecting the first value of every variable.

    The JSON-stat response of such a query is tiny but still contains table-level
    metadata (label, contents, unit, notes, source, update time) in the requested language.
    """
    return [
        {"code": v["code"], "selection": {"filter": "item", "values": v["values"][:1]}}
        for v in metadata.get("variables", [])
        if v.get("values")
    ]
