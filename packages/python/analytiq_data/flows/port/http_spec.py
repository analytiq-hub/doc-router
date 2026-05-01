from __future__ import annotations

from typing import Any

from .properties import iter_integration_parameter_tree


def pick_primary_routing(description: dict[str, Any]) -> dict[str, Any] | None:
    for p in iter_integration_parameter_tree(description):
        r = p.get("routing")
        if not isinstance(r, dict):
            continue
        req = r.get("request")
        if isinstance(req, dict) and (req.get("method") or req.get("url")):
            return r
    return None


def build_http_request_spec(
    description: dict[str, Any], warnings: list[str]
) -> dict[str, Any] | None:
    """Map declarative routing + requestDefaults onto http_request_v1-shaped JSON."""

    routing = pick_primary_routing(description)
    if routing is None:
        return None

    rd = description.get("requestDefaults") or {}
    if not isinstance(rd, dict):
        rd = {}

    req = routing.get("request") or {}
    if not isinstance(req, dict):
        req = {}

    method_raw = req.get("method") or "GET"
    method = str(method_raw).strip().upper() if method_raw else "GET"
    url = req.get("url") or ""
    url = str(url)
    if url.startswith("="):
        warnings.append(
            "expression URL: stripped leading '='; may need manual Jinja templating"
        )
        url = url[1:].strip()

    base = str(rd.get("baseURL") or "").rstrip("/")
    if base and url and not url.startswith("http"):
        url = f"{base}/{url.lstrip('/')}"

    spec: dict[str, Any] = {"method": method, "url": url}

    headers: dict[str, str] = {}
    h0 = rd.get("headers")
    if isinstance(h0, dict):
        for k, v in h0.items():
            if v is not None:
                headers[str(k)] = str(v)
    h1 = req.get("headers")
    if isinstance(h1, dict):
        for k, v in h1.items():
            if isinstance(v, str):
                headers[str(k)] = v
            elif isinstance(v, list) and v and isinstance(v[0], str):
                headers[str(k)] = v[0]
    if headers:
        spec["headers"] = headers

    qs = req.get("qs")
    if isinstance(qs, dict) and qs:
        spec["query_params"] = {str(k): v for k, v in qs.items()}

    body = req.get("body")
    if body is not None:
        spec["body"] = body

    out = routing.get("output")
    if isinstance(out, dict):
        pr = out.get("postReceive") or []
        if isinstance(pr, list):
            for step in pr:
                if not isinstance(step, dict):
                    continue
                if (
                    step.get("type") == "rootProperty"
                    and step.get("properties") is not None
                ):
                    pass
                if step.get("type") == "rootProperty" and step.get("property"):
                    spec["response_jmespath"] = str(step["property"])
                    break

    return spec
