"""Block obviously unsafe outbound HTTP targets (RFC 1918, loopback, link-local, metadata)."""

from __future__ import annotations

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


def assert_http_url_allowed(url: str, *, purpose: str = "HTTP Request") -> None:
    """
    Resolve the request hostname and reject blocked addresses before ``httpx`` runs.

    Covers numeric IPs directly and all ``socket.getaddrinfo`` results for hostnames.
    Redirect targets are not re-checked (see node ``follow_redirects``).
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
        return

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        # Offline / test hosts may not resolve here; httpx will fail the connection if bogus.
        logger.warning(
            "%s DNS lookup failed for host=%r url=%r (%s); skipping IP blocklist for hostname",
            purpose,
            host,
            url[:500],
            e,
        )
        return

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
