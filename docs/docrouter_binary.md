# DocRouter Binary Blob Support — Implementation Plan

This document plans how to extend the DocRouter flow engine to fully support binary data: flowing document binaries through items, storing flow-produced binaries in GridFS, serving them via a REST endpoint, and displaying them in the flow UI.

Reference: [`docs/n8n_binary.md`](./n8n_binary.md) for how n8n implements the equivalent.

---

## 1. Current state

| Component | State |
|---|---|
| `BinaryRef` dataclass (`items.py`) | Defined — `mime_type`, `file_name`, `data` (bytes), `storage_id` (str) |
| `FlowItem.binary` | Defined — `dict[str, BinaryRef]` |
| `BinaryRef` serialization in run_data | Persists inline `data` bytes to MongoDB — **wrong for large blobs** |
| GridFS storage (`mongodb/blob.py`) | Fully implemented — `save_blob_async`, `get_blob_async`, `delete_blob_async` |
| Document streaming endpoint | `GET /v0/orgs/{orgId}/documents/{docId}/file` — streams raw binary from GridFS |
| Document binary in flow items | **Not wired** — trigger emits only metadata JSON, not a binary ref |
| `storage_id` field | Defined but never populated or read |
| Binary endpoint for flow run data | **Does not exist** |
| Frontend binary display in flows | **Not implemented** |

The foundation is solid. The main gaps are: wiring documents into `FlowItem.binary`, using `storage_id` instead of inline bytes for persistence, the serve endpoint, and frontend display.

---

## 2. `storage_id` format

`BinaryRef.storage_id` uses the same `"<bucket>:<key>"` convention as GridFS bucket/key pairs:

```
"files:64f3a1b2.pdf"           → GridFS bucket "files", key "64f3a1b2.pdf"  (existing document)
"flow_blobs:exec-abc/node-3/0/data.png"  → GridFS bucket "flow_blobs", key for a flow-produced binary
```

Two GridFS buckets:
- **`files`** — existing document store (originals and PDFs). DocRouter documents already live here. Flow items reference them read-only.
- **`flow_blobs`** — binaries produced during flow execution (HTTP downloads, code node outputs, etc.). Keyed by `{execution_id}/{node_id}/{item_index}/{property_name}`.

Never store raw bytes in `BinaryRef.data` in persisted run_data. `data` is transient — used only during in-memory execution before the run_data is committed to MongoDB.

---

## 3. DocRouter document integration (key design)

Documents are the central entity in DocRouter. When a flow is triggered with a document, the document's binary content must flow into `FlowItem.binary` as a named property — just as it would in any binary-aware flow system.

### 3.1 Trigger node — emit binary ref

The manual trigger node (`docrouter.trigger.manual`) currently emits only document metadata in `FlowItem.json`. Extend it to also populate `FlowItem.binary`:

```python
# In manual_trigger_node.py execute()
doc = await db.docs.find_one({"document_id": document_id, ...})

# Determine which GridFS key to reference
pdf_key = doc.get("pdf_file_name")      # e.g. "64f3a1b2.pdf"
orig_key = doc.get("mongo_file_name")   # e.g. "64f3a1b2.docx"

binary: dict[str, BinaryRef] = {}
if pdf_key:
    binary["pdf"] = BinaryRef(
        mime_type="application/pdf",
        file_name=doc.get("user_file_name", "document.pdf"),
        storage_id=f"files:{pdf_key}",
    )
if orig_key:
    binary["original"] = BinaryRef(
        mime_type=detect_mime(orig_key),
        file_name=doc.get("user_file_name"),
        storage_id=f"files:{orig_key}",
    )

item = FlowItem(json={"document_id": document_id, "document": doc_metadata}, binary=binary)
```

This means every node downstream of a document trigger has access to the document binary by name (`"pdf"` or `"original"`) without making any additional API calls.

### 3.2 Webhook trigger — accept binary uploads

When a webhook receives a multipart upload or a raw binary body, create a `FlowItem` with the binary attached:

```python
# Parse multipart or raw body from request
body_bytes: bytes = ...
binary["data"] = BinaryRef(
    mime_type=content_type,
    file_name=filename,
    data=body_bytes,  # transient — offloaded before persist
)
```

The binary is held in `data` during the execution step that produces it. Before `run_data` is committed to MongoDB, the engine flushes all in-memory `BinaryRef.data` to GridFS (see §5).

---

## 4. `BinaryRef` changes

No new fields are needed. The semantics of the existing fields become well-defined:

| Field | Meaning |
|---|---|
| `mime_type` | Always set |
| `file_name` | Optional; used for `Content-Disposition` on download |
| `data` | Transient in-memory bytes only. Never persisted to MongoDB. Cleared after GridFS offload. |
| `storage_id` | `"<bucket>:<key>"` string. Set after offload or when referencing an existing document. |

A `BinaryRef` is valid if either `data` or `storage_id` is set. After execution completes, all refs must have `storage_id` set (no inline bytes in persisted run_data).

---

## 5. Engine changes — offload before persist

**File:** `packages/python/analytiq_data/flows/engine.py`

Add `_offload_binary_refs(run_data, execution_id, analytiq_client)` called just before `run_data` is written to MongoDB:

```python
async def _offload_binary_refs(
    run_data: dict[str, Any],
    execution_id: str,
    analytiq_client: Any,
) -> None:
    """
    Walk run_data, find BinaryRef objects with inline `data`, upload to GridFS
    under the "flow_blobs" bucket, replace with storage_id, clear data.
    """
    for node_id, entry in run_data.items():
        for slot in (entry.get("data") or {}).get("main") or []:
            if not isinstance(slot, list):
                continue
            for item in slot:
                if not isinstance(item, FlowItem):
                    continue
                for prop, ref in item.binary.items():
                    if ref.data and not ref.storage_id:
                        key = f"{execution_id}/{node_id}/{prop}"
                        await ad.blob.save_blob_async(
                            analytiq_client,
                            bucket="flow_blobs",
                            key=key,
                            blob=ref.data,
                            metadata={"mime_type": ref.mime_type, "file_name": ref.file_name or ""},
                        )
                        ref.storage_id = f"flow_blobs:{key}"
                        ref.data = None
```

Call this before every `run_data` persistence point in the engine.

### Serialization

Update `_bson_serialize_value` in `engine.py` to assert no inline `data` survives to persistence:

```python
if isinstance(obj, ad.flows.BinaryRef):
    # data must have been offloaded before serialization
    assert obj.data is None, f"BinaryRef.data not offloaded for {obj.file_name}"
    return {"mime_type": obj.mime_type, "file_name": obj.file_name, "storage_id": obj.storage_id}
```

And the corresponding deserialization (`_bson_deserialize_value`) reconstructs `BinaryRef` with only `storage_id`.

---

## 6. Node helper — `get_binary_stream()`

Add to `ExecutionContext` (or as a standalone utility in `credentials.py`-style):

```python
async def get_binary_stream(ref: BinaryRef, analytiq_client) -> bytes:
    """Return the bytes for a BinaryRef, from memory or GridFS."""
    if ref.data is not None:
        return ref.data
    if ref.storage_id:
        bucket, key = ref.storage_id.split(":", 1)
        result = await ad.blob.get_blob_async(analytiq_client, bucket=bucket, key=key)
        return result["blob"]
    raise ValueError("BinaryRef has neither data nor storage_id")
```

Nodes that need to read binary content (e.g. the HTTP Request node writing to a file, or a future PDF-parse node) call this helper.

---

## 7. HTTP Request node — binary response

**File:** `packages/python/analytiq_data/flows/nodes/http_request.py`

When the response `Content-Type` indicates binary content, store it as a `BinaryRef` on the output item instead of (or alongside) the JSON body:

```python
BINARY_CONTENT_TYPES = ("application/pdf", "image/", "audio/", "video/",
                         "application/zip", "application/gzip", "application/octet-stream")

if any(ct in response.headers.get("content-type", "") for ct in BINARY_CONTENT_TYPES):
    content_type = response.headers.get("content-type", "application/octet-stream").split(";")[0]
    file_name = _extract_filename(response.headers)
    out_item = FlowItem(
        json={"status_code": response.status_code, "headers": dict(response.headers)},
        binary={"data": BinaryRef(mime_type=content_type, file_name=file_name, data=response.content)},
        meta=item.meta,
        paired_item=item.paired_item,
    )
```

The inline `data` bytes are held transiently and offloaded by the engine before run_data is persisted (§5).

---

## 8. REST endpoint — serve flow binary data

Add to `packages/python/app/routes/flows.py`:

```
GET /v0/orgs/{orgId}/executions/{executionId}/binary-data
    ?node_id=<id>&slot=0&item_index=0&property=data
    &action=view|download
```

Implementation:
1. Load the `flow_executions` document; verify `organization_id`.
2. Walk `run_data[node_id].data.main[slot][item_index].binary[property]` to find the `BinaryRef`.
3. Parse `storage_id` → `bucket:key`, fetch from GridFS via `get_blob_async`.
4. Return `StreamingResponse` with correct `Content-Type` and `Content-Disposition`.

For document references (`storage_id = "files:…"`), this endpoint is equivalent to `GET /documents/{docId}/file` but keyed by position in the flow output rather than document ID — useful when the flow transforms or combines documents.

---

## 9. Frontend

### 9.1 Flow output panel — binary display

**File:** `packages/typescript/frontend/src/components/flows/flowNodeIoPreview.ts` (and the panel component that uses it)

Currently only `item.json` is displayed. Add detection and rendering for `item.binary`:

- For each named binary property in an item, show a pill/chip with the property name and `mime_type`.
- Clicking it opens a preview or downloads via the binary endpoint (§8).
- Render by `mime_type` category:
  - `image/*` → inline `<img>`
  - `application/pdf` → PDF embed or "Open PDF" link
  - `audio/*`, `video/*` → media player
  - other → download link with filename

### 9.2 URL construction

```typescript
function getFlowBinaryUrl(
  orgId: string,
  executionId: string,
  nodeId: string,
  slot: number,
  itemIndex: number,
  property: string,
  action: 'view' | 'download' = 'view',
): string {
  const url = new URL(`/fastapi/v0/orgs/${orgId}/executions/${executionId}/binary-data`);
  url.searchParams.set('node_id', nodeId);
  url.searchParams.set('slot', String(slot));
  url.searchParams.set('item_index', String(itemIndex));
  url.searchParams.set('property', property);
  url.searchParams.set('action', action);
  return url.toString();
}
```

### 9.3 SDK types

Add to `packages/typescript/sdk/src/types/flows.ts`:

```typescript
export interface FlowBinaryRef {
  mime_type: string;
  file_name?: string | null;
  storage_id?: string | null;   // set when persisted; absent for in-memory (not sent to frontend)
}

// Extend FlowItem (already in FlowExecution.run_data shape)
export interface FlowItemData {
  json: Record<string, unknown>;
  binary?: Record<string, FlowBinaryRef>;
}
```

---

## 10. What is implemented vs. what remains

### Implemented

| Component | Status |
|---|---|
| `BinaryRef` dataclass | Done |
| `FlowItem.binary` field | Done |
| GridFS `blob.py` utilities | Done |
| Document streaming endpoint | Done |
| `BinaryRef` BSON serialization | Done (but persists inline bytes — needs fix) |

### Not yet implemented

| Component | Notes |
|---|---|
| Trigger node populates `FlowItem.binary` | Wire document GridFS keys into binary refs on trigger |
| Engine `_offload_binary_refs()` | Flush inline bytes to `flow_blobs` GridFS before persist |
| Serialization assert — no inline bytes | Prevent accidental large BSON documents |
| `get_binary_stream()` node helper | Utility for nodes that need to read binary content |
| HTTP Request node binary response | Produce `BinaryRef` for binary content-types |
| Webhook trigger binary upload | Attach uploaded file as `BinaryRef` on trigger item |
| `GET /executions/{id}/binary-data` endpoint | Serve flow binary from GridFS |
| Frontend binary display in flow output panel | Render binary chips, preview, download |
| SDK `FlowBinaryRef` type | TypeScript type for binary refs in flow item data |

---

## 11. Build order

**Step 1 — Offload + serialization (backend only)**

Fix `_bson_serialize_value` to assert no inline bytes, implement `_offload_binary_refs()`, call it before every run_data persist. No visible change to users, but prevents runaway BSON document sizes.

**Step 2 — Document trigger wiring**

Populate `FlowItem.binary` with `"pdf"` and `"original"` refs in the manual trigger node. Downstream nodes immediately gain access to document bytes via `get_binary_stream()`.

**Step 3 — `get_binary_stream()` helper**

Add to `ExecutionContext` or as a utility. Used by nodes in subsequent steps.

**Step 4 — HTTP Request node binary response**

Detect binary `Content-Type`, attach `BinaryRef` to output item. The offload step (Step 1) handles persistence.

**Step 5 — Webhook binary upload**

Parse multipart/raw binary body, attach `BinaryRef`. Same offload path.

**Step 6 — Binary serve endpoint**

Add `GET /v0/orgs/{orgId}/executions/{executionId}/binary-data`. Unlocks the frontend.

**Step 7 — Frontend binary display**

Extend `flowNodeIoPreview` and the output panel to detect and render binary properties. Add `getFlowBinaryUrl()` helper.
