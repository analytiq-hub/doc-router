# DocRouter Binary Blob Support

This document describes binary data support in the DocRouter flow engine: how document and flow-produced binaries flow through items, are stored in GridFS, served via REST, and displayed in the flow UI.

Reference: [`docs/n8n_binary.md`](./n8n_binary.md) for how n8n implements the equivalent.

---

## 1. Current state

| Component | State |
|---|---|
| `BinaryRef` dataclass (`items.py`) | Done — `mime_type`, `file_name`, `data` (bytes), `storage_id` (str), `file_size` (int) |
| `FlowItem.binary` | Done — `dict[str, BinaryRef]` |
| `get_binary_stream()` helper | Done — in `items.py` |
| `coerce_binary_ref()` deserializer | Done — in `items.py` |
| `_offload_binary_refs()` in engine | Done — offloads inline bytes to `flow_blobs` before persist |
| `BinaryRef` BSON serialization/deserialization | Done — rejects unset `storage_id`; no inline bytes persisted |
| GridFS `blob.py` utilities | Done — `save_blob_async`, `get_blob_async`, `delete_blob_async`, `delete_blobs_by_prefix_async` |
| `worker_flow_cleanup` | Done — hourly worker deletes expired `flow_blobs` + `flow_executions` rows |
| Document streaming endpoint | Done — `GET /v0/orgs/{orgId}/documents/{docId}/file` |
| Manual trigger — `FlowItem.binary` wiring | Done — emits `"pdf"` and `"original"` refs pointing at `files` bucket |
| Webhook trigger — binary upload | Done — stores uploaded files to `flow_blobs` at trigger time; surfaced as `FlowItem.binary` |
| HTTP Request node — binary response | Done — binary `Content-Type` → `BinaryRef` under `binary["data"]` |
| Binary pass-by-reference convention | Done — nodes copy `item.binary` dict; engine skips re-upload for already-stored refs |
| `docrouter.create_document` node | **Not implemented** |
| `GET /executions/{id}/binary-data` endpoint | **Not implemented** |
| Frontend binary display in flows | **Not implemented** |
| SDK `FlowBinaryRef` type | **Not implemented** |

---

## 2. Two GridFS buckets — design rationale

DocRouter uses two GridFS buckets with distinct lifecycles:

| Bucket | Contents | Lifecycle |
|---|---|---|
| **`files`** | DocRouter document originals and PDFs | Permanent — deleted only when the document is explicitly deleted by the user |
| **`flow_blobs`** | Binaries produced during flow execution (HTTP downloads, webhook uploads, etc.) | Transient — deleted when the flow execution is expired/cleaned up |

**Why not a single bucket?**

- **Retention safety.** Flow execution cleanup deletes `flow_blobs` entries by `execution_id` prefix. If flow binaries lived in `files` alongside permanent documents, a bug in the cleanup query could delete a customer's invoice. Separate buckets make the boundary unambiguous.
- **Feature isolation.** Flows can be enabled or licensed independently of the core DocRouter document system. Disabling flows means `flow_blobs` is never written to and can be dropped entirely without touching `files`.
- **Backup and restore.** `files` can be backed up independently on a different schedule than transient execution artifacts.

**The document creation path (deliberate copy)**

When a flow produces a binary (e.g. an HTTP download) and a subsequent `docrouter.create_document` node promotes it into a permanent DocRouter document, the node copies the bytes from `flow_blobs` into `files` and inserts a `docs` collection entry. This copy is intentional — it represents an explicit promotion from transient execution artifact to permanent document. The `flow_blobs` entry is subsequently cleaned up with the execution.

The read path (trigger → downstream nodes) never crosses buckets: the trigger reads document keys from `files` and emits `BinaryRef` pointing there. Only flow-produced binaries go into `flow_blobs`.

---

## 3. `storage_id` format

`BinaryRef.storage_id` encodes the GridFS bucket and key:

```
"files:64f3a1b2.pdf"                         → bucket "files",      key "64f3a1b2.pdf"
"flow_blobs:exec-abc/node-3/0/data.png"      → bucket "flow_blobs", key "exec-abc/node-3/0/data.png"
```

`flow_blobs` keys follow the pattern `{execution_id}/{node_id}/{item_index}/{property_name}`, making per-execution bulk deletion straightforward.

Never store raw bytes in `BinaryRef.data` in persisted run_data. `data` is transient — used only during in-memory execution before the run_data is committed to MongoDB.

---

## 4. DocRouter document integration

### 4.1 Manual trigger node — emit binary ref — Done

**File:** `packages/python/analytiq_data/docrouter_flows/nodes/manual_trigger_node.py`

The manual trigger node emits `FlowItem.binary` with `"pdf"` and `"original"` refs pointing directly at `files` bucket entries. No bytes are copied — only string refs are created.

```python
binary: dict[str, BinaryRef] = {}
if pdf_key := doc.get("pdf_file_name"):
    binary["pdf"] = BinaryRef(
        mime_type="application/pdf",
        file_name=doc.get("user_file_name", "document.pdf"),
        storage_id=f"files:{pdf_key}",
    )
if orig_key := doc.get("mongo_file_name"):
    binary["original"] = BinaryRef(
        mime_type=detect_mime(orig_key),
        file_name=doc.get("user_file_name"),
        storage_id=f"files:{orig_key}",
    )
item = FlowItem(json={...}, binary=binary)
```

### 4.2 `docrouter.create_document` node — Not implemented

A node that promotes a flow-produced binary into a permanent DocRouter document:

1. Accepts a `BinaryRef` from `FlowItem.binary[property]`.
2. Reads bytes from `flow_blobs` via `get_binary_stream()`.
3. Writes bytes to `files` bucket under a new document key.
4. Inserts a `docs` collection entry with the new key and metadata.
5. Emits `FlowItem.json = { "document_id": new_id, ... }` so downstream nodes (OCR, LLM, tagging) can process the new document through the standard DocRouter pipeline.

### 4.3 Webhook trigger — binary upload — Done

**File:** `packages/python/analytiq_data/flows/nodes/trigger_webhook.py`

Uploaded files (multipart or raw binary body) are stored to GridFS `flow_blobs` at trigger time — before the flow execution starts. The stored refs are passed into `FlowItem.binary` directly as `BinaryRef(storage_id=...)` objects; there are no inline bytes to offload later.

```python
# trigger_webhook.py (simplified)
bprops = td_any.get("binary_properties")   # written by the webhook ingestion API
for bp in bprops:
    sid = bp.get("storage_id")             # e.g. "flow_blobs:exec1/webhook/0/data"
    binary_out[name] = ad.flows.BinaryRef(
        mime_type=bp.get("mime_type"),
        file_name=bp.get("file_name"),
        storage_id=sid,
        file_size=bp.get("file_size"),
    )
```

---

## 5. `BinaryRef` field semantics

| Field | Meaning |
|---|---|
| `mime_type` | Always set |
| `file_name` | Optional; used for `Content-Disposition` on download |
| `data` | Transient in-memory bytes only. Never persisted to MongoDB. Cleared after GridFS offload. |
| `storage_id` | `"<bucket>:<key>"` string. Set after offload or when referencing an existing document. |
| `file_size` | Byte count when known (set after offload or by webhook ingestion); used by UI/API. |

A `BinaryRef` is valid if either `data` or `storage_id` is set. After execution completes, all refs must have `storage_id` set.

---

## 6. Engine — offload before persist — Done

**File:** `packages/python/analytiq_data/flows/engine.py`

`_offload_binary_refs(run_data, execution_id, analytiq_client)` is called just before `run_data` is written to MongoDB. It walks all nodes' output items and uploads any inline `BinaryRef.data` to `flow_blobs`, sets `storage_id`, and clears `data`.

The serializer (`_bson_serialize_value`) raises ``RuntimeError`` if `storage_id` is missing or inline `data` was not offloaded — no inline bytes reach MongoDB.

Deserialization reconstructs `BinaryRef` from the stored dict (only `storage_id` is set; `data` is always `None` after loading from MongoDB).

---

## 7. Flow execution cleanup — Done

**File:** `packages/python/worker/worker.py`, `packages/python/analytiq_data/mongodb/blob.py`

### 7.1 Configuration

```
FLOW_EXECUTION_RETENTION_DAYS=30   # env var; default 30
```

### 7.2 `delete_blobs_by_prefix_async` — Done

In `mongodb/blob.py`. Queries `flow_blobs.files` by filename prefix regex and deletes each matching GridFS entry.

### 7.3 `worker_flow_cleanup` — Done

Single coroutine registered in `start_workers()` alongside `worker_kb_reconcile`. Runs once per hour. Finds `flow_executions` with terminal status and `finished_at` older than the retention window, deletes their `flow_blobs` entries by `{execution_id}/` prefix, then deletes the `flow_executions` document.

```python
expired = await db.flow_executions.find({
    "finished_at": {"$lt": cutoff},
    "status": {"$in": ["success", "error", "cancelled"]},
}).to_list(length=None)

for execution in expired:
    execution_id = str(execution["_id"])
    blobs_deleted = await ad.mongodb.blob.delete_blobs_by_prefix_async(
        analytiq_client, bucket="flow_blobs", prefix=f"{execution_id}/"
    )
    await db.flow_executions.delete_one({"_id": execution["_id"]})
```

### 7.4 What is never cleaned up

- **`files` bucket** — never touched. Document permanence is unconditional.
- **Running executions** — `status` filter excludes `"running"` and `"pending"` rows.

---

## 8. Binary pass-by-reference and node authoring convention — Done

### 8.1 No copies between nodes

`BinaryRef.storage_id` is a string pointer. When a node receives a `FlowItem` with binary refs and does not modify the binary content, it must include the same `BinaryRef` objects unchanged in its output `FlowItem`. The engine's `_offload_binary_refs` only writes to GridFS when `ref.data` is set and `ref.storage_id` is not — so passing through an already-stored ref produces zero GridFS writes and no duplication.

Multiple nodes' `run_data` entries can all reference the same `storage_id` string. The underlying file exists exactly once.

**Example — 5-node flow, large PDF that no node modifies:**

```
trigger → extract-text → classify → tag-document → notify-webhook
```

- `trigger` emits `BinaryRef(storage_id="files:abc.pdf")` — no upload.
- Each subsequent node passes the same `BinaryRef` through — no uploads.
- Total GridFS writes for the binary: **zero**.

**Example — HTTP Request node downloads a new binary:**

```
trigger → http-request → ocr
```

- `http-request` sets `ref.data = response.content` — inline bytes in memory.
- Engine offloads once to `flow_blobs:exec1/http-request/0/data`, sets `storage_id`, clears `ref.data`.
- `ocr` receives `BinaryRef(storage_id="flow_blobs:exec1/http-request/0/data")` — no further writes.

**Cleanup implication:** prefix deletion of `flow_blobs/{execution_id}/` only hits files that were actually written during that execution. Passthrough nodes contribute nothing to `flow_blobs`.

### 8.2 Node authoring rules

1. **To read binary content:** use `get_binary_stream()` (§8.3). Never access `ref.data` directly.
2. **To pass binary through unchanged:** copy the incoming `BinaryRef` reference into the output `FlowItem.binary` under the same (or a chosen) property name. Do not set `ref.data`.
3. **To produce new binary content:** create a new `BinaryRef` with `data=<bytes>` and no `storage_id`. The engine offloads it before persist.
4. **Do not drop binary refs silently.** If a node ignores binary input (e.g. a classifier that only reads JSON), it should still forward the incoming `binary` dict so downstream nodes retain access.

### 8.3 `get_binary_stream()` — Done

**File:** `packages/python/analytiq_data/flows/items.py`

```python
async def get_binary_stream(ref: BinaryRef, analytiq_client) -> bytes:
    """Return bytes for a BinaryRef — from memory or GridFS."""
    if ref.data is not None:
        return ref.data
    sid = ref.storage_id
    if not sid:
        raise ValueError("BinaryRef has neither data nor storage_id")
    parts = sid.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid BinaryRef.storage_id: {sid!r}")
    bucket, key = parts
    result = await ad.blob.get_blob_async(analytiq_client, bucket=bucket, key=key)
    if not result:
        raise ValueError(f"Binary blob not found for storage_id={sid!r}")
    return result["blob"]
```

Works transparently across both buckets.

---

## 9. HTTP Request node — binary response — Done

**File:** `packages/python/analytiq_data/flows/nodes/http_request.py`

When `Content-Type` indicates binary content, the response bytes are attached as `BinaryRef(data=resp.content)` under `binary["data"]`. The output `item.json` always contains `status_code` and `headers` for binary responses (the `full_response` flag is not checked in this path). Incoming `item.binary` refs are merged into the output — no upstream refs are dropped.

The inline bytes are offloaded to `flow_blobs` by the engine before run_data is persisted.

---

## 10. REST endpoint — serve flow binary data — Not implemented

Add to `packages/python/app/routes/flows.py`:

```
GET /v0/orgs/{orgId}/executions/{executionId}/binary-data
    ?node_id=<id>&slot=0&item_index=0&property=data&action=view|download
```

Implementation:
1. Load the `flow_executions` document; verify `organization_id`.
2. Walk `run_data[node_id].data.main[slot][item_index].binary[property]` to find the `BinaryRef`.
3. Parse `storage_id` → `bucket:key`, fetch from GridFS via `get_blob_async`.
4. Return `StreamingResponse` with correct `Content-Type` and `Content-Disposition`.

For document refs (`storage_id = "files:…"`), this streams the same bytes as `GET /documents/{docId}/file` but addressed by flow output position.

---

## 11. Frontend — Not implemented

### 11.1 Flow output panel — binary display

**File:** `packages/typescript/frontend/src/components/flows/flowNodeIoPreview.ts`

Currently only `item.json` is displayed. Add detection and rendering for `item.binary`:

- For each named binary property in an item, show a pill with the property name and `mime_type`.
- Clicking opens a preview or triggers a download via the binary endpoint (§10).
- Render by `mime_type` category:
  - `image/*` → inline `<img>`
  - `application/pdf` → PDF embed or "Open PDF" link
  - `audio/*`, `video/*` → media player
  - other → download link with filename

### 11.2 URL construction

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

### 11.3 SDK types — Not implemented

Add to `packages/typescript/sdk/src/types/flows.ts`:

```typescript
export interface FlowBinaryRef {
  mime_type: string;
  file_name?: string | null;
  storage_id?: string | null;
  file_size?: number | null;
}

export interface FlowItemData {
  json: Record<string, unknown>;
  binary?: Record<string, FlowBinaryRef>;
}
```

---

## 12. What is implemented vs. what remains

### Implemented

| Component | Notes |
|---|---|
| `BinaryRef` dataclass | `mime_type`, `file_name`, `data`, `storage_id`, `file_size` |
| `FlowItem.binary` field | `dict[str, BinaryRef]` |
| `get_binary_stream()` | In `items.py`; transparent across both buckets |
| `coerce_binary_ref()` | Deserializer in `items.py` |
| `_offload_binary_refs()` in engine | Flushes inline bytes to `flow_blobs` before persist |
| BSON serialization guard | Rejects any `BinaryRef` without `storage_id` at persist time (`RuntimeError`) |
| `delete_blobs_by_prefix_async` | In `mongodb/blob.py` |
| `worker_flow_cleanup` | Hourly; deletes expired `flow_blobs` + `flow_executions` |
| GridFS `blob.py` utilities | `save_blob_async`, `get_blob_async`, `delete_blob_async` |
| Manual trigger — binary wiring | `"pdf"` and `"original"` refs into `FlowItem.binary` |
| Webhook trigger — binary upload | Files stored to `flow_blobs` at trigger time; emitted as `FlowItem.binary` |
| HTTP Request node — binary response | `BinaryRef` under `binary["data"]` for binary `Content-Type` |
| Binary pass-by-reference convention | Engine skips re-upload for already-stored refs; nodes copy `item.binary` |
| Execution blob HTTP API | §10 — `GET .../blob?storage_id=flow_blobs:…` |
| Frontend binary UX | §11 — `IoViewer` / **`IoBinaryPanel`** + `flowExecutionBlob.ts` |

### Not yet implemented (or intentionally narrow)

| Component | Notes |
|---|---|
| `docrouter.create_document` node | Promote flow binary to permanent DocRouter document (§4.2) |
| Coordinate-based blob API | Resolve blob from `{ node_id, slot, item_index, property }` without client-supplied `storage_id` |
| Execution API for `files:` binaries | Document file endpoint by `document_id`, not this `/blob` route |
| SDK `FlowBinaryRef` / item types | §11.3 |

---

## 13. Build order — remaining steps

**Step 1 — `docrouter.create_document` node**

Implement the promotion node: `flow_blobs` → `files` + `docs` entry. Enables end-to-end: webhook receives PDF → create document → OCR → LLM.

**Step 2 — Broader binary API (optional)**

Coordinate-based download, or authenticated `files:` streaming from execution context if product needs it.

**Step 3 — SDK and polish**

Add `FlowBinaryRef` to the SDK; optional in-panel preview for `files:` refs similar to `flow_blobs:`.
