import asyncio
import analytiq_data as ad
import litellm
from litellm.utils import supports_pdf_input, supports_prompt_caching
import json
from datetime import datetime, UTC
from pydantic import BaseModel, create_model
from typing import Optional, Dict, Any, Union, List, Tuple
from collections import OrderedDict
import logging
from bson import ObjectId
import base64
import os
import re
import stamina
from fastapi.responses import StreamingResponse
from fastapi import HTTPException
from .llm_output_utils import process_llm_resp_content

logger = logging.getLogger(__name__)

# Drop unsupported provider/model params automatically (e.g., O-series temperature)
litellm.drop_params = True
# When thinking_blocks missing in assistant msg, drop thinking param (Anthropic + tools workaround)
litellm.modify_params = True

# Cache control directive for Anthropic/Bedrock prompt caching (ephemeral cache).
# Explicit 1h TTL requested for system prompt caching.
_PROMPT_CACHE_CONTROL = {"type": "ephemeral", "ttl": "1h"}
_DEFAULT_CACHE_BREAKPOINT_TTL = "5m"


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


LLM_REQUEST_TIMEOUT_SECS = _get_int_env("LLM_REQUEST_TIMEOUT_SECS", 300)  # 5 min

def _is_valid_json(s: str) -> bool:
    """Return True if s is a non-empty, parseable JSON string."""
    try:
        json.loads(s)
        return True
    except (ValueError, TypeError):
        return False


def _cache_breakpoint_ttl(cache_control: Optional[Dict[str, Any]]) -> str:
    """Return cache breakpoint TTL; default to 5m when not explicitly set."""
    if isinstance(cache_control, dict):
        ttl = cache_control.get("ttl")
        if isinstance(ttl, str) and ttl.strip():
            return ttl.strip()
    return _DEFAULT_CACHE_BREAKPOINT_TTL


def _append_cache_breakpoint(text: str, cache_control: Optional[Dict[str, Any]]) -> str:
    """
    Annotate a printed prompt component with a cache breakpoint marker.
    This affects only prompt logging/debug output, not model payload content.
    """
    ttl = _cache_breakpoint_ttl(cache_control)
    return f"{text.rstrip()}\n[cache_breakpoint ttl={ttl}]"


def _apply_prompt_caching(model: str, messages: list, *, tools: Optional[List[Dict]] = None) -> list:
    """
    When the model supports prompt caching, convert the first (system) message
    to content-block form with cache_control so the provider caches it.
    Anthropic requires ~1024+ tokens for caching; we always add the directive
    and let the API decide. Other providers ignore cache_control.

    Skip caching for Gemini/Vertex AI entirely: their CachedContent API has a
    minimum token requirement (1024 for Flash, 4096 for Pro). Our system prompts
    are often smaller, causing "Cached content is too small" errors. Claude and
    GPT do not have this restriction.
    """
    if not messages or not supports_prompt_caching(model=model):
        return messages
    try:
        _, provider, _, _ = litellm.get_llm_provider(model)
        if provider in ("gemini", "vertex_ai"):
            return messages
    except Exception:
        pass
    first = messages[0]
    if first.get("role") != "system":
        return messages
    content = first.get("content")
    if isinstance(content, str):
        # Single block with cache_control so the system prompt is cached
        cached_system = {
            "role": "system",
            "content": [
                {"type": "text", "text": content, "cache_control": _PROMPT_CACHE_CONTROL}
            ],
        }
        return [cached_system] + list(messages[1:])
    if isinstance(content, list):
        # Already blocks; add cache_control to the last text block (per Anthropic spec)
        blocks = list(content)
        for i in range(len(blocks) - 1, -1, -1):
            if isinstance(blocks[i], dict) and blocks[i].get("type") == "text":
                blocks[i] = {**blocks[i], "cache_control": _PROMPT_CACHE_CONTROL}
                break
        return [{"role": "system", "content": blocks}] + list(messages[1:])
    return messages


async def get_extracted_llm_text(analytiq_client, document_id: str) -> str | None:
    """
    Get extracted text from a document.

    For OCR-supported files, returns OCR text.
    For txt/md files, returns the original file content as text.
    For other non-OCR files, returns None.

    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID

    Returns:
        str | None: The extracted text, or None if file needs to be attached
    """
    # Get document info
    doc = await ad.common.doc.get_doc(analytiq_client, document_id)
    if not doc:
        return None

    file_name = doc.get("user_file_name", "")

    # Check if OCR is supported
    if ad.common.doc.ocr_supported(file_name):
        # OCR may be produced asynchronously; if it's not ready yet (or retrieval
        # temporarily fails), poll briefly before giving up.
        poll_every_s = 5
        max_steps = 6
        last_err: Exception | None = None
        for step in range(max_steps):
            try:
                text = await ad.ocr.get_ocr_text(analytiq_client, document_id)
                if isinstance(text, str) and text.strip():
                    return text
                last_err = None
            except Exception as e:
                last_err = e
                logger.debug(
                    f"get_ocr_text failed (step {step + 1}/{max_steps}) for document_id={document_id}; will retry",
                    exc_info=True,
                )

            if step < max_steps - 1:
                await asyncio.sleep(poll_every_s)

        if last_err is not None:
            logger.info(
                f"OCR/text not available after polling for document_id={document_id} (last error: {last_err})"
            )
        return None

    # For non-OCR files, check if it's a text file we can read
    if file_name:
        ext = os.path.splitext(file_name)[1].lower()
        if ext in {'.txt', '.md'}:
            # Get the original file and decode as text
            original_file = await ad.common.get_file_async(analytiq_client, doc["mongo_file_name"])
            if original_file and original_file["blob"]:
                try:
                    return original_file["blob"].decode("utf-8")
                except UnicodeDecodeError:
                    # Fallback to latin-1 if UTF-8 fails
                    return original_file["blob"].decode("latin-1")

    # For other files (csv, xls, xlsx), return None to indicate file attachment needed
    return None


async def get_file_attachment(analytiq_client, doc: dict, llm_provider: str, llm_model: str):
    """
    Get file attachment for LLM processing.

    Args:
        analytiq_client: The AnalytiqClient instance
        doc: Document dictionary
        llm_provider: LLM provider name
        llm_model: LLM model name

    Returns:
        File blob and file name, or None, None
    """
    file_name = doc.get("user_file_name", "")
    if not file_name:
        return None, None

    ext = os.path.splitext(file_name)[1].lower()

    # Check if model supports vision
    # Note: XAI doesn't support the complex file attachment format, so we exclude it here
    # XAI will use OCR text-only approach instead
    model_supports_vision = supports_pdf_input(llm_model, None)

    if model_supports_vision and doc.get("pdf_file_name"):
        # For vision-capable models, prefer PDF version
        pdf_file = await ad.common.get_file_async(analytiq_client, doc["pdf_file_name"])
        if pdf_file and pdf_file["blob"]:
            return pdf_file["blob"], doc["pdf_file_name"]

    # For CSV, Excel files, or when PDF not available, use original file
    if ext in {'.csv', '.xls', '.xlsx'} or not model_supports_vision:
        original_file = await ad.common.get_file_async(analytiq_client, doc["mongo_file_name"])
        if original_file and original_file["blob"]:
            return original_file["blob"], file_name

    return None, None

async def _load_pdf_blob(
    analytiq_client,
    doc: dict,
    doc_id_str: str,
    llm_provider: str,
    llm_model: str,
) -> Tuple[bytes, str]:
    """
    Load the best-available PDF bytes for LLM consumption.

    Prefers an explicit `pdf_file_name` blob, then falls back to the same
    file-attachment logic used for non-PDF models.
    """
    pdf_file_name = doc.get("pdf_file_name")
    upload_name = pdf_file_name or (doc.get("user_file_name") or "attachment")

    blob = None
    if pdf_file_name:
        pdf_file = await ad.common.get_file_async(analytiq_client, pdf_file_name)
        blob = pdf_file.get("blob") if pdf_file else None

    # If the explicit PDF blob isn't available, fall back to attachment logic.
    if not blob:
        blob, fname = await get_file_attachment(analytiq_client, doc, llm_provider, llm_model)
        if fname:
            upload_name = fname

    if not blob:
        raise Exception(
            f"LLM run failed: missing file blob for document {doc_id_str} "
            "(include.pdf is true)"
        )
    return blob, upload_name

def is_o_series_model(model_name: str) -> bool:
    """Return True for OpenAI O-series models (e.g., o1, o1-mini, o3, o4-mini)."""
    if not model_name:
        return False
    name = model_name.strip().lower()
    # O-series models start with 'o' (not to be confused with gpt-4o which starts with 'gpt')
    return name.startswith("o") and not name.startswith("gpt")

def get_temperature(model: str) -> float:
    """
    Get the temperature setting for a given model.
    
    Args:
        model: The model name
        
    Returns:
        float: Temperature value (1.0 for o-series models or gemini models, 0.1 otherwise)
    """
    if not model:
        return 0.1
    
    model_lower = model.strip().lower()
    
    # O-series models require temperature=1
    if is_o_series_model(model):
        return 1.0
    
    # Gemini models use temperature=1
    if model_lower.startswith("gemini/") or "gemini" in model_lower:
        return 1.0
    
    # Default temperature for other models
    return 0.1

def is_retryable_error(exception) -> bool:
    """
    Check if an exception is retryable based on error patterns.
    
    Args:
        exception: The exception to check
        
    Returns:
        bool: True if the exception is retryable, False otherwise
    """
    # First check if it's an exception
    if not isinstance(exception, Exception):
        return False

    # Explicitly treat asyncio.TimeoutError as retryable
    import asyncio as _asyncio  # local import to avoid circulars in some environments
    if isinstance(exception, _asyncio.TimeoutError):
        return True

    error_message = str(exception).lower()
    
    # Check for specific retryable error patterns
    retryable_patterns = [
        "503",
        "model is overloaded",
        "unavailable",
        "rate limit",
        "timeout",
        "connection error",
        "internal server error",
        "service unavailable",
        "temporarily unavailable"
    ]
    
    for pattern in retryable_patterns:
        if pattern in error_message:
            return True
    
    return False

def _extract_thinking_from_response(message: Any) -> str | None:
    """
    Extract thinking/reasoning text from LLM response for display.
    Uses reasoning_content (all providers) or concatenates thinking_blocks (Anthropic).
    """
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning and isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    blocks = getattr(message, "thinking_blocks", None)
    if blocks and isinstance(blocks, list):
        parts = []
        for b in blocks:
            if isinstance(b, dict) and b.get("thinking"):
                parts.append(str(b["thinking"]).strip())
            elif hasattr(b, "thinking"):
                parts.append(str(getattr(b, "thinking", "")).strip())
        if parts:
            return "\n\n".join(p for p in parts if p)
    return None


@stamina.retry(on=is_retryable_error)
async def _litellm_acompletion_with_retry(
    analytiq_client,
    model: str,
    messages: list,
    api_key: str,
    response_format: Optional[Dict] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[Union[str, Dict]] = None,
    thinking: Optional[Dict] = None,
    use_prompt_caching: bool = False,
    max_tokens: Optional[int] = None,
):
    """
    Make an LLM call with stamina retry mechanism.

    Provider-specific params (AWS credentials, GCP credentials, Azure Entra token)
    are injected via add_aws_params / add_gcp_params / add_azure_params using
    analytiq_client so each retry always gets fresh credentials.
    """
    temperature = get_temperature(model)
    if thinking is not None:
        # Anthropic requires temperature=1 when extended thinking is enabled
        temperature = 1.0
    messages_to_send = _apply_prompt_caching(model, messages, tools=tools) if use_prompt_caching else messages
    params = {
        "model": model,
        "messages": messages_to_send,
        "api_key": api_key,
        "temperature": temperature,
        "response_format": response_format,
        # litellm's timeout kwarg (overall request timeout in seconds)
        "timeout": LLM_REQUEST_TIMEOUT_SECS,
    }
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    try:
        _, provider, _, _ = litellm.get_llm_provider(model)
    except Exception:
        provider = None
    if provider == "bedrock":
        from analytiq_data.llm.llm_aws import add_aws_params

        await add_aws_params(analytiq_client, params)
    elif provider == "vertex_ai":
        from analytiq_data.llm.llm_gcp import add_gcp_params

        await add_gcp_params(analytiq_client, params, api_key)
    elif provider == "azure_ai":
        from analytiq_data.llm.llm_azure import add_azure_params

        await add_azure_params(params)
    if tools:
        params["tools"] = tools
        params["tool_choice"] = tool_choice if tool_choice is not None else "auto"
    if thinking is not None:
        params["thinking"] = thinking

    return await litellm.acompletion(**params)


async def agent_completion(
    analytiq_client,
    model: str,
    messages: list,
    api_key: str,
    response_format: Optional[Dict] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[Union[str, Dict]] = None,
    thinking: Optional[Dict] = None,
):
    """
    Public wrapper for agent/chat use. Makes one LLM completion call with optional tools.
    Each call checks SPU at the caller; this only performs the litellm call with retry.
    """
    return await _litellm_acompletion_with_retry(
        analytiq_client,
        model=model,
        messages=messages,
        api_key=api_key,
        response_format=response_format,
        tools=tools,
        tool_choice=tool_choice,
        thinking=thinking,
        use_prompt_caching=True,
    )


async def agent_completion_stream(
    analytiq_client,
    model: str,
    messages: list,
    api_key: str,
    response_format: Optional[Dict] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[Union[str, Dict]] = None,
    thinking: Optional[Dict] = None,
):
    """
    Streaming version of agent completion. Yields ("content", str) for each content delta,
    then ("message", message_like) with accumulated content and tool_calls, then ("usage", usage_like) if present.
    Caller must record SPU using the usage object when present.
    """
    temperature = get_temperature(model)
    if thinking is not None:
        temperature = 1.0
    messages_to_send = _apply_prompt_caching(model, messages, tools=tools)
    params: Dict[str, Any] = {
        "model": model,
        "messages": messages_to_send,
        "api_key": api_key,
        "temperature": temperature,
        "response_format": response_format,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    try:
        _, provider, _, _ = litellm.get_llm_provider(model)
    except Exception:
        provider = None
    if provider == "bedrock":
        from analytiq_data.llm.llm_aws import add_aws_params

        await add_aws_params(analytiq_client, params)
    elif provider == "vertex_ai":
        from analytiq_data.llm.llm_gcp import add_gcp_params

        await add_gcp_params(analytiq_client, params, api_key)
    elif provider == "azure_ai":
        from analytiq_data.llm.llm_azure import add_azure_params

        await add_azure_params(params)
    if tools:
        params["tools"] = tools
        params["tool_choice"] = tool_choice if tool_choice is not None else "auto"
    if thinking is not None:
        params["thinking"] = thinking

    content_parts: list[str] = []
    thinking_parts: list[str] = []
    # Accumulate tool_calls by index (OpenAI stream sends partial deltas per index)
    tool_calls_by_index: Dict[int, Dict[str, Any]] = {}
    usage_obj: Any = None
    chunk_count = 0

    logger.info(f"agent_completion_stream start model={model} stream=True")
    response = await litellm.acompletion(**params)
    async for chunk in response:
        chunk_count += 1
        if chunk_count == 1 and isinstance(chunk, dict):
            logger.debug(f"agent_completion_stream first chunk keys: {list(chunk.keys())}")
        choices = chunk.get("choices", []) if isinstance(chunk, dict) else getattr(chunk, "choices", None) or []
        if not chunk or not choices or len(choices) == 0:
            # Usage-only chunk (include_usage)
            usage_obj = chunk.get("usage") if isinstance(chunk, dict) else getattr(chunk, "usage", None)
            continue
        c0 = choices[0]
        delta = c0.get("delta") if isinstance(c0, dict) else (getattr(c0, "delta", None) if hasattr(c0, "delta") else None)
        # Some providers send full message in one chunk instead of deltas
        if not delta:
            msg = c0.get("message") if isinstance(c0, dict) else getattr(c0, "message", None)
            if msg:
                msg_content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
                if msg_content:
                    content_parts.append(msg_content)
                    yield ("content", msg_content)
            continue
        # Content delta
        part = delta.get("content") if isinstance(delta, dict) else getattr(delta, "content", None)
        if part:
            content_parts.append(part)
            yield ("content", part)
        # Reasoning/thinking delta (Anthropic extended thinking, etc.)
        thinking_part = (
            delta.get("reasoning_content") if isinstance(delta, dict) else getattr(delta, "reasoning_content", None)
        ) or (delta.get("thinking") if isinstance(delta, dict) else getattr(delta, "thinking", None))
        if thinking_part:
            thinking_parts.append(thinking_part)
            yield ("thinking", thinking_part)
        # Tool call deltas (merge by index)
        tcs = delta.get("tool_calls") if isinstance(delta, dict) else getattr(delta, "tool_calls", None)
        if tcs:
            for tc in tcs:
                idx = getattr(tc, "index", None) if not isinstance(tc, dict) else tc.get("index")
                if idx is None:
                    continue
                if idx not in tool_calls_by_index:
                    tool_calls_by_index[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                cur = tool_calls_by_index[idx]
                if isinstance(tc, dict):
                    if tc.get("id"):
                        cur["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        cur["function"]["name"] = fn["name"]
                    if fn.get("arguments"):
                        cur["function"]["arguments"] = cur["function"]["arguments"] + fn["arguments"]
                else:
                    if getattr(tc, "id", None):
                        cur["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn and getattr(fn, "name", None):
                        cur["function"]["name"] = fn.name
                    if fn and getattr(fn, "arguments", None):
                        cur["function"]["arguments"] = cur["function"]["arguments"] + fn.arguments

    full_content = "".join(content_parts)
    full_thinking = "".join(thinking_parts).strip() or None
    logger.info(
        f"agent_completion_stream done model={model} chunks={chunk_count} content_parts={len(content_parts)} "
        f"thinking_parts={len(thinking_parts)} full_content_len={len(full_content)}"
    )
    # When provider sends full response in one (or zero) content chunks, simulate streaming so UI shows progressive output
    if full_content and len(content_parts) <= 1:
        sim_chunk_size = 80
        for i in range(0, len(full_content), sim_chunk_size):
            yield ("content", full_content[i : i + sim_chunk_size])

    # Build message-like object for agent_loop (content, tool_calls in OpenAI shape)
    tool_calls_list = []
    for i in sorted(tool_calls_by_index.keys()):
        tc = tool_calls_by_index[i]
        tool_calls_list.append(type("ToolCall", (), {
            "id": tc["id"],
            "function": type("Fn", (), {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]})(),
        })())
    message = type("Message", (), {
        "content": full_content,
        "tool_calls": tool_calls_list,
        "thinking_blocks": [{"type": "thinking", "thinking": full_thinking}] if full_thinking else None,
        "reasoning_content": full_thinking,
    })()
    yield ("message", message)
    if usage_obj is not None:
        yield ("usage", usage_obj)


@stamina.retry(on=is_retryable_error)
async def _litellm_acreate_file_with_retry(
    file: tuple,
    purpose: str,
    custom_llm_provider: str,
    api_key: str
):
    """
    Create a file with litellm with stamina retry mechanism.
    
    Args:
        file: The file tuple (filename, file_content)
        purpose: The purpose of the file (e.g., "assistants")
        custom_llm_provider: The LLM provider (e.g., "openai")
        api_key: The API key
        
    Returns:
        The file creation response
        
    Raises:
        Exception: If the call fails after all retries
    """
    return await litellm.acreate_file(
        file=file,
        purpose=purpose,
        custom_llm_provider=custom_llm_provider,
        api_key=api_key
    )

def _prompt_used_from_grouped_user_blocks(
    system_prompt: str,
    user_blocks: List[Dict[str, Any]],
    ordered_peer_docs: List[dict],
    include_ocr: bool,
    include_pdf: bool,
) -> str:
    """
    Build prompt_used text from the same user content blocks sent to the model.
    Text blocks are copied verbatim; OCR bodies and PDF payloads are replaced with placeholders.
    """
    if not user_blocks:
        return system_prompt.rstrip()

    # Build prompt_used by dispatching based on block content (OCR/PDF prefixes),
    # instead of walking by index position. This makes the placeholder build
    # resilient to future include toggles / inserted blocks.
    parts: List[str] = [_append_cache_breakpoint(system_prompt, _PROMPT_CACHE_CONTROL), ""]

    doc_ptr = -1
    current_doc_id_str: str | None = None
    n_docs = len(ordered_peer_docs)
    # Track which required blocks we replaced for each document.
    # This keeps the new order-robust dispatch while still failing fast
    # when OCR/PDF placeholders are missing.
    seen_ocr = [False] * n_docs
    seen_pdf = [False] * n_docs

    for blk in user_blocks:
        blk_type = blk.get("type")
        if blk_type == "text":
            text = blk.get("text") or ""
            stripped = text.lstrip()

            # Document boundary marker; map it to the corresponding doc id.
            if stripped.startswith("[Document #"):
                # Validate the previous doc before moving to the next.
                prev_idx = doc_ptr
                if prev_idx >= 0:
                    prev_doc_id_str = str(ordered_peer_docs[prev_idx].get("_id"))
                    if include_ocr and not seen_ocr[prev_idx]:
                        raise Exception(
                            f"Grouped LLM: missing OCR text block for document {prev_doc_id_str} "
                            f"(doc {prev_idx + 1} of {n_docs}) while building prompt_used"
                        )
                    if include_pdf and not seen_pdf[prev_idx]:
                        raise Exception(
                            f"Grouped LLM: missing PDF block for document {prev_doc_id_str} "
                            f"(doc {prev_idx + 1} of {n_docs}) while building prompt_used"
                        )
                doc_ptr += 1
                if doc_ptr >= len(ordered_peer_docs):
                    raise Exception("Grouped LLM: extra document header while building prompt_used")
                current_doc_id_str = str(ordered_peer_docs[doc_ptr].get("_id"))
                parts.append("")
                parts.append(text)
                continue

            # OCR placeholder
            if include_ocr and stripped.startswith("ocr_text:\n"):
                if not current_doc_id_str:
                    raise Exception("Grouped LLM: OCR block before any document header while building prompt_used")
                parts.append(f"ocr_text:\n<{current_doc_id_str}_ocr_text>")
                # Mark OCR seen for the current document.
                if 0 <= doc_ptr < n_docs:
                    seen_ocr[doc_ptr] = True
                continue

            # PDF placeholder (embedded form)
            if include_pdf and stripped.startswith("pdf:\n"):
                if not current_doc_id_str:
                    raise Exception("Grouped LLM: PDF text block before any document header while building prompt_used")
                parts.append(f"pdf:\n<{current_doc_id_str}_pdf>")
                # Mark PDF seen for the current document.
                if 0 <= doc_ptr < n_docs:
                    seen_pdf[doc_ptr] = True
                continue

            # Any other text block (e.g. group header, extra labels) is copied verbatim.
            parts.append(text)

        elif blk_type == "file":
            # PDF placeholder (file attachment form)
            if include_pdf:
                if not current_doc_id_str:
                    raise Exception("Grouped LLM: PDF file block before any document header while building prompt_used")
                parts.append(f"pdf:\n<{current_doc_id_str}_pdf>")
                if 0 <= doc_ptr < n_docs:
                    seen_pdf[doc_ptr] = True
            else:
                parts.append("pdf:\n<omitted_pdf>")

        else:
            # Unknown block type: preserve something stable rather than failing.
            parts.append(str(blk))

    if doc_ptr + 1 != len(ordered_peer_docs):
        raise Exception(
            f"Grouped LLM: document header count mismatch while building prompt_used "
            f"({doc_ptr + 1} != {len(ordered_peer_docs)})"
        )

    # Validate the last doc we've entered.
    if doc_ptr >= 0:
        last_idx = doc_ptr
        last_doc_id_str = str(ordered_peer_docs[last_idx].get("_id"))
        if include_ocr and not seen_ocr[last_idx]:
            raise Exception(
                f"Grouped LLM: missing OCR text block for document {last_doc_id_str} "
                f"(doc {last_idx + 1} of {n_docs}) while building prompt_used"
            )
        if include_pdf and not seen_pdf[last_idx]:
            raise Exception(
                f"Grouped LLM: missing PDF block for document {last_doc_id_str} "
                f"(doc {last_idx + 1} of {n_docs}) while building prompt_used"
            )

    return "\n".join(parts).rstrip()


async def _build_prompt_context(
    analytiq_client,
    doc: dict,
    prompt_revid: str,
    org_id: str,
    system_prompt: str,
    llm_provider: str,
    llm_model: str,
    api_key: str,
) -> Tuple[list, dict | None, str]:
    """
    Build chat messages (and optional peer_run) from prompt revision include settings.

    Used for grouped prompts (peer_match_keys) and for single-document runs with the same
    block layout and include toggles (ocr_text, pdf, metadata_keys). Prompt content is always included.
    """
    group_cfg = await ad.common.get_prompt_group_config(analytiq_client, prompt_revid)
    peer_match_keys: List[str] = group_cfg.get("peer_match_keys") or []
    include: Dict[str, Any] = group_cfg.get("include") or {}

    include_ocr = bool(include.get("ocr_text", True))
    include_pdf = bool(include.get("pdf", True))
    model_supports_pdf = supports_pdf_input(llm_model, None)
    # Providers like XAI don't support file blocks, so we fall back to embedding base64 in prompt text.
    can_attach_pdf_as_file_block = bool(include_pdf) and bool(model_supports_pdf) and llm_provider != "xai"
    embed_pdf_as_text = bool(include_pdf) and not can_attach_pdf_as_file_block
    metadata_keys: List[str] = list(include.get("metadata_keys") or [])
    include_all_metadata = metadata_keys == ["*"]

    db = analytiq_client.mongodb_async[analytiq_client.env]
    source_doc_id = str(doc.get("_id"))

    peer_run: dict | None = None
    ordered_peer_docs: List[dict]

    if peer_match_keys:
        doc_metadata: Dict[str, Any] = doc.get("metadata", {}) or {}

        match_values: Dict[str, Any] = {}
        for key in peer_match_keys:
            if key not in doc_metadata:
                raise Exception(f"Grouped LLM run failed: source document missing metadata key '{key}'")
            match_values[key] = doc_metadata[key]

        peer_query: Dict[str, Any] = {"organization_id": org_id}
        for key, value in match_values.items():
            peer_query[f"metadata.{key}"] = value

        peer_docs = await db.docs.find(peer_query).to_list(length=None)

        def _sort_key(d: dict):
            created_at = d.get("created_at") or d.get("upload_date")
            if not created_at and isinstance(d.get("_id"), ObjectId):
                created_at = d["_id"].generation_time
            return (created_at, d.get("_id"))

        peer_docs.sort(key=_sort_key)

        match_document_ids_all = [str(d["_id"]) for d in peer_docs if d.get("_id") is not None]

        if source_doc_id not in match_document_ids_all:
            raise Exception(
                "Grouped LLM run failed: source document not found by computed peer query "
                f"{match_values}"
            )

        # `ordered_peer_docs` includes the source as the first block (so the prompt can
        # describe the full analysis set). `match_document_ids`, however, is used for
        # UI/debugging to show "matched peer documents" *excluding* the source doc.
        match_document_ids = [doc_id for doc_id in match_document_ids_all if doc_id != source_doc_id]
        peer_run = {
            "match_values": match_values,
            "match_document_ids": match_document_ids,
        }

        ordered_peer_docs = [d for d in peer_docs if str(d.get("_id")) == source_doc_id] + [
            d for d in peer_docs if str(d.get("_id")) != source_doc_id
        ]
    else:
        ordered_peer_docs = [doc]

    instruction = await ad.common.get_prompt_content(analytiq_client, prompt_revid)

    ocr_cache: Dict[str, str] = {}
    pdf_base64_cache: Dict[str, str] = {}
    openai_file_id_cache: Dict[str, str] = {}
    pdf_upload_name_cache: Dict[str, str] = {}

    user_blocks: List[Dict[str, Any]] = []
    header_lines: List[str] = []
    if peer_match_keys:
        header_lines.append("You are analyzing a group of related documents.")
    else:
        header_lines.append("You are analyzing a document.")
    header_lines.append("")
    header_lines.append("Instruction:")
    header_lines.append(instruction)
    header_lines.append("")
    header_lines.append("Documents:")
    header_lines.append("")
    user_blocks.append({"type": "text", "text": "\n".join(header_lines)})

    for idx, d in enumerate(ordered_peer_docs, start=1):
        doc_id_str = str(d.get("_id"))
        doc_header_parts: List[str] = []
        doc_header_parts.append(f"[Document #{idx}]")

        meta = d.get("metadata") or {}
        if include_all_metadata:
            filtered_meta = meta
        else:
            filtered_meta = {k: meta[k] for k in metadata_keys if k in meta}

        if filtered_meta:
            doc_header_parts.append("metadata:")
            doc_header_parts.append(json.dumps(filtered_meta, indent=2, default=str))

        user_blocks.append({"type": "text", "text": "\n".join(doc_header_parts)})

        if include_ocr:
            if doc_id_str not in ocr_cache:
                text = await get_extracted_llm_text(analytiq_client, doc_id_str)
                if text is None:
                    raise Exception(
                        f"LLM run failed: missing OCR/text for document {doc_id_str} "
                        f"(doc {idx} of {len(ordered_peer_docs)}; include.ocr_text is true)"
                    )
                ocr_cache[doc_id_str] = text
            user_blocks.append({"type": "text", "text": f"ocr_text:\n{ocr_cache[doc_id_str]}"})

        if include_pdf:
            if doc_id_str not in pdf_base64_cache:
                blob, upload_name = await _load_pdf_blob(
                    analytiq_client,
                    d,
                    doc_id_str,
                    llm_provider,
                    llm_model,
                )
                pdf_base64_cache[doc_id_str] = base64.b64encode(blob).decode("utf-8")
                pdf_upload_name_cache[doc_id_str] = upload_name

            upload_name = pdf_upload_name_cache.get(doc_id_str) or (d.get("pdf_file_name") or "attachment")

            if can_attach_pdf_as_file_block:
                if llm_provider == "openai":
                    if doc_id_str not in openai_file_id_cache:
                        blob_bytes = base64.b64decode(pdf_base64_cache[doc_id_str].encode("utf-8"))
                        file_response = await _litellm_acreate_file_with_retry(
                            file=(upload_name, blob_bytes),
                            purpose="assistants",
                            custom_llm_provider="openai",
                            api_key=api_key,
                        )
                        openai_file_id_cache[doc_id_str] = file_response.id
                    user_blocks.append({"type": "file", "file": {"file_id": openai_file_id_cache[doc_id_str]}})
                else:
                    base64_url = f"data:application/pdf;base64,{pdf_base64_cache[doc_id_str]}"
                    user_blocks.append({"type": "file", "file": {"file_data": base64_url}})
            elif embed_pdf_as_text:
                user_blocks.append({"type": "text", "text": f"pdf:\n{pdf_base64_cache[doc_id_str]}"})

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_blocks},
    ]

    prompt_used_text = _prompt_used_from_grouped_user_blocks(
        system_prompt,
        user_blocks,
        ordered_peer_docs,
        include_ocr,
        include_pdf,
    )

    return messages, peer_run, prompt_used_text


async def run_llm(
    analytiq_client,
    document_id: str,
    prompt_revid: str = "default",
    llm_model: str = None,
    force: bool = False,
) -> dict:
    """
    Run the LLM for the given document and prompt.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revid: The prompt revision ID
        llm_model: The model to use (e.g. "gpt-4", "claude-3-sonnet", "mixtral-8x7b-32768")
               If not provided, the model will be retrieved from the prompt.
        force: If True, run the LLM even if the result is already cached
    
    Returns:
        dict: The LLM result
    """
    # Normalize invalid prompt_revid (e.g. non-ObjectId from agent) to avoid ObjectId errors downstream
    if prompt_revid != "default" and not ad.common.is_valid_object_id(prompt_revid):
        logger.info(f"prompt_revid {prompt_revid!r} is not a valid ObjectId, using default prompt")
        prompt_revid = "default"

    # Check for existing result unless force is True
    if not force:
        existing_result = await get_llm_result(analytiq_client, document_id, prompt_revid)
        if existing_result:
            logger.info(f"Using cached LLM result for doc_id/prompt_revid {document_id}/{prompt_revid}")
            return existing_result["llm_result"]
    else:
        # Delete the existing result
        await delete_llm_result(analytiq_client, document_id, prompt_revid)

    if not llm_model:
        logger.info(f"Running new LLM analysis for doc_id/prompt_revid {document_id}/{prompt_revid}")
    else:
        logger.info(f"Running new LLM analysis for doc_id/prompt_revid {document_id}/{prompt_revid} with passed-in model {llm_model}")

    # 1. Get the document and organization_id
    doc = await ad.common.doc.get_doc(analytiq_client, document_id)
    org_id = doc.get("organization_id")
    if not org_id:
        raise Exception("Document missing organization_id")

    # 2. Determine LLM model
    if llm_model is None:
        llm_model = await ad.llm.get_llm_model(analytiq_client, prompt_revid)

    # 3. Determine SPU cost for this LLM
    spu_cost = await ad.payments.get_spu_cost(llm_model)

    # 4. Determine number of pages (example: from doc['num_pages'] or OCR)
    num_pages = doc.get("num_pages", 1)  # You may need to adjust this

    total_spu_needed = spu_cost * num_pages

    # 5. Check if org has enough credits (throws SPUCreditException if insufficient)
    await ad.payments.check_spu_limits(org_id, total_spu_needed)

    if not ad.llm.is_chat_model(llm_model) and not ad.llm.is_supported_model(llm_model):
        logger.info(f"{document_id}/{prompt_revid}: LLM model {llm_model} is not a chat model, falling back to default llm_model")
        llm_model = "gpt-4o-mini"

    # Get the provider for the given LLM model
    llm_provider = ad.llm.get_llm_model_provider(llm_model)
    if llm_provider is None:
        logger.info(f"{document_id}/{prompt_revid}: LLM model {llm_model} not supported, falling back to default llm_model")
        llm_model = "gpt-4o-mini"
        llm_provider = "openai"
        
    api_key = await ad.llm.get_llm_key(analytiq_client, llm_provider)
    if api_key:
        logger.info(
            f"{document_id}/{prompt_revid}: LLM model: {llm_model}, provider: {llm_provider}, api_key: {api_key[:16]}********"
        )
    else:
        logger.info(
            f"{document_id}/{prompt_revid}: LLM model: {llm_model}, provider: {llm_provider}, api_key: (none — using provider-specific auth)"
        )

    # Check if prompt has KB ID for RAG (do this early to modify system prompt if needed)
    kb_id = await ad.common.get_prompt_kb_id(analytiq_client, prompt_revid)
    
    # Define system_prompt before using it
    if kb_id:
        system_prompt = (
            "You are a helpful assistant that extracts document information into JSON format. "
            "You have access to a knowledge base that contains additional context from related documents. "
            "Use the search_knowledge_base tool when you need additional information beyond what's in the current document. "
            "Always respond with valid JSON only, no other text. "
            "Format your entire response as a JSON object."
        )
    else:
        system_prompt = (
            "You are a helpful assistant that extracts document information into JSON format. "
            "Always respond with valid JSON only, no other text. "
            "Format your entire response as a JSON object."
        )
    
    messages, peer_run, prompt_used_text = await _build_prompt_context(
        analytiq_client,
        doc,
        prompt_revid,
        org_id,
        system_prompt,
        llm_provider=llm_provider,
        llm_model=llm_model,
        api_key=api_key,
    )
    if peer_run is not None:
        logger.info(f"{document_id}/{prompt_revid}: Grouped prompt context peer_run={peer_run}")
    else:
        logger.info(f"{document_id}/{prompt_revid}: Single-document prompt context from include settings")

    response_format = None
    
    # Most but not all models support response_format
    # See https://platform.openai.com/docs/guides/structured-outputs?format=without-parse
    if prompt_revid == "default":
        # Use a default response format
        response_format = {"type": "json_object"}
    elif litellm.supports_response_schema(model=llm_model):
        # Get the prompt response format, if any
        response_format = await ad.common.get_prompt_response_format(analytiq_client, prompt_revid)
        logger.info(f"{document_id}/{prompt_revid}: Response format: {response_format}")
    
    if response_format is None:
        logger.info(f"{document_id}/{prompt_revid}: No response format found for prompt")

    # Set up tools if KB is enabled (kb_id already retrieved above)
    tools = None
    max_iterations = 5  # Maximum number of tool call iterations
    
    if kb_id:
        # Check if model supports function calling
        if litellm.supports_function_calling(model=llm_model):
            logger.info(f"{document_id}/{prompt_revid}: KB {kb_id} specified, enabling RAG with function calling")
            
            # Define the search_knowledge_base tool
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_knowledge_base",
                        "description": "Search the knowledge base for relevant information to answer questions about documents. Use this when you need additional context beyond what's in the current document.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query to find relevant information in the knowledge base"
                                },
                                "top_k": {
                                    "type": "integer",
                                    "description": "Number of results to return (default: 5)",
                                    "default": 5
                                },
                                "metadata_filter": {
                                    "type": "object",
                                    "description": "Optional metadata filters (document_name, tag_ids, etc.)"
                                },
                                "coalesce_neighbors": {
                                    "type": "integer",
                                    "description": "Number of neighboring chunks to include for context (default: 1)"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ]
        else:
            logger.warning(f"{document_id}/{prompt_revid}: KB {kb_id} specified but model {llm_model} doesn't support function calling. RAG disabled.")
            kb_id = None  # Disable KB if model doesn't support it

    # 6. Call the LLM with agentic loop if KB is enabled, otherwise single call
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    
    if kb_id and tools:
        # Agentic loop: handle tool calls iteratively
        iteration = 0
        response = None
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"{document_id}/{prompt_revid}: LLM call iteration {iteration}/{max_iterations}")
            
            response = await _litellm_acompletion_with_retry(
                analytiq_client,
                model=llm_model,
                messages=messages,
                api_key=api_key,
                response_format=response_format,
                tools=tools,
                tool_choice="auto"  # Always allow tool calls in agentic mode
            )
            
            # Accumulate token usage
            if hasattr(response, 'usage') and response.usage:
                total_prompt_tokens += response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0
                total_completion_tokens += response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0
                total_cost += litellm.completion_cost(completion_response=response) if hasattr(response, 'usage') else 0.0
            
            # Check if LLM wants to call a tool
            message = response.choices[0].message
            tool_calls = message.tool_calls if hasattr(message, 'tool_calls') and message.tool_calls else []
            
            if not tool_calls:
                # No tool calls - LLM is done, break the loop
                logger.info(f"{document_id}/{prompt_revid}: LLM completed after {iteration} iteration(s)")
                break
            
            # Handle tool calls
            for tool_call in tool_calls:
                if tool_call.function.name == "search_knowledge_base":
                    # Parse function arguments
                    try:
                        args = json.loads(tool_call.function.arguments)
                        search_query = args.get("query", "")
                        top_k = args.get("top_k", 5)
                        metadata_filter = args.get("metadata_filter")
                        coalesce_neighbors = args.get("coalesce_neighbors")
                        
                        logger.info(f"{document_id}/{prompt_revid}: LLM requested KB search: query='{search_query}', top_k={top_k}")
                        
                        # Perform KB search
                        search_results = await ad.kb.search.search_knowledge_base(
                            analytiq_client=analytiq_client,
                            kb_id=kb_id,
                            query=search_query,
                            organization_id=org_id,
                            top_k=top_k,
                            metadata_filter=metadata_filter,
                            coalesce_neighbors=coalesce_neighbors
                        )
                        
                        # Format search results for LLM (merge overlapping spans per document)
                        formatted_context = ad.kb.format_kb_search_results_for_llm(
                            search_results.get("results", [])
                        )
                        
                        # Add tool response to messages
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.function.name,
                                        "arguments": tool_call.function.arguments
                                    }
                                }
                            ]
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": formatted_context
                        })
                        
                        logger.info(f"{document_id}/{prompt_revid}: Added {len(search_results.get('results', []))} KB search results to conversation")
                    except Exception as e:
                        error_msg = str(e)
                        # Check if this is a vector index timing issue
                        if "INITIAL_SYNC" in error_msg or "NOT_STARTED" in error_msg or "cannot query vector index" in error_msg.lower():
                            logger.warning(
                                f"{document_id}/{prompt_revid}: KB search index not ready yet (timing issue). "
                                f"Error: {error_msg[:200]}"
                            )
                            error_content = (
                                "The knowledge base search index is still building. "
                                "This is a temporary issue - please try again in a few moments."
                            )
                        else:
                            logger.error(f"{document_id}/{prompt_revid}: Error handling KB search tool call: {e}")
                            error_content = f"Error searching knowledge base: {error_msg[:200]}"
                        
                        # Add error message to conversation
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.function.name,
                                        "arguments": tool_call.function.arguments
                                    }
                                }
                            ]
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": error_content
                        })
                else:
                    logger.warning(f"{document_id}/{prompt_revid}: Unknown tool call: {tool_call.function.name}")
            
            # Continue loop to get LLM response with tool results
            if iteration >= max_iterations:
                logger.warning(f"{document_id}/{prompt_revid}: Reached max iterations ({max_iterations}), using last response")
                break
        
        if response is None:
            raise Exception(f"{document_id}/{prompt_revid}: No response received from LLM")
    else:
        # No KB or tools - single LLM call
        response = await _litellm_acompletion_with_retry(
            analytiq_client,
            model=llm_model,
            messages=messages,  # Use the vision-aware messages
            api_key=api_key,
            response_format=response_format,
        )
        
        # Get token usage for single call
        if hasattr(response, 'usage') and response.usage:
            total_prompt_tokens = response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0
            total_completion_tokens = response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0
            total_cost = litellm.completion_cost(completion_response=response) if hasattr(response, 'usage') else 0.0

    # 7. Get actual usage and cost from LLM response
    # For agentic loops, tokens are already accumulated above
    total_tokens = total_prompt_tokens + total_completion_tokens

    # 8. Deduct credits with actual metrics
    await ad.payments.record_spu_usage(
        org_id, 
        total_spu_needed,
        llm_provider=llm_provider,
        llm_model=llm_model,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        actual_cost=total_cost
    )

    # Skip any <think> ... </think> blocks
    resp_content = response.choices[0].message.content
    if resp_content is None:
        # If content is None after agentic loop, the LLM made tool calls but didn't provide final content
        # This shouldn't happen if we break the loop correctly, but handle it gracefully
        if kb_id and tools:
            logger.warning(f"{document_id}/{prompt_revid}: LLM response has no content after agentic loop, may have incomplete tool calls")
            raise Exception(f"LLM response incomplete: model made tool calls but didn't provide final response after {max_iterations} iterations")
        else:
            # For non-agentic calls, content should always be present
            logger.error(f"{document_id}/{prompt_revid}: LLM response has no content")
            raise Exception(f"LLM response has no content")

    # Process response based on LLM provider
    resp_content1 = process_llm_resp_content(resp_content, llm_provider)

    # 9. Return the response
    try:
        resp_dict = json.loads(resp_content1)
    except json.JSONDecodeError as e:
        # Surface enough of the raw content to diagnose provider quirks
        # (e.g. reasoning models that wrap output in <think> or markdown fences).
        raw_preview = (resp_content or "")[:500]
        cleaned_preview = (resp_content1 or "")[:500]
        logger.error(
            f"{document_id}/{prompt_revid}: Failed to parse LLM JSON response (provider={llm_provider}, model={llm_model}): {e}. "
            f"Raw content (first 500 chars): {raw_preview!r}. Cleaned content (first 500 chars): {cleaned_preview!r}"
        )
        raise Exception(
            f"LLM response was not valid JSON (provider={llm_provider}, model={llm_model}): {e}"
        ) from e

    # If this is not the default prompt, reorder the response to match schema
    if prompt_revid != "default":
        # Get the prompt response format
        response_format = await ad.common.get_prompt_response_format(analytiq_client, prompt_revid)
        if response_format and response_format.get("type") == "json_schema":
            schema = response_format["json_schema"]["schema"]
            # Get ordered properties from schema
            ordered_properties = list(schema.get("properties", {}).keys())
            
            #logger.info(f"Ordered properties: {ordered_properties}")

            # Create new ordered dictionary based on schema property order
            ordered_resp = OrderedDict()
            for key in ordered_properties:
                if key in resp_dict:
                    ordered_resp[key] = resp_dict[key]

            #logger.info(f"Ordered response: {ordered_resp}")
            
            # Add any remaining keys that might not be in schema
            for key in resp_dict:
                if key not in ordered_resp:
                    ordered_resp[key] = resp_dict[key]
                    
            resp_dict = dict(ordered_resp)  # Convert back to regular dict

            #logger.info(f"Reordered response: {resp_dict}")

    # 10. Save the new result
    run_payload: dict[str, object] = {"prompt": prompt_used_text}
    if peer_run is not None:
        run_payload["match_values"] = peer_run["match_values"]
        run_payload["match_document_ids"] = peer_run["match_document_ids"]
    await save_llm_result(
        analytiq_client,
        document_id,
        prompt_revid,
        resp_dict,
        run=run_payload,
    )

    # Optional per-org webhook: per-prompt completion (non-default prompts only)
    if prompt_revid != "default":
        try:
            prompt_id, prompt_version = await get_prompt_info_from_rev_id(analytiq_client, prompt_revid)
            await ad.webhooks.enqueue_event(
                analytiq_client,
                organization_id=org_id,
                event_type="llm.completed",
                document_id=document_id,
                prompt={
                    "prompt_revid": prompt_revid,
                    "prompt_id": prompt_id,
                    "prompt_version": prompt_version,
                },
                llm_output=resp_dict,
            )
        except Exception as e:
            logger.warning(f"{document_id}/{prompt_revid}: webhook enqueue failed: {e}")
    
    return resp_dict

async def get_llm_result(analytiq_client,
                         document_id: str,
                         prompt_revid: str,
                         fallback: bool = False) -> dict | None:
    """
    Retrieve the latest LLM result from MongoDB.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revid: The prompt revision ID
        fallback: If True, return the latest LLM result available for the prompt_id
    
    Returns:
        dict | None: The latest LLM result if found, None otherwise
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    
    if not fallback:
        result = await db.llm_runs.find_one(
            {
                "document_id": document_id,
                "prompt_revid": prompt_revid
            },
            sort=[("_id", -1)]
        )
    else:
        # Get the prompt_id and prompt_version from the prompt_revid
        prompt_id, _ = await get_prompt_info_from_rev_id(analytiq_client, prompt_revid)
        # Sort by _id in descending order to get the latest available result for the prompt_id
        result = await db.llm_runs.find_one(
            {
                "document_id": document_id,
                "prompt_id": prompt_id,
            },
            sort=[("prompt_version", -1)]
        )

    return result

async def get_prompt_info_from_rev_id(analytiq_client, prompt_revid: str) -> tuple[str, int]:
    """
    Get prompt_id and prompt_version from prompt_revid.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        prompt_revid: The prompt revision ID
        
    Returns:
        tuple[str, int]: (prompt_id, prompt_version)
    """
    # Special case for the default prompt
    if prompt_revid == "default":
        return "default", 1
    
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    
    # Get the prompt revision
    elem = await db.prompt_revisions.find_one({"_id": ObjectId(prompt_revid)})
    if elem is None:
        raise ValueError(f"Prompt revision {prompt_revid} not found")
    
    return str(elem["prompt_id"]), elem["prompt_version"]


def _llm_run_element_for_log(element: dict[str, object]) -> dict[str, object]:
    """Shallow copy of an llm_runs document for logging; truncates huge run.prompt text."""
    out = dict(element)
    run = out.get("run")
    if isinstance(run, dict):
        run_copy = dict(run)
        p = run_copy.get("prompt")
        if p is not None:
            n = len(p) if isinstance(p, str) else len(str(p))
            run_copy["prompt"] = f"<omitted {n} chars>"
        out["run"] = run_copy
    return out


async def save_llm_result(
    analytiq_client,
    document_id: str,
    prompt_revid: str,
    llm_result: dict,
    run: dict | None = None,
) -> str:
    """
    Save the LLM result to MongoDB.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revid: The prompt revision ID
        llm_result: The LLM result
        run: Optional execution metadata (prompt, match_values, match_document_ids).
    """

    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]

    current_time_utc = datetime.now(UTC)
    
    # Get prompt_id and prompt_version from prompt_revid
    prompt_id, prompt_version = await get_prompt_info_from_rev_id(analytiq_client, prompt_revid)

    element: dict[str, object] = {
        "prompt_revid": prompt_revid,
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "document_id": document_id,
        "llm_result": llm_result,
        "updated_llm_result": llm_result.copy(),
        "is_edited": False,
        "is_verified": False,
        "created_at": current_time_utc,
        "updated_at": current_time_utc,
    }

    if run is not None:
        element["run"] = run

    logger.info(f"Saving LLM result: {_llm_run_element_for_log(element)}")

    # Save the result, return the ID
    result = await db.llm_runs.insert_one(element)
    return str(result.inserted_id)

async def delete_llm_result(analytiq_client,
                            document_id: str,
                            prompt_revid: str | None = None) -> bool:
    """
    Delete an LLM result from MongoDB.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revid: The prompt revision ID. If None, delete all LLM results for the document.
    
    Returns:
        bool: True if deleted, False if not found
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]

    delete_filter = {
        "document_id": document_id
    }

    if prompt_revid is not None:
        delete_filter["prompt_revid"] = prompt_revid

    result = await db.llm_runs.delete_many(delete_filter)
    
    return result.deleted_count > 0


async def run_llm_for_prompt_revids(analytiq_client, document_id: str, prompt_revids: list[str], llm_model: str = None, force: bool = False) -> None:
    """
    Run the LLM for the given prompt IDs.

    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revids: The prompt revision IDs to run the LLM for
        force: If True, run the LLM even if the result is already cached
    """

    n_prompts = len(prompt_revids)

    if n_prompts == 0:
        logger.info(f"No prompts to run for document {document_id}")
        return []

    # Create n_prompts concurrent tasks, each with its own timeout to avoid one hung
    # prompt blocking all others. We still rely on litellm's own timeout, but this
    # is an extra safeguard at the task level.
    tasks: List[asyncio.Task] = []
    for prompt_revid in prompt_revids:
        task = asyncio.create_task(
            asyncio.wait_for(
                run_llm(analytiq_client, document_id, prompt_revid, llm_model, force=force),
                timeout=LLM_REQUEST_TIMEOUT_SECS,
            )
        )
        tasks.append(task)

    # Run the tasks, returning exceptions instead of raising immediately
    results = await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(
        f"LLM run completed for {document_id} with {n_prompts} prompts "
        f"(successes={sum(1 for r in results if not isinstance(r, Exception))}, "
        f"failures={sum(1 for r in results if isinstance(r, Exception))})"
    )

    return results

async def update_llm_result(analytiq_client,
                            document_id: str,
                            prompt_revid: str,
                            updated_llm_result: dict,
                            is_verified: bool = False) -> str:
    """
    Update an existing LLM result with edits and verification status.
    
    Args:
        analytiq_client: The AnalytiqClient instance
        document_id: The document ID
        prompt_revid: The prompt revision ID
        updated_llm_result: The updated LLM result
        is_verified: Whether this result has been verified
    
    Returns:
        str: The ID of the updated document
        
    Raises:
        ValueError: If no existing result found or if result signatures don't match
    """
    db_name = analytiq_client.env
    db = analytiq_client.mongodb_async[db_name]
    
    # Get the latest result
    existing = await db.llm_runs.find_one(
        {
            "document_id": document_id,
            "prompt_revid": prompt_revid
        },
        sort=[("_id", -1)]
    )
    
    if not existing:
        raise ValueError(f"No existing LLM result found for document_id: {document_id}, prompt_revid: {prompt_revid}")
    
    # Validate that the updated result has the same structure as the original
    existing_keys = set(existing["llm_result"].keys())
    updated_keys = set(updated_llm_result.keys())
    
    if existing_keys != updated_keys:
        raise ValueError(
            f"Updated result signature does not match original. "
            f"Original keys: {sorted(existing_keys)}, "
            f"Updated keys: {sorted(updated_keys)}"
        )

    current_time_utc = datetime.now(UTC)
    created_at = existing.get("created_at", current_time_utc)
    updated_at = current_time_utc
    
    # Update the document
    update_data = {
        "llm_result": existing["llm_result"],
        "updated_llm_result": updated_llm_result,
        "is_edited": True,
        "is_verified": is_verified,
        "created_at": created_at,
        "updated_at": updated_at
    }
    
    result = await db.llm_runs.update_one(
        {"_id": existing["_id"]},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise ValueError("Failed to update LLM result")
        
    return str(existing["_id"])

async def run_llm_chat(
    request: "LLMPromptRequest",
    current_user: "User"
) -> Union[dict, "StreamingResponse"]:
    """
    Test LLM with arbitrary prompt (admin only).
    Supports both streaming and non-streaming responses.
    
    Args:
        request: The LLM prompt request
        current_user: The current user making the request
    
    Returns:
        Union[dict, StreamingResponse]: Either a chat completion response or a streaming response
    """
    
    logger.info(f"run_llm_chat() start: model: {request.model}, stream: {request.stream}")

    # Verify the model exists and is enabled
    db = ad.common.get_async_db()
    found = False
    for provider in await db.llm_providers.find({}).to_list(None):
        if request.model in provider["litellm_models_enabled"]:
            found = True
            break
    if not found:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {request.model}"
        )

    try:
        # Prepare messages for litellm
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Prepare parameters
        params = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
        }
        
        if request.max_tokens:
            params["max_tokens"] = request.max_tokens
        
        # Get the provider and API key for this model
        llm_provider = ad.llm.get_llm_model_provider(request.model)
        analytiq_client = ad.common.get_analytiq_client()
        
        # Get the API key for the provider
        api_key = await ad.llm.get_llm_key(analytiq_client, llm_provider)
        if api_key:
            params["api_key"] = api_key
            logger.info(f"Using API key for provider {llm_provider}: {api_key[:16]}********")
        
        if llm_provider == "bedrock":
            from analytiq_data.llm.llm_aws import add_aws_params

            await add_aws_params(analytiq_client, params)

        elif llm_provider == "vertex_ai":
            from analytiq_data.llm.llm_gcp import add_gcp_params

            await add_gcp_params(analytiq_client, params, api_key)

        elif llm_provider == "azure_ai":
            from analytiq_data.llm.llm_azure import add_azure_params

            await add_azure_params(params)

        if request.stream:
            # Streaming response
            async def generate_stream():
                try:
                    params["temperature"] = get_temperature(params["model"])
                    response = await litellm.acompletion(**params, stream=True)
                    async for chunk in response:
                        if chunk.choices[0].delta.content:
                            yield f"data: {json.dumps({'chunk': chunk.choices[0].delta.content, 'done': False})}\n\n"
                    # Send final done signal
                    yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
                except Exception as e:
                    logger.error(f"Error in streaming LLM response: {str(e)}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                generate_stream(),
                media_type="text/plain",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )
        else:
            # Non-streaming response
            params["temperature"] = get_temperature(params["model"])
            response = await litellm.acompletion(**params)
            
            return {
                "id": response.id,
                "object": "chat.completion",
                "created": int(datetime.now(UTC).timestamp()),
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response.choices[0].message.content
                        },
                        "finish_reason": response.choices[0].finish_reason
                    }
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
    except Exception as e:
        logger.error(f"Error in LLM test: {str(e)}")
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Error processing LLM request: {str(e)}"
        )


def get_embedding_models(provider: str = "openai") -> List[Dict[str, Any]]:
    """
    Get all embedding models for a given provider.
    
    Args:
        provider: The litellm provider name (e.g., "openai", "cohere", "azure")
    
    Returns:
        List of dictionaries, each containing:
        - name: Model name
        - dimensions: Embedding vector dimensions (output_vector_size)
        - input_cost_per_token: Cost per token for input
        - input_cost_per_token_batches: Cost per token for batched input (if available)
    """
    models = litellm.models_by_provider.get(provider, [])
    embedding_models = []
    
    for model in models:
        try:
            model_info = litellm.get_model_info(model)
            # Check if this is an embedding model
            if model_info.get('mode') == 'embedding':
                # Get cost information from model_cost
                input_cost_per_token = 0.0
                input_cost_per_token_batches = 0.0
                if model in litellm.model_cost:
                    input_cost_per_token = litellm.model_cost[model].get("input_cost_per_token", 0.0)
                    input_cost_per_token_batches = litellm.model_cost[model].get("input_cost_per_token_batches", 0.0)
                
                embedding_models.append({
                    'name': model,
                    'dimensions': model_info.get('output_vector_size'),
                    'input_cost_per_token': input_cost_per_token,
                    'input_cost_per_token_batches': input_cost_per_token_batches
                })
        except Exception as e:
            # Skip models that can't be queried
            logger.debug(f"Could not get model info for {model}: {e}")
            pass
    
    return embedding_models