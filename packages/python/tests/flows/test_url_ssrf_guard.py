"""Tests for outbound HTTP SSRF guard (`url_ssrf_guard`)."""

from __future__ import annotations

import asyncio

import pytest

from analytiq_data.flows.url_ssrf_guard import validate_http_url_allowed, validate_http_url_allowed_async


def test_blocks_loopback_ipv4() -> None:
    with pytest.raises(RuntimeError, match="blocked"):
        validate_http_url_allowed("http://127.0.0.1:8080/path")


def test_blocks_private_ipv4() -> None:
    with pytest.raises(RuntimeError, match="blocked"):
        validate_http_url_allowed("https://10.0.0.1/")


def test_blocks_metadata_link_local_ipv4() -> None:
    with pytest.raises(RuntimeError, match="blocked"):
        validate_http_url_allowed("http://169.254.169.254/latest/meta-data/")


def test_blocks_localhost_hostname() -> None:
    with pytest.raises(RuntimeError, match="localhost"):
        validate_http_url_allowed("http://localhost/foo")


def test_allows_public_literal_ipv4() -> None:
    """No DNS; ensures blocklist does not reject all outbound traffic."""

    validate_http_url_allowed("http://8.8.8.8/", purpose="test")


def test_async_allows_public_literal_ipv4() -> None:
    """Async guard matches literal-IP shortcut (no executor DNS)."""

    async def _run() -> None:
        await validate_http_url_allowed_async("http://8.8.8.8/", purpose="test")

    asyncio.run(_run())


def test_async_blocks_loopback_hostname() -> None:
    async def _run() -> None:
        await validate_http_url_allowed_async("http://localhost/foo")

    with pytest.raises(RuntimeError, match="localhost"):
        asyncio.run(_run())
