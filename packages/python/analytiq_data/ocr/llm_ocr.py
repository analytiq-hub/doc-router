"""
LLM OCR: send the PDF to a vision/PDF-capable LiteLLM model and persist Mistral-shaped JSON.

Output shape: ``{ "provider", "model", "pages": [ { "index", "markdown" }, ... ] }``.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import litellm
import analytiq_data as ad
from litellm.utils import supports_pdf_input

from analytiq_data.llm.llm import _litellm_acompletion_with_retry

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You extract text from PDF documents. Output a single JSON object with this exact shape:\n"
    '{"pages":[{"index":0,"markdown":"..."}, ...]}\n'
    "Rules: index is 0-based page order. markdown is GitHub-flavored markdown preserving headings, "
    "lists, and tables as markdown tables. Use one page object per PDF page when possible; if you "
    "cannot split pages, use a single page with index 0 containing the full document. Output JSON only, "
    "no markdown code fences or commentary."
)

# Long OCR runs: allow large markdown output (LiteLLM / provider caps still apply).
_LLM_OCR_MAX_TOKENS = 32768


def _message_content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
                elif "text" in block:
                    parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def _normalize_pages(parsed: Any, fallback: str) -> list[dict[str, Any]]:
    pages = None
    if isinstance(parsed, dict):
        pages = parsed.get("pages")
    if not isinstance(pages, list) or not pages:
        return [{"index": 0, "markdown": fallback}]
    out: list[dict[str, Any]] = []
    for i, p in enumerate(pages):
        if isinstance(p, dict):
            md = p.get("markdown")
            if md is None:
                md = json.dumps(p, ensure_ascii=False)
            else:
                md = str(md)
            idx = p.get("index", i)
            try:
                idx_int = int(idx)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                idx_int = i
            out.append({"index": idx_int, "markdown": md})
        elif isinstance(p, str):
            out.append({"index": i, "markdown": p})
    return out if out else [{"index": 0, "markdown": fallback}]


def _parse_llm_ocr_response(raw: str) -> list[dict[str, Any]]:
    text = _strip_json_fences(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [{"index": 0, "markdown": raw}]
    return _normalize_pages(data, raw)


async def _assert_llm_ocr_provider_and_model(
    analytiq_client,
    provider_name: str,
    model: str,
) -> tuple[str, str | None, str | None, str | None, str]:
    """
    Validate ``llm_providers`` (name, enabled, model list) and that ``model`` maps to the same
    LiteLLM provider row. Returns (api_key, row_litellm).
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    doc = await db.llm_providers.find_one({"name": provider_name})
    if doc is None:
        raise ValueError(f"LLM provider {provider_name!r} is not configured")
    if not doc.get("enabled"):
        raise ValueError(f"LLM provider {provider_name!r} is disabled")
    enabled = doc.get("litellm_models_enabled") or []
    if model not in enabled:
        raise ValueError(f"Model {model!r} is not enabled for provider {provider_name!r}")
    row_litellm = doc.get("litellm_provider")
    if not row_litellm:
        raise ValueError(f"LLM provider {provider_name!r} has no litellm_provider field")
    model_litellm = ad.llm.get_llm_model_provider(model)
    if model_litellm is None:
        raise ValueError(f"Model {model!r} is not recognized by LiteLLM")
    if model_litellm != row_litellm:
        raise ValueError(
            f"Model {model!r} maps to LiteLLM provider {model_litellm!r}, "
            f"but provider {provider_name!r} is configured as {row_litellm!r}"
        )
    if not supports_pdf_input(model, None):
        raise ValueError(
            f"Model {model!r} does not support PDF input; choose a vision/PDF-capable model for OCR"
        )

    api_key = await ad.llm.get_llm_key(analytiq_client, row_litellm)
    if not (api_key or "").strip():
        raise ValueError(
            f"LLM provider {provider_name!r} has no stored API key or credentials for OCR"
        )

    return api_key, row_litellm


def _build_pdf_user_content(
    pdf_bytes: bytes,
    *,
    litellm_provider: str,
    model: str,
) -> list[dict[str, Any]]:
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    data_url = f"data:application/pdf;base64,{b64}"
    user_blocks: list[dict[str, Any]] = []
    # Match chat PDF attachment rules in llm.py (xai: no file blocks).
    can_file = bool(supports_pdf_input(model, None)) and litellm_provider != "xai"
    if can_file:
        user_blocks.append({"type": "file", "file": {"file_data": data_url}})
    else:
        user_blocks.append({"type": "text", "text": f"pdf:\n{b64}"})
    user_blocks.append(
        {
            "type": "text",
            "text": (
                "Extract all text from the attached PDF. Return JSON only as specified in the system message."
            ),
        }
    )
    return user_blocks


async def run_llm_ocr_pdf(
    analytiq_client,
    pdf_bytes: bytes,
    *,
    provider_name: str,
    model: str,
) -> dict[str, Any]:
    """
    Run OCR via LiteLLM using the organization's configured provider name and model id.

    Returns the canonical LLM OCR JSON (``provider``, ``model``, ``pages``).
    """
    if analytiq_client is None:
        raise ValueError("LLM OCR requires an active analytiq client")
    if not pdf_bytes:
        raise ValueError("LLM OCR requires non-empty PDF bytes")

    api_key, row_litellm = await _assert_llm_ocr_provider_and_model(
        analytiq_client, provider_name, model
    )

    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": _build_pdf_user_content(
                pdf_bytes, litellm_provider=row_litellm, model=model
            ),
        },
    ]

    response_format: dict[str, str] | None = None
    try:
        if litellm.supports_response_schema(model=model):
            response_format = {"type": "json_object"}
    except Exception:
        response_format = None

    logger.info(
        "LLM OCR start provider_name=%s model=%s litellm_provider=%s json_mode=%s",
        provider_name,
        model,
        row_litellm,
        bool(response_format),
    )

    response = await _litellm_acompletion_with_retry(
        analytiq_client,
        model=model,
        messages=messages,
        api_key=api_key,
        response_format=response_format,
        use_prompt_caching=False,
        max_tokens=_LLM_OCR_MAX_TOKENS,
    )

    msg = response.choices[0].message
    raw = _message_content_text(getattr(msg, "content", None))
    if not (raw or "").strip():
        raise RuntimeError("LLM OCR returned empty content")

    pages = _parse_llm_ocr_response(raw)
    return {
        "provider": provider_name,
        "model": model,
        "pages": pages,
    }
