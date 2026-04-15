"""
Knowledge Base indexing logic.

Handles chunking, embedding generation, caching, and atomic vector storage.
"""

import logging
import math
import os
import re
import warnings
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional, Tuple
from bson import ObjectId
import tiktoken
import litellm
import stamina

import analytiq_data as ad
from .embedding_cache import (
    compute_chunk_hash,
    get_embedding_from_cache,
    store_embedding_in_cache
)
from .errors import (
    is_retryable_embedding_error,
    is_permanent_embedding_error,
    set_kb_status_to_error
)
from .chunking_config import (
    ChunkingPreprocessConfig,
    chunking_preprocess_from_kb_dict,
    preprocess_markdown,
)

logger = logging.getLogger(__name__)


def get_embedding_cost(response, embedding_model: str) -> float:
    """
    Extract actual cost from a litellm embedding response.
    
    Args:
        response: The litellm embedding response object
        embedding_model: The embedding model name
        
    Returns:
        Actual cost in USD (float)
    """
    try:
        # Try to get cost from hidden params (litellm's automatic cost tracking)
        if hasattr(response, '_hidden_params') and response._hidden_params:
            response_cost = response._hidden_params.get("response_cost")
            if response_cost is not None:
                return float(response_cost)
        
        # Fallback: calculate cost from usage if available
        if hasattr(response, 'usage') and response.usage:
            # Get token count from usage
            total_tokens = 0
            if hasattr(response.usage, 'total_tokens'):
                total_tokens = response.usage.total_tokens
            elif hasattr(response.usage, 'prompt_tokens'):
                total_tokens = response.usage.prompt_tokens
            
            # Get cost per token from litellm model_cost
            if embedding_model in litellm.model_cost:
                cost_info = litellm.model_cost[embedding_model]
                # For embeddings, check if we're using batched pricing
                input_cost_per_token = cost_info.get("input_cost_per_token", 0.0)
                input_cost_per_token_batches = cost_info.get("input_cost_per_token_batches", 0.0)
                
                # Use batched pricing if available and we have multiple inputs
                if input_cost_per_token_batches > 0 and hasattr(response, 'data') and len(response.data) > 1:
                    cost = total_tokens * input_cost_per_token_batches
                else:
                    cost = total_tokens * input_cost_per_token
                
                return float(cost)
        
        # If we can't determine cost, return 0.0
        logger.debug(f"Could not determine cost for embedding model {embedding_model}, returning 0.0")
        return 0.0
        
    except Exception as e:
        logger.warning(f"Error extracting embedding cost: {e}, returning 0.0")
        return 0.0


try:
    from chonkie import (
        TokenChunker,
        SentenceChunker,
        RecursiveChunker,
        RecursiveRules,
        RecursiveLevel,
        OverlapRefinery,
        TableChunker,
    )
    from chonkie.chef import MarkdownChef, TableChef, TextChef

    CHONKIE_AVAILABLE = True
except ImportError:
    CHONKIE_AVAILABLE = False
    MarkdownChef = None  # type: ignore[misc, assignment]
    TableChef = None  # type: ignore[misc, assignment]
    TextChef = None  # type: ignore[misc, assignment]
    TableChunker = None  # type: ignore[misc, assignment]
    RecursiveRules = None  # type: ignore[misc, assignment]
    RecursiveLevel = None  # type: ignore[misc, assignment]
    logger.warning("Chonkie not available. KB indexing will not work.")

# Disabled chunker types (require sentence_transformers which is too large)
DISABLED_CHUNKER_TYPES = ["semantic", "late", "sdpm"]

# Embedding batch size for LiteLLM API calls
EMBEDDING_BATCH_SIZE = 100

# SPU metering: one SPU covers up to this many embedding API calls (cache misses), then another SPU per block of N.
# Example: 1000 misses -> ceil(1000 / 250) = 4 SPUs (at least ~2x raw API cost vs $0.05/SPU retail).
EMBEDDINGS_PER_SPU = 250


def spus_for_kb_indexing_embedding_misses(cache_miss_count: int) -> int:
    """Return billable SPUs for KB indexing given the number of embedding cache misses."""
    if cache_miss_count <= 0:
        return 0
    return math.ceil(cache_miss_count / EMBEDDINGS_PER_SPU)


@dataclass
class ExtractedIndexingText:
    """Text used for chunking plus optional per-page character offsets (1-based page numbers)."""

    text: str
    page_offsets: List[Dict[str, int]]


class Chunk:
    """Represents a text chunk with metadata."""

    def __init__(
        self,
        text: str,
        chunk_index: int,
        token_count: int,
        indexed_text_start: int,
        indexed_text_end: int,
        *,
        heading_path: str = "",
        page_start: int = 0,
        page_end: int = 0,
        chunk_type: str = "prose",
        embedding_input: Optional[str] = None,
    ):
        self.text = text
        self.chunk_index = chunk_index
        self.token_count = token_count
        self.indexed_text_start = indexed_text_start
        self.indexed_text_end = indexed_text_end
        self.heading_path = heading_path
        self.page_start = page_start
        self.page_end = page_end
        self.chunk_type = chunk_type
        self.embedding_input = embedding_input
        self.hash = compute_chunk_hash(text)


def _assign_indexed_text_spans(full_text: str, chonkie_chunks: List[Any]) -> List[Tuple[int, int]]:
    """
    Map each chunk's ``.text`` to ``[start, end)`` character offsets in ``full_text``.

    Chonkie's ``start_index`` / ``end_index`` are unreliable after ``OverlapRefinery`` on
    recursive chunks, so we locate each chunk sequentially in the source string.
    """
    spans: List[Tuple[int, int]] = []
    cursor = 0
    prev_start = 0
    for i, ch in enumerate(chonkie_chunks):
        t = ch.text
        if not t:
            spans.append((cursor, cursor))
            continue
        pos = full_text.find(t, cursor)
        if pos == -1:
            # Overlap >= chunk body: the chunk starts at or before cursor.
            # Search from prev_start (tightest safe lower bound) rather than 0
            # to avoid matching identical text that appeared earlier in the document.
            pos = full_text.find(t, prev_start)
            if pos == -1:
                raise ValueError(
                    f"Chunk {i} text not found in indexed source string (len full_text={len(full_text)})"
                )
        start = pos
        end = pos + len(t)
        if full_text[start:end] != t:
            raise ValueError(f"Chunk {i} span mismatch at [{start}:{end}]")
        spans.append((start, end))
        prev_start = pos
        cursor = pos + 1
    return spans


def build_markdown_with_page_offsets(textract_doc: Any, cfg: ChunkingPreprocessConfig) -> Tuple[str, List[Dict[str, int]]]:
    """Concatenate per-page OCR markdown with exact character offsets per page (1-based page numbers)."""
    from textractor.data.markdown_linearization_config import MarkdownLinearizationConfig

    config = MarkdownLinearizationConfig(table_linearization_format="markdown")
    parts: List[str] = []
    page_offsets: List[Dict[str, int]] = []
    cursor = 0
    pages = list(getattr(textract_doc, "pages", None) or [])
    for page_num, page in enumerate(pages, start=1):
        page_md_raw = page.to_markdown(config=config)
        page_md = preprocess_markdown(page_md_raw, cfg)
        page_offsets.append({"page": page_num, "start": cursor, "end": cursor + len(page_md)})
        parts.append(page_md)
        cursor += len(page_md)
        if page_num < len(pages):
            sep = "\n\n"
            parts.append(sep)
            cursor += len(sep)
    return "".join(parts), page_offsets


def find_page_range_for_span(start: int, end: int, page_offsets: List[Dict[str, int]]) -> Tuple[int, int]:
    if not page_offsets or end <= start:
        return (0, 0)

    def page_at(p: int) -> int:
        for r in page_offsets:
            if r["start"] <= p < r["end"]:
                return int(r["page"])
        if p >= page_offsets[-1]["end"]:
            return int(page_offsets[-1]["page"])
        if p < page_offsets[0]["start"]:
            return int(page_offsets[0]["page"])
        # p is in a gap between pages (e.g. the \n\n separator): return the preceding page
        preceding = [r for r in page_offsets if r["end"] <= p]
        if preceding:
            return int(preceding[-1]["page"])
        return int(page_offsets[0]["page"])

    last_char = max(start, end - 1)
    ps = page_at(start)
    pe = page_at(last_char)
    return (min(ps, pe), max(ps, pe))


def extract_heading_path(chunk_text: str, full_markdown: str, depth: int, *, chunk_start: int = -1) -> str:
    """Nearest preceding markdown headings as a breadcrumb (depth = max heading level to track).

    Prefer passing ``chunk_start`` (the known character offset of the chunk in ``full_markdown``)
    to avoid mis-locating repeated text via string search.
    """
    if chunk_start >= 0:
        pos = chunk_start
    else:
        anchor = chunk_text[:120] if len(chunk_text) >= 120 else chunk_text
        if not anchor.strip():
            return ""
        pos = full_markdown.find(anchor)
        if pos == -1 and len(chunk_text) >= 40:
            pos = full_markdown.find(chunk_text[:40])
        if pos == -1:
            return ""
    if not chunk_text.strip():
        return ""
    preceding = full_markdown[:pos]
    headings = re.findall(rf"^(#{{1,{depth}}})\s+(.+)$", preceding, re.MULTILINE)
    path_parts: Dict[int, str] = {}
    for hashes, title in headings:
        path_parts[len(hashes)] = title.strip()
    if not path_parts:
        return ""
    return " > ".join(path_parts[k] for k in sorted(path_parts))


def make_recursive_chunker(chunk_size: int, cfg: ChunkingPreprocessConfig) -> Any:
    """Heading-aware recursive chunker without HuggingFace hub (Option B)."""
    depth = cfg.heading_split_depth
    heading_pattern = rf"(?m)(?=^#{{1,{depth}}} )"
    rules = RecursiveRules(
        levels=[
            RecursiveLevel(pattern=heading_pattern, include_delim="next", pattern_mode="split"),
            RecursiveLevel(delimiters=["\n\n"]),
            RecursiveLevel(delimiters=[". ", "! ", "? "]),
            RecursiveLevel(whitespace=True),
            RecursiveLevel(),
        ]
    )
    return RecursiveChunker(chunk_size=chunk_size, rules=rules)


def _ordered_markdown_segments(md_doc: Any, source_text: str) -> List[Tuple[str, str, int, int]]:
    """Prose / table / code segments in source order (indices in original markdown string)."""
    items: List[Tuple[str, str, int, int]] = []
    for ch in getattr(md_doc, "chunks", None) or []:
        t = getattr(ch, "text", "") or ""
        if t.strip():
            items.append(("prose", t, ch.start_index, ch.end_index))
    for t in getattr(md_doc, "tables", None) or []:
        items.append(("table", t.content, t.start_index, t.end_index))
    for c in getattr(md_doc, "code", None) or []:
        seg = source_text[c.start_index:c.end_index]
        items.append(("code", seg, c.start_index, c.end_index))
    for im in getattr(md_doc, "images", None) or []:
        seg = source_text[im.start_index:im.end_index]
        items.append(("prose", seg, im.start_index, im.end_index))
    items.sort(key=lambda x: (x[2], x[3]))
    return items


def _chunk_markdown_document(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    cfg: ChunkingPreprocessConfig,
    page_offsets: Optional[List[Dict[str, int]]],
) -> List[Chunk]:
    chef = MarkdownChef()
    md_doc = chef.parse(text)
    prose_chunker = make_recursive_chunker(chunk_size, cfg)
    table_chunker = TableChunker(chunk_size=chunk_size)
    raw_with_meta: List[Tuple[Any, str]] = []

    for kind, seg_text, _si, _ei in _ordered_markdown_segments(md_doc, text):
        if not seg_text.strip():
            continue
        if kind == "table":
            for ch in table_chunker.chunk(seg_text):
                raw_with_meta.append((ch, "table"))
        elif kind == "code":
            code_chunker = RecursiveChunker(chunk_size=chunk_size)
            for ch in code_chunker.chunk(seg_text):
                raw_with_meta.append((ch, "code"))
        else:
            pcs = prose_chunker.chunk(seg_text)
            if chunk_overlap > 0:
                refinery = OverlapRefinery(context_size=chunk_overlap, mode="token")
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=".*Context size is greater than the chunk size.*",
                        category=UserWarning,
                        module="chonkie.refinery.overlap",
                    )
                    pcs = refinery.refine(pcs)
            for ch in pcs:
                raw_with_meta.append((ch, "prose"))

    chonkie_chunks = [x[0] for x in raw_with_meta]
    types = [x[1] for x in raw_with_meta]
    indexed_spans = _assign_indexed_text_spans(text, chonkie_chunks)
    encoding = tiktoken.get_encoding("cl100k_base")
    po = page_offsets or []
    result: List[Chunk] = []
    for idx, (chonkie_chunk, ctype) in enumerate(zip(chonkie_chunks, types)):
        ct = chonkie_chunk.text
        token_count = len(encoding.encode(ct))
        start, end = indexed_spans[idx]
        ps, pe = find_page_range_for_span(start, end, po)
        result.append(Chunk(ct, idx, token_count, start, end, page_start=ps, page_end=pe, chunk_type=ctype))
    return result


async def chunk_text(
    text: str,
    chunker_type: str,
    chunk_size: int,
    chunk_overlap: int,
    *,
    preprocess_cfg: Optional[ChunkingPreprocessConfig] = None,
    page_offsets: Optional[List[Dict[str, int]]] = None,
) -> List[Chunk]:
    """
    Chunk text using Chonkie.

    ``chunker_type="recursive"`` routes through MarkdownChef (heading-aware prose +
    table-aware splits via TableChunker). All other types ("token", "word", "sentence")
    apply the chunker directly to the raw text. Chef selection is internal to this
    function and not user-configurable.
    """
    if not CHONKIE_AVAILABLE:
        raise RuntimeError("Chonkie is not available. Please install chonkie package.")

    if not text or not text.strip():
        return []

    if chunker_type in DISABLED_CHUNKER_TYPES:
        raise ValueError(
            f"Chunker type '{chunker_type}' is disabled as it requires sentence_transformers "
            f"(large dependency). Supported types: token, word, sentence, recursive"
        )

    cfg = preprocess_cfg or ChunkingPreprocessConfig()

    try:
        # "recursive" uses MarkdownChef: heading-aware prose splits + TableChunker for tables.
        if chunker_type == "recursive":
            result = _chunk_markdown_document(
                text, chunk_size, chunk_overlap, cfg, page_offsets
            )
            logger.info(f"Chunked text into {len(result)} chunks using recursive+markdown chunker")
            return result

        # token / word / sentence: apply chunker directly to raw text.
        chunkers_with_overlap: Dict[str, Any] = {
            "token": TokenChunker,
            "word": TokenChunker,
            "sentence": SentenceChunker,
        }

        if chunker_type not in chunkers_with_overlap:
            raise ValueError(
                f"Unknown chunker_type: {chunker_type}. Supported types: "
                f"{['recursive'] + list(chunkers_with_overlap.keys())}"
            )

        ChunkerClass = chunkers_with_overlap[chunker_type]
        if chunker_type == "word":
            chunker = ChunkerClass(tokenizer="word", chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        else:
            chunker = ChunkerClass(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chonkie_chunks = chunker.chunk(text)

        indexed_spans = _assign_indexed_text_spans(text, chonkie_chunks)
        encoding = tiktoken.get_encoding("cl100k_base")
        po = page_offsets or []
        result = []
        for idx, chonkie_chunk in enumerate(chonkie_chunks):
            ctext = chonkie_chunk.text
            token_count = len(encoding.encode(ctext))
            start, end = indexed_spans[idx]
            ps, pe = find_page_range_for_span(start, end, po)
            result.append(Chunk(ctext, idx, token_count, start, end, page_start=ps, page_end=pe))

        logger.info(f"Chunked text into {len(result)} chunks using {chunker_type} chunker")
        return result

    except Exception as e:
        logger.error(f"Error chunking text with {chunker_type}: {e}")
        raise


@stamina.retry(on=is_retryable_embedding_error)
async def generate_embeddings_batch(
    analytiq_client,
    texts: List[str],
    embedding_model: str
) -> Tuple[List[List[float]], float]:
    """
    Generate embeddings for a batch of texts using LiteLLM.
    
    Uses stamina retry mechanism for transient errors (rate limits, timeouts, 503 errors).
    
    Args:
        analytiq_client: The analytiq client
        texts: List of text strings to embed
        embedding_model: LiteLLM embedding model string
        
    Returns:
        Tuple of (list of embedding vectors, actual cost in USD)
        
    Raises:
        Exception: If embedding generation fails after retries
    """
    if not texts:
        return [], 0.0

    # Generate embeddings via LiteLLM (handles Bedrock/Vertex AI credentials automatically)
    # This will be retried automatically by stamina if it raises a retryable error
    response = await ad.llm.aembedding(analytiq_client, embedding_model, texts)
    
    # Extract embeddings from response
    embeddings = [item["embedding"] for item in response.data]
    
    # Extract actual cost from response
    actual_cost = get_embedding_cost(response, embedding_model)
    
    logger.info(f"Generated {len(embeddings)} embeddings using {embedding_model}, cost: ${actual_cost:.6f}")
    return embeddings, actual_cost


async def get_or_generate_embeddings(
    analytiq_client,
    chunks: List[Chunk],
    embedding_model: str,
    organization_id: str
) -> Tuple[List[List[float]], int]:
    """
    Get embeddings from cache or generate new ones.
    
    Args:
        analytiq_client: The analytiq client
        chunks: List of Chunk objects
        embedding_model: LiteLLM embedding model string
        organization_id: Organization ID for SPU metering
        
    Returns:
        Tuple of (embeddings list, cache_miss_count)
    """
    if not chunks:
        return [], 0
    
    embeddings = []
    cache_misses = []
    cache_miss_indices = []
    
    # Check cache for each chunk
    for idx, chunk in enumerate(chunks):
        cached_embedding = await get_embedding_from_cache(
            analytiq_client,
            chunk.hash,
            embedding_model
        )

        if cached_embedding:
            embeddings.append(cached_embedding)
        else:
            embeddings.append(None)  # Placeholder
            cache_misses.append(chunk.embedding_input if chunk.embedding_input else chunk.text)
            cache_miss_indices.append(idx)
    
    # Generate embeddings for cache misses in batches
    if cache_misses:
        cache_miss_count = len(cache_misses)
        spus_to_charge = spus_for_kb_indexing_embedding_misses(cache_miss_count)
        logger.info(
            f"Generating {cache_miss_count} embeddings (cache misses), bill as {spus_to_charge} SPU(s) "
            f"(up to {EMBEDDINGS_PER_SPU} embeddings per SPU)"
        )
        
        # Check SPU credits before generating embeddings (bundled: ceil(misses / EMBEDDINGS_PER_SPU) SPUs)
        # This will raise SPUCreditException if insufficient credits
        await ad.payments.check_spu_limits(organization_id, spus_to_charge)
        
        generated_embeddings = []
        
        # Get provider for SPU metering using the standard method
        provider = ad.llm.get_llm_model_provider(embedding_model)
        
        # Process in batches
        total_cost = 0.0
        for i in range(0, len(cache_misses), EMBEDDING_BATCH_SIZE):
            batch = cache_misses[i:i + EMBEDDING_BATCH_SIZE]
            batch_embeddings, batch_cost = await generate_embeddings_batch(
                analytiq_client,
                batch,
                embedding_model
            )
            generated_embeddings.extend(batch_embeddings)
            total_cost += batch_cost
        
        # Store in cache and fill in embeddings list
        for idx, (cache_miss_idx, embedding) in enumerate(zip(cache_miss_indices, generated_embeddings)):
            chunk = chunks[cache_miss_idx]
            await store_embedding_in_cache(
                analytiq_client,
                chunk.hash,
                embedding_model,
                embedding
            )
            embeddings[cache_miss_idx] = embedding
        
        # Record SPU usage: ceil(cache_misses / EMBEDDINGS_PER_SPU) SPUs
        if cache_miss_count > 0:
            try:
                await ad.payments.record_spu_usage(
                    org_id=organization_id,
                    spus=spus_to_charge,
                    llm_provider=provider,
                    llm_model=embedding_model,
                    actual_cost=total_cost
                )
                logger.info(
                    f"Recorded {spus_to_charge} SPU for {cache_miss_count} embedding(s) generated, "
                    f"actual cost: ${total_cost:.6f}"
                )
            except Exception as e:
                logger.error(f"Error recording SPU usage for embeddings: {e}")
                # Don't fail indexing if SPU recording fails
    
    cache_miss_count = len(cache_misses)
    logger.info(f"Embedding lookup complete: {len(chunks)} total, {cache_miss_count} cache misses, {len(chunks) - cache_miss_count} cache hits")
    
    return embeddings, cache_miss_count

async def get_extracted_indexing_text(
    analytiq_client,
    document_id: str,
    *,
    preprocess: Optional[ChunkingPreprocessConfig] = None,
) -> Optional[ExtractedIndexingText]:
    """
    Get extracted text from a document plus optional per-page character offsets.

    For OCR with ``prefer_markdown``, builds markdown per page (exact page map). Otherwise
    preserves legacy behavior (single ``to_markdown()`` when tables exist, else ``get_text()``).
    Applies ``preprocess_markdown`` to final text for .txt/.md and plain OCR fallbacks.
    """
    cfg = preprocess or ChunkingPreprocessConfig()

    doc = await ad.common.doc.get_doc(analytiq_client, document_id)
    if not doc:
        return None

    file_name = doc.get("user_file_name", "")

    if ad.common.doc.ocr_supported(file_name):
        ocr_json = await ad.ocr.get_ocr_json(analytiq_client, document_id)
        if ocr_json is None:
            text = await ad.ocr.get_ocr_text(analytiq_client, document_id)
            if isinstance(text, str) and text.strip():
                return ExtractedIndexingText(text=preprocess_markdown(text, cfg), page_offsets=[])
            return None

        if ad.ocr.is_pages_markdown_ocr(ocr_json):
            full_md = ad.ocr.export_pages_markdown_full_text(ocr_json)
            return ExtractedIndexingText(
                text=preprocess_markdown(full_md, cfg), page_offsets=[]
            )

        blocks = ad.aws.textract.ocr_result_blocks(ocr_json)
        table_blocks = [b for b in blocks if b.get("BlockType") == "TABLE"]

        try:
            textract_doc = ad.aws.textract.open_textract_document_from_ocr_json(
                ocr_json, document_id=document_id
            )
        except (ValueError, RuntimeError) as e:
            logger.warning(
                "%s: textractor open failed for indexing: %s; falling back to plain OCR text",
                document_id,
                e,
            )
            text = await ad.ocr.get_ocr_text(analytiq_client, document_id)
            if isinstance(text, str) and text.strip():
                return ExtractedIndexingText(text=preprocess_markdown(text, cfg), page_offsets=[])
            return None

        if not textract_doc.pages:
            text = await ad.ocr.get_ocr_text(analytiq_client, document_id)
            if isinstance(text, str) and text.strip():
                return ExtractedIndexingText(text=preprocess_markdown(text, cfg), page_offsets=[])
            return None

        if cfg.prefer_markdown:
            logger.info(f"{document_id}: Exporting per-page OCR markdown for indexing")
            full_md, page_offsets = build_markdown_with_page_offsets(textract_doc, cfg)
            return ExtractedIndexingText(text=full_md, page_offsets=page_offsets)

        if table_blocks:
            logger.info(f"{document_id}: Exporting OCR markdown for indexing")
            return ExtractedIndexingText(text=textract_doc.to_markdown(), page_offsets=[])
        logger.info(f"{document_id}: Exporting OCR text for indexing")
        return ExtractedIndexingText(text=textract_doc.get_text(), page_offsets=[])

    if file_name:
        ext = os.path.splitext(file_name)[1].lower()
        if ext in {".txt", ".md"}:
            original_file = await ad.common.get_file_async(analytiq_client, doc["mongo_file_name"])
            if original_file and original_file["blob"]:
                logger.info(f"{document_id}: Exporting original file content for indexing")
                try:
                    raw = original_file["blob"].decode("utf-8")
                except UnicodeDecodeError:
                    raw = original_file["blob"].decode("latin-1")
                return ExtractedIndexingText(text=preprocess_markdown(raw, cfg), page_offsets=[])

        if ext in {".csv", ".xls", ".xlsx"}:
            original_file = await ad.common.get_file_async(analytiq_client, doc["mongo_file_name"])
            if original_file and original_file["blob"]:
                table_md = _convert_tabular_file_to_markdown(ext, original_file["blob"], document_id)
                if table_md:
                    return ExtractedIndexingText(text=table_md, page_offsets=[])

    logger.info(f"{document_id}: No extractable text. Skipping indexing.")
    return None


def _convert_tabular_file_to_markdown(ext: str, blob: bytes, document_id: str) -> Optional[str]:
    """Convert a CSV / XLS / XLSX binary blob to a markdown table string for indexing."""
    try:
        import io
        import pandas as pd

        if ext == ".csv":
            try:
                df_map = {"Sheet1": pd.read_csv(io.BytesIO(blob))}
            except Exception as e:
                logger.warning(f"{document_id}: Failed to parse CSV: {e}")
                return None
        else:
            # .xls / .xlsx — may contain multiple sheets
            try:
                engine = "openpyxl" if ext == ".xlsx" else None
                df_map = pd.read_excel(io.BytesIO(blob), sheet_name=None, engine=engine)
            except ImportError as e:
                logger.warning(
                    f"{document_id}: Cannot read {ext}: missing dependency ({e}). "
                    "Install openpyxl (for .xlsx) or xlrd (for .xls)."
                )
                return None
            except Exception as e:
                logger.warning(f"{document_id}: Failed to parse {ext}: {e}")
                return None

        parts: List[str] = []
        for sheet_name, df in df_map.items():
            if df.empty:
                continue
            # Drop columns/rows that are entirely NaN
            df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)
            if df.empty:
                continue
            if len(df_map) > 1:
                parts.append(f"## {sheet_name}\n")
            try:
                parts.append(df.to_markdown(index=False))
            except ImportError:
                # tabulate not installed — fall back to CSV-style rendering
                parts.append(df.to_csv(index=False))
            parts.append("\n\n")

        result = "".join(parts).strip()
        if not result:
            return None
        logger.info(f"{document_id}: Converted {ext} ({len(df_map)} sheet(s)) to markdown table ({len(result)} chars)")
        return result

    except Exception as e:
        logger.warning(f"{document_id}: Unexpected error converting {ext} to markdown: {e}")
        return None

async def index_document_in_kb(
    analytiq_client,
    kb_id: str,
    document_id: str,
    organization_id: str
) -> Dict[str, Any]:
    """
    Index a document into a knowledge base.
    
    This implements the "Blue-Green" atomic swap pattern:
    1. Chunk the document text
    2. Get or generate embeddings (with caching)
    3. Atomically replace old vectors with new ones
    4. Update document_index and KB stats
    
    Args:
        analytiq_client: The analytiq client
        kb_id: Knowledge base ID
        document_id: Document ID to index
        organization_id: Organization ID
        
    Returns:
        Dict with indexing results (chunk_count, cache_misses, etc.)
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    
    # Get KB configuration
    kb = await db.knowledge_bases.find_one({"_id": ObjectId(kb_id), "organization_id": organization_id})
    if not kb:
        raise ValueError(f"Knowledge base {kb_id} not found")
    
    if kb.get("status") == "error":
        raise ValueError(f"Knowledge base {kb_id} is in error state")
    
    # Get document
    doc = await ad.common.doc.get_doc(analytiq_client, document_id, organization_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    
    prep = chunking_preprocess_from_kb_dict(kb)
    extracted = await get_extracted_indexing_text(
        analytiq_client, document_id, preprocess=prep
    )
    if extracted is None or not extracted.text.strip():
        logger.warning(f"Document {document_id} has no extractable text. Skipping indexing.")
        return {
            "chunk_count": 0,
            "cache_misses": 0,
            "skipped": True,
            "reason": "no_text"
        }

    text_to_chunk = extracted.text
    page_offsets = extracted.page_offsets

    chunks = await chunk_text(
        text_to_chunk,
        kb["chunker_type"],
        kb["chunk_size"],
        kb["chunk_overlap"],
        preprocess_cfg=prep,
        page_offsets=page_offsets,
    )

    for chunk in chunks:
        hp = (
            extract_heading_path(chunk.text, text_to_chunk, prep.heading_split_depth, chunk_start=chunk.indexed_text_start)
            if prep.prepend_heading_path
            else ""
        )
        chunk.heading_path = hp
        emb_in = f"{hp}\n\n{chunk.text}" if hp else chunk.text
        chunk.embedding_input = emb_in
        chunk.hash = compute_chunk_hash(emb_in)
    
    if not chunks:
        logger.warning(f"Document {document_id} produced no chunks. Skipping indexing.")
        return {
            "chunk_count": 0,
            "cache_misses": 0,
            "skipped": True,
            "reason": "no_chunks"
        }
    
    # Get or generate embeddings
    embeddings, cache_miss_count = await get_or_generate_embeddings(
        analytiq_client,
        chunks,
        kb["embedding_model"],
        organization_id
    )
    
    # Prepare vectors for insertion
    collection_name = f"kb_vectors_{kb_id}"
    vectors_collection = db[collection_name]
    
    # Get document metadata snapshot for filtering
    metadata_snapshot = {
        "document_name": doc.get("user_file_name", ""),
        "tag_ids": doc.get("tag_ids", []),
        "upload_date": doc.get("upload_date"),
        "metadata": doc.get("metadata", {})
    }
    
    now = datetime.now(UTC)
    new_vectors = []
    for chunk, embedding in zip(chunks, embeddings):
        new_vectors.append({
            "organization_id": organization_id,
            "document_id": document_id,
            "chunk_index": chunk.chunk_index,
            "chunk_hash": chunk.hash,
            "chunk_text": chunk.text,
            "embedding": embedding,
            "token_count": chunk.token_count,
            "indexed_text_start": chunk.indexed_text_start,
            "indexed_text_end": chunk.indexed_text_end,
            "heading_path": chunk.heading_path or None,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "chunk_type": chunk.chunk_type,
            "metadata_snapshot": metadata_snapshot,
            "indexed_at": now
        })
    
    # Atomic swap: Use MongoDB transaction for blue-green pattern.
    # Use with_transaction() so the driver auto-retries on WriteConflict (TransientTransactionError)
    # when multiple workers index different docs into the same KB concurrently.
    async def _run_index_txn(session):
        # Delete old vectors for this document
        await vectors_collection.delete_many(
            {"document_id": document_id},
            session=session
        )
        # Insert new vectors
        if new_vectors:
            await vectors_collection.insert_many(new_vectors, session=session)
        # Update or insert document_index entry
        await db.document_index.update_one(
            {
                "kb_id": kb_id,
                "document_id": document_id
            },
            {
                "$set": {
                    "organization_id": organization_id,
                    "kb_id": kb_id,
                    "document_id": document_id,
                    "chunk_count": len(new_vectors),
                    "indexed_at": now
                }
            },
            upsert=True,
            session=session
        )
        # Update KB stats (same KB doc updated by concurrent jobs causes WriteConflict; with_transaction retries)
        total_docs = await db.document_index.count_documents({"kb_id": kb_id}, session=session)
        total_chunks_cursor = db.document_index.aggregate([
            {"$match": {"kb_id": kb_id}},
            {"$group": {"_id": None, "total": {"$sum": "$chunk_count"}}}
        ], session=session)
        total_chunks = await total_chunks_cursor.to_list(length=1)
        total_chunks_count = total_chunks[0]["total"] if total_chunks else 0
        await db.knowledge_bases.update_one(
            {"_id": ObjectId(kb_id)},
            {
                "$set": {
                    "document_count": total_docs,
                    "chunk_count": total_chunks_count,
                    "updated_at": now
                }
            },
            session=session
        )

    try:
        client = analytiq_client.mongodb_async
        async with await client.start_session() as session:
            await session.with_transaction(_run_index_txn)
        logger.info(f"Successfully indexed document {document_id} into KB {kb_id}: {len(new_vectors)} chunks")
        
        return {
            "chunk_count": len(new_vectors),
            "cache_misses": cache_miss_count,
            "cache_hits": len(chunks) - cache_miss_count,
            "skipped": False
        }
        
    except Exception as e:
        logger.error(f"Error indexing document {document_id} into KB {kb_id}: {e}")
        
        # Check if this is a permanent error that should set KB status to error
        if is_permanent_embedding_error(e):
            error_msg = f"Permanent error indexing document {document_id}: {str(e)}"
            try:
                await set_kb_status_to_error(analytiq_client, kb_id, organization_id, error_msg)
            except Exception as status_error:
                logger.error(f"Failed to set KB status to error: {status_error}")
        
        # Transaction will rollback automatically
        raise


async def remove_document_from_kb(
    analytiq_client,
    kb_id: str,
    document_id: str,
    organization_id: str
) -> None:
    """
    Remove a document from a knowledge base.
    
    Args:
        analytiq_client: The analytiq client
        kb_id: Knowledge base ID
        document_id: Document ID to remove
        organization_id: Organization ID
    """
    db = analytiq_client.mongodb_async[analytiq_client.env]
    collection_name = f"kb_vectors_{kb_id}"
    vectors_collection = db[collection_name]
    
    async def _run_remove_txn(session):
        await vectors_collection.delete_many(
            {"document_id": document_id},
            session=session
        )
        await db.document_index.delete_one(
            {"kb_id": kb_id, "document_id": document_id},
            session=session
        )
        total_docs = await db.document_index.count_documents({"kb_id": kb_id}, session=session)
        total_chunks_cursor = db.document_index.aggregate([
            {"$match": {"kb_id": kb_id}},
            {"$group": {"_id": None, "total": {"$sum": "$chunk_count"}}}
        ], session=session)
        total_chunks = await total_chunks_cursor.to_list(length=1)
        total_chunks_count = total_chunks[0]["total"] if total_chunks else 0
        await db.knowledge_bases.update_one(
            {"_id": ObjectId(kb_id)},
            {
                "$set": {
                    "document_count": total_docs,
                    "chunk_count": total_chunks_count,
                    "updated_at": datetime.now(UTC)
                }
            },
            session=session
        )

    try:
        client = analytiq_client.mongodb_async
        async with await client.start_session() as session:
            await session.with_transaction(_run_remove_txn)
        logger.info(f"Removed document {document_id} from KB {kb_id}")
        
    except Exception as e:
        logger.error(f"Error removing document {document_id} from KB {kb_id}: {e}")
        raise
