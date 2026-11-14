"""Safe outbound fetch: domain allowlist, 25 MB size cap and timeouts."""
from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

MAX_BYTES = 25 * 1024 * 1024
TIMEOUT = (10, 60)  # connect, read (seconds)
MAX_REDIRECTS = 3

# Only these hosts, and their subdomains, may be fetched. This is what stops a crafted PDF link
# from making the server call an internal address (SSRF). nseindia.in is where NSE now serves
# attachments from, alongside nseindia.com.
ALLOWED_DOMAINS = ("bseindia.com", "nseindia.com", "nseindia.in", "screener.in", "yahoo.com", "tavily.com")


class FetchError(Exception):
    """The request could not be made, or was refused."""


class BlockedUrl(FetchError):
    """The URL is not on the allow-list."""


class TooLarge(FetchError):
    """The response is larger than the size cap."""


@dataclass(frozen=True)
class Fetched:
    url: str
    status: int
    content: bytes
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def text(self, encoding: str = "utf-8") -> str:
        return self.content.decode(encoding, errors="replace")

    def json(self) -> Any:
        return json.loads(self.content)


def check_url(url: str) -> str:
    """Return the URL if it may be fetched, otherwise raise BlockedUrl."""
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError as exc:
        raise BlockedUrl("invalid port") from exc
    if parts.scheme != "https" or not host or parts.username or parts.password or port not in (None, 443):
        raise BlockedUrl(f"only plain https URLs are allowed: {url[:80]}")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise BlockedUrl("IP addresses are not allowed")
    if not any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS):
        raise BlockedUrl(f"host not allowed: {host}")
    return url


def fetch(
    url: str,
    *,
    session: requests.Session | None = None,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    max_bytes: int = MAX_BYTES,
    timeout: tuple[float, float] = TIMEOUT,
) -> Fetched:
    """GET a URL on the allow-list. Every redirect hop is re-checked; the body is capped."""
    http = session or requests.Session()
    current = check_url(url)
    query = params
    try:
        for _ in range(MAX_REDIRECTS + 1):
            with http.get(
                current, headers=headers, params=query, stream=True, timeout=timeout, allow_redirects=False
            ) as resp:
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        raise FetchError("redirect without a location")
                    current, query = check_url(urljoin(current, location)), None
                    continue
                declared = resp.headers.get("content-length", "")
                if declared.isdigit() and int(declared) > max_bytes:
                    raise TooLarge(f"{declared} bytes exceeds the {max_bytes} byte cap")
                chunks: list[bytes] = []
                size = 0
                for chunk in resp.iter_content(65536):
                    size += len(chunk)
                    if size > max_bytes:
                        raise TooLarge(f"response is larger than the {max_bytes} byte cap")
                    chunks.append(chunk)
                return Fetched(current, resp.status_code, b"".join(chunks), dict(resp.headers))
    except requests.RequestException as exc:
        raise FetchError(f"{type(exc).__name__}: {str(exc)[:160]}") from exc
    raise FetchError("too many redirects")
