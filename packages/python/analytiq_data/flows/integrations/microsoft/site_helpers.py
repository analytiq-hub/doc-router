"""SharePoint REST API v2.0 URL helpers (n8n ``/_api/v2.0/`` parity, not Microsoft Graph)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urlparse

from analytiq_data.flows.credential_runtime import normalize_sharepoint_subdomain

_DEFAULT_SITE = "root"
_SITE_COLLECTION_PATH_RE = re.compile(r"^/(?:sites|teams)/[^/]+", re.IGNORECASE)
_SITE_GUID_RE = re.compile(r"^[0-9a-f-]{20,}$", re.IGNORECASE)


def _looks_like_site_guid(value: str) -> bool:
    return bool(_SITE_GUID_RE.match(value.replace(" ", "")))


def _bare_site_slug_to_path(value: str) -> str:
    """Map ``GreenieRE`` → ``/sites/GreenieRE`` (common team site URL slug)."""

    s = value.strip()
    if not s or s.startswith("/") or s.lower().startswith(("sites/", "teams/")):
        return s
    if ".sharepoint.com" in s.lower() or _looks_like_site_guid(s):
        return s
    return f"/sites/{s}"


def _site_collection_path_from_url_path(path: str) -> str:
    """Extract ``/sites/Name`` or ``/teams/Name`` from a SharePoint browser URL path."""

    normalized = (path or "/").strip() or "/"
    match = _SITE_COLLECTION_PATH_RE.match(normalized)
    if match:
        return match.group(0)
    return normalized


def normalize_site_id(raw: Any) -> str:
    """Site id, ``hostname:/sites/...`` composite, SharePoint URL, or ``root``."""

    s = str(raw or "").strip()
    if not s or s.lower() in (_DEFAULT_SITE, "/"):
        return _DEFAULT_SITE
    if s.startswith("http://") or s.startswith("https://"):
        parsed = urlparse(s)
        host = parsed.netloc.strip()
        path = _site_collection_path_from_url_path(parsed.path.strip() or "/")
        if not host:
            return _DEFAULT_SITE
        if path in ("/", ""):
            return _DEFAULT_SITE
        return f"{host}:{path}"
    if s.lower().startswith(("sites/", "teams/")):
        return f"/{s}"
    return _bare_site_slug_to_path(s)


def sharepoint_host_slug_from_subdomain(subdomain: str) -> str:
    """Tenant slug for ``https://{slug}.sharepoint.com`` (from credential subdomain field)."""

    slug = normalize_sharepoint_subdomain(subdomain)
    if not slug:
        raise RuntimeError(
            "Microsoft SharePoint credential subdomain is required. "
            'Use the slug from your SharePoint URL (e.g. "tenant123" in '
            "https://tenant123.sharepoint.com)."
        )
    return slug


def sharepoint_tenant_rest_api_base(subdomain: str) -> str:
    """Tenant-level SharePoint REST v2.0 base (site search, etc.)."""

    host = sharepoint_host_slug_from_subdomain(subdomain)
    return f"https://{host}.sharepoint.com/_api/v2.0"


def sharepoint_rest_api_base(subdomain: str, site_id: str) -> str:
    """Site-scoped SharePoint REST v2.0 base for drive, lists, and site metadata."""

    host = sharepoint_host_slug_from_subdomain(subdomain)
    sid = normalize_site_id(site_id)
    if sid == _DEFAULT_SITE:
        return f"https://{host}.sharepoint.com/_api/v2.0/sites/root"
    lower = sid.lower()
    if ".sharepoint.com" in lower:
        if ":" in sid:
            hostname, path = sid.split(":", 1)
            path = path.strip()
            if not path.startswith("/"):
                path = f"/{path}"
            return f"https://{hostname.strip()}{path}/_api/v2.0"
        return f"https://{sid}/_api/v2.0"
    if sid.startswith("/"):
        return f"https://{host}.sharepoint.com{sid}/_api/v2.0"
    if sid.startswith("sites/"):
        return f"https://{host}.sharepoint.com/{sid}/_api/v2.0"
    return f"https://{host}.sharepoint.com/_api/v2.0/sites/{quote(sid, safe='')}"


def site_drive_delta_latest(site_base: str) -> str:
    return f"{site_base.rstrip('/')}/drive/root/delta?token=latest"


def site_drive_delta_root(site_base: str) -> str:
    return f"{site_base.rstrip('/')}/drive/root/delta"


def site_search_query_path(query: str) -> str:
    escaped = str(query or "").replace("'", "''")
    return f"/drive/root/search(q='{escaped}')"


def site_encoded_drive_item_content_path(parent_id: str, file_name: str) -> str:
    return f"/drive/items/{parent_id}:/{quote(str(file_name), safe='')}:/content"
