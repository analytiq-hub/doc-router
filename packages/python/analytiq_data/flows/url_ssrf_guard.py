"""Block obviously unsafe outbound HTTP targets (RFC 1918, loopback, link-local, metadata)."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata",
        "metadata.google.internal",
        "metadata.google",
    }
)


def _ip_is_blocked(addr: ipaddress._BaseAddress) -> bool:
    if addr.is_loopback or addr.is_private or addr.is_link_local:
        return True
    if addr.is_multicast or addr.is_unspecified:
        return True
    if addr.version == 4:
        first = int(addr) >> 24
        if first == 0:
            return True
    return False


def _http_hostname_to_resolve_or_done(url: str, purpose: str) -> str | None:
    """
    Parse URL and apply non-DNS checks.

    Returns ``None`` if validation is complete (public literal IP). Otherwise returns hostname
    for ``getaddrinfo`` (sync or executor-backed).
    """

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise RuntimeError(f"{purpose}: only http(s) URLs are allowed.")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise RuntimeError(f"{purpose}: URL has no hostname.")

    if host in _BLOCKED_HOSTNAMES:
        raise RuntimeError(f"{purpose}: hostname {host!r} is not allowed.")

    try:
        numeric = ipaddress.ip_address(host)
    except ValueError:
        numeric = None

    if numeric is not None:
        if _ip_is_blocked(numeric):
            raise RuntimeError(f"{purpose}: blocked destination IP {host}.")
        return None

    return host


def _check_resolved_addrs(host: str, url: str, purpose: str, infos: list[tuple]) -> None:
    if not infos:
        logger.warning("%s no addresses returned for host=%r url=%r; skipping hostname IP checks", purpose, host, url[:500])
        return

    for info in infos:
        sockaddr = info[4]
        addr_s = sockaddr[0]
        ip = ipaddress.ip_address(addr_s)
        if _ip_is_blocked(ip):
            raise RuntimeError(
                f"{purpose}: hostname {host!r} resolves to a blocked address ({ip}). "
                "Private, loopback, and link-local targets are not allowed."
            )


def validate_http_url_allowed(url: str, *, purpose: str = "HTTP Request") -> None:
    """
    Resolve the request hostname and reject blocked addresses before ``httpx`` runs.

    Covers numeric IPs directly and all ``socket.getaddrinfo`` results for hostnames.

    Performs **synchronous DNS** (`socket.getaddrinfo`), which blocks the thread. Prefer
    :func:`validate_http_url_allowed_async` inside asyncio contexts (FastAPI handlers, ``httpx``
    async hooks).

    When used as an ``httpx.AsyncClient`` **request** event hook, use the async variant;
    otherwise every outbound request can stall the event loop on DNS.

    Raises ``RuntimeError`` when the URL targets a blocked host or IP.
    """

    to_resolve = _http_hostname_to_resolve_or_done(url, purpose)
    if to_resolve is None:
        return

    try:
        infos = socket.getaddrinfo(to_resolve, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        # Offline / test hosts may not resolve here; httpx will fail the connection if bogus.
        logger.warning(
            "%s DNS lookup failed for host=%r url=%r (%s); skipping IP blocklist for hostname",
            purpose,
            to_resolve,
            url[:500],
            e,
        )
        return

    _check_resolved_addrs(to_resolve, url, purpose, infos)


async def validate_http_url_allowed_async(url: str, *, purpose: str = "HTTP Request") -> None:
    """Like :func:`validate_http_url_allowed` but resolves hostnames via a thread pool (non-blocking DNS).

    Raises ``RuntimeError`` when the URL targets a blocked host or IP.
    """

    to_resolve = _http_hostname_to_resolve_or_done(url, purpose)
    if to_resolve is None:
        return

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.run_in_executor(
            None,
            lambda h=to_resolve: socket.getaddrinfo(h, None, type=socket.SOCK_STREAM),
        )
    except socket.gaierror as e:
        logger.warning(
            "%s DNS lookup failed for host=%r url=%r (%s); skipping IP blocklist for hostname",
            purpose,
            to_resolve,
            url[:500],
            e,
        )
        return

    _check_resolved_addrs(to_resolve, url, purpose, infos)
