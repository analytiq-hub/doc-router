"""SharePoint REST API v2.0 URL helpers (n8n ``/_api/v2.0/`` parity, not Microsoft Graph)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlparse

from analytiq_data.flows.credential_runtime import normalize_sharepoint_subdomain

_DEFAULT_SITE = "root"


def normalize_site_id(raw: Any) -> str:
    """Site id, ``hostname:/sites/...`` composite, SharePoint URL, or ``root``."""

    s = str(raw or "").strip()
    if not s or s.lower() in (_DEFAULT_SITE, "/"):
        return _DEFAULT_SITE
    if s.startswith("http://") or s.startswith("https://"):
        parsed = urlparse(s)
        host = parsed.netloc.strip()
        path = parsed.path.strip() or "/"
        if not host:
            return _DEFAULT_SITE
        return f"{host}:{path}"
    return s


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
