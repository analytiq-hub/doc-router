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

## 2. Two GridFS buckets — design rationale

DocRouter uses two GridFS buckets with distinct lifecycles:

| Bucket | Contents | Lifecycle |
|---|---|---|
| **`files`** | DocRouter document originals and PDFs | Permanent — deleted only when the document is explicitly deleted by the user |
| **`flow_blobs`** | Binaries produced during flow execution (HTTP downloads, webhook uploads, etc.) | Transient — deleted when the flow execution is expired/cleaned up |

**Why not a single bucket?**

- **Retention safety.** Flow execution cleanup must delete `flow_blobs` entries by `execution_id` prefix. If flow binaries lived in `files` alongside permanent documents, a bug in the cleanup query could delete a customer's invoice. Separate buckets make the boundary unambiguous.
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

Documents are the central entity in DocRouter. When a flow is triggered with a document, the document's binary content must flow into `FlowItem.binary` as named properties.

### 4.1 Trigger node — emit binary ref

The manual trigger node (`docrouter.trigger.manual`) currently emits only document metadata in `FlowItem.json`. Extend it to also populate `FlowItem.binary`:

```python
# In manual_trigger_node.py execute()
doc = await db.docs.find_one({"document_id": document_id, ...})

pdf_key  = doc.get("pdf_file_name")    # e.g. "64f3a1b2.pdf"
orig_key = doc.get("mongo_file_name")  # e.g. "64f3a1b2.docx"

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

Every node downstream of a document trigger has access to the document binary by name (`"pdf"` or `"original"`) without any additional API calls. No bytes are copied — the refs point directly at the existing `files` bucket entries.

### 4.2 `docrouter.create_document` node

A new node that promotes a flow-produced binary into a permanent DocRouter document:

1. Accepts a `BinaryRef` from `FlowItem.binary[property]`.
2. Reads bytes from `flow_blobs` via `get_binary_stream()`.
3. Writes bytes to `files` bucket under a new document key.
4. Inserts a `docs` collection entry with the new key and metadata.
5. Emits `FlowItem.json = { "document_id": new_id, ... }` so downstream nodes (OCR, LLM, tagging) can process the new document through the standard DocRouter pipeline.

This makes the promotion from transient flow binary to permanent document explicit and visible in the flow graph.

### 4.3 Webhook trigger — accept binary uploads

When a webhook receives a multipart upload or a raw binary body:

```python
binary["data"] = BinaryRef(
    mime_type=content_type,
    file_name=filename,
    data=body_bytes,  # transient — offloaded to flow_blobs before persist
)
```

The bytes are held in `data` during the execution step and offloaded to `flow_blobs` before run_data is committed (see §6).

---

## 5. `BinaryRef` field semantics

No new fields are needed. The semantics of the existing fields become well-defined:

| Field | Meaning |
|---|---|
| `mime_type` | Always set |
| `file_name` | Optional; used for `Content-Disposition` on download |
| `data` | Transient in-memory bytes only. Never persisted to MongoDB. Cleared after GridFS offload. |
| `storage_id` | `"<bucket>:<key>"` string. Set after offload or when referencing an existing document. |

A `BinaryRef` is valid if either `data` or `storage_id` is set. After execution completes, all refs must have `storage_id` set.

---

## 6. Engine changes — offload before persist

**File:** `packages/python/analytiq_data/flows/engine.py`

Add `_offload_binary_refs(run_data, execution_id, analytiq_client)` called just before `run_data` is written to MongoDB:

```python
async def _offload_binary_refs(
    run_data: dict[str, Any],
    execution_id: str,
    analytiq_client: Any,
) -> None:
    """Walk run_data; upload any inline BinaryRef.data to flow_blobs, set storage_id, clear data."""
    for node_id, entry in run_data.items():
        for slot in (entry.get("data") or {}).get("main") or []:
            if not isinstance(slot, list):
                continue
            for item_idx, item in enumerate(slot):
                if not isinstance(item, FlowItem):
                    continue
                for prop, ref in item.binary.items():
                    if ref.data and not ref.storage_id:
                        key = f"{execution_id}/{node_id}/{item_idx}/{prop}"
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

### Serialization

Update `_bson_serialize_value` to assert no inline bytes survive to persistence:

```python
if isinstance(obj, ad.flows.BinaryRef):
    assert obj.data is None, f"BinaryRef.data not offloaded for {obj.file_name}"
    return {"mime_type": obj.mime_type, "file_name": obj.file_name, "storage_id": obj.storage_id}
```

Deserialization (`_bson_deserialize_value`) reconstructs `BinaryRef` with only `storage_id` set.

---

## 7. Flow execution cleanup

Flow executions have a configurable retention period. When an execution expires, its `flow_blobs` entries must be deleted alongside the `flow_executions` document. No retention system exists today — it must be built from scratch.

### 7.1 Configuration

```
FLOW_EXECUTION_RETENTION_DAYS=30   # env var; default 30
```

Read at worker startup via `int(os.getenv("FLOW_EXECUTION_RETENTION_DAYS", "30"))`. No per-org override in the first version; a single global value is sufficient.

### 7.2 `delete_blobs_by_prefix_async` — new utility in `mongodb/blob.py`

```python
async def delete_blobs_by_prefix_async(analytiq_client, bucket: str, prefix: str) -> int:
    """Delete all GridFS entries in `bucket` whose filename starts with `prefix`.
    Returns the number of files deleted."""
    db = analytiq_client.mongodb_async[analytiq_client.env]
    files_col = db[f"{bucket}.files"]
    file_docs = await files_col.find(
        {"filename": {"$regex": f"^{re.escape(prefix)}"}},
        {"_id": 1, "filename": 1},
    ).to_list(length=None)
    if not file_docs:
        return 0
    fs_bucket = AsyncIOMotorGridFSBucket(db, bucket_name=bucket)
    for doc in file_docs:
        await fs_bucket.delete(doc["_id"])
    logger.debug(f"Deleted {len(file_docs)} blob(s) with prefix {bucket}/{prefix}")
    return len(file_docs)
```

Add `import re` at the top of `blob.py`.

### 7.3 `worker_flow_cleanup` coroutine in `worker.py`

Follows the same pattern as `worker_kb_reconcile`: a single long-running coroutine registered once in `start_workers()`.

```python
async def worker_flow_cleanup(worker_id: str) -> None:
    """Periodic cleanup of expired flow executions and their flow_blobs."""
    ENV = os.getenv("ENV", "dev")
    analytiq_client = ad.common.get_analytiq_client(env=ENV, name=worker_id)
    retention_days = int(os.getenv("FLOW_EXECUTION_RETENTION_DAYS", "30"))
    logger.info(f"Starting flow cleanup worker {worker_id} (retention={retention_days}d)")

    last_heartbeat = datetime.now(UTC)
    CHECK_INTERVAL_SECS = 3600  # Run once per hour

    while True:
        try:
            now = datetime.now(UTC)

            if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL_SECS:
                logger.info(f"Flow cleanup worker {worker_id} heartbeat")
                last_heartbeat = now

            cutoff = now - timedelta(days=retention_days)
            db = analytiq_client.mongodb_async[ENV]

            expired = await db.flow_executions.find(
                {
                    "finished_at": {"$lt": cutoff},
                    "status": {"$in": ["success", "error", "cancelled"]},
                }
            ).to_list(length=None)

            logger.info(f"Flow cleanup: found {len(expired)} expired execution(s) (cutoff={cutoff.date()})")

            for execution in expired:
                execution_id = str(execution["_id"])
                blobs_deleted = await ad.blob.delete_blobs_by_prefix_async(
                    analytiq_client, bucket="flow_blobs", prefix=f"{execution_id}/"
                )
                await db.flow_executions.delete_one({"_id": execution["_id"]})
                logger.info(f"Cleaned up execution {execution_id}: {blobs_deleted} blob(s) deleted")

            await asyncio.sleep(CHECK_INTERVAL_SECS)

        except asyncio.CancelledError:
            logger.warning(f"Flow cleanup worker {worker_id} cancelled")
            raise
        except Exception as e:
            logger.error(f"Flow cleanup worker {worker_id} error: {e}")
            await asyncio.sleep(300)  # Back off 5 min on errors
```

Add `from datetime import timedelta` to the imports in `worker.py` (alongside the existing `datetime, UTC` import).

### 7.4 Registration in `start_workers()`

```python
tasks.append(asyncio.create_task(worker_kb_reconcile("kb_reconcile_0"), name="kb_reconcile_0"))
tasks.append(asyncio.create_task(worker_flow_cleanup("flow_cleanup_0"), name="flow_cleanup_0"))
```

A single instance is sufficient — there is no concurrency risk because the cleanup loop sleeps for an hour between passes and only touches `flow_executions` rows with terminal status.

### 7.5 What is never cleaned up

- **`files` bucket** — never touched. Document permanence is unconditional.
- **Running executions** — `status` filter excludes `"running"` and `"pending"` rows.
- **`flow_executions` documents for active flows** — only rows with a `finished_at` timestamp older than the retention window are eligible.

---

## 8. Binary pass-by-reference and node authoring convention

### 8.1 No copies between nodes

`BinaryRef.storage_id` is a string pointer. When a node receives a `FlowItem` with binary refs and does not modify the binary content, it must include the same `BinaryRef` objects unchanged in its output `FlowItem`. The engine's `_offload_binary_refs` (§6) only writes to GridFS when `ref.data` is set and `ref.storage_id` is not — so passing through an already-stored ref produces zero GridFS writes and no duplication.

Multiple nodes' `run_data` entries can all reference the same `storage_id` string. The underlying file exists exactly once.

**Example — 5-node flow, large PDF that no node modifies:**

```
trigger → extract-text → classify → tag-document → notify-webhook
```

- `trigger` emits `BinaryRef(storage_id="files:abc.pdf")` — points at existing GridFS entry, no upload.
- Each subsequent node passes the same `BinaryRef` through — no uploads.
- `run_data` for all five nodes contains references to `"files:abc.pdf"`. Total GridFS writes for the binary: **zero**.

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
4. **Do not drop binary refs silently.** If a node ignores binary input (e.g. a classifier that only reads JSON), it should still forward the incoming `binary` dict so downstream nodes retain access. Dropping refs means they are lost from `run_data` at that point forward.

### 8.3 `get_binary_stream()` helper

Add as a utility (e.g. in `items.py` or alongside `credentials.py`):

```python
async def get_binary_stream(ref: BinaryRef, analytiq_client) -> bytes:
    """Return bytes for a BinaryRef — from memory or GridFS."""
    if ref.data is not None:
        return ref.data
    if ref.storage_id:
        bucket, key = ref.storage_id.split(":", 1)
        result = await ad.blob.get_blob_async(analytiq_client, bucket=bucket, key=key)
        return result["blob"]
    raise ValueError("BinaryRef has neither data nor storage_id")
```

Works transparently across both buckets — the caller does not need to know where the binary lives.

---

## 9. HTTP Request node — binary response

**File:** `packages/python/analytiq_data/flows/nodes/http_request.py`

When `Content-Type` indicates binary content, attach a `BinaryRef` to the output item:

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

The inline bytes are offloaded to `flow_blobs` by the engine before run_data is persisted (§6). This node produces a new binary; see §8.1 for how passthrough nodes handle the same ref without re-writing.

---

## 10. REST endpoint — serve flow binary data

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

For document refs (`storage_id = "files:…"`), this streams the same bytes as `GET /documents/{docId}/file` but addressed by flow output position — useful when viewing what a node received or produced.

---

## 11. Frontend

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

### 11.3 SDK types

Add to `packages/typescript/sdk/src/types/flows.ts`:

```typescript
export interface FlowBinaryRef {
  mime_type: string;
  file_name?: string | null;
  storage_id?: string | null;
}

export interface FlowItemData {
  json: Record<string, unknown>;
  binary?: Record<string, FlowBinaryRef>;
}
```

---

## 12. What is implemented vs. what remains

### Implemented

| Component | Status |
|---|---|
| `BinaryRef` dataclass | Done |
| `FlowItem.binary` field | Done |
| GridFS `blob.py` utilities | Done |
| Document streaming endpoint | Done |
| `BinaryRef` BSON serialization | Done (but persists inline bytes — needs fix per §6) |

### Not yet implemented

| Component | Notes |
|---|---|
| Trigger node populates `FlowItem.binary` | Wire document GridFS keys into binary refs (§4.1) |
| `docrouter.create_document` node | Promote flow binary to permanent DocRouter document (§4.2) |
| Engine `_offload_binary_refs()` | Flush inline bytes to `flow_blobs` before persist (§6) |
| Serialization assert — no inline bytes | Prevent large BSON documents (§6) |
| `delete_blobs_by_prefix_async` in `blob.py` | Needed for execution cleanup (§7) |
| Flow execution cleanup / retention | Delete `flow_blobs` entries on execution expiry (§7) |
| Pass-by-reference convention + `get_binary_stream()` | Node authoring rules and transparent read from either bucket (§8) |
| HTTP Request node binary response | Produce `BinaryRef` for binary content-types (§9) |
| Webhook trigger binary upload | Attach uploaded file as `BinaryRef` (§4.3) |
| `GET /executions/{id}/binary-data` endpoint | Serve flow binary from GridFS (§10) |
| Frontend binary display in flow output panel | Render binary chips, preview, download (§11) |
| SDK `FlowBinaryRef` type | TypeScript type for binary refs in flow item data (§11.3) |

---

## 13. Build order

**Step 1 — Offload + serialization**

Implement `_offload_binary_refs()`, add the serialization assert, call offload before every run_data persist. No visible change to users; prevents runaway BSON sizes.

**Step 2 — `delete_blobs_by_prefix_async` + execution cleanup**

Add prefix-delete to `blob.py`. Wire into the worker's execution expiry path. Keeps `flow_blobs` from growing unboundedly.

**Step 3 — Document trigger wiring**

Populate `FlowItem.binary` with `"pdf"` and `"original"` refs in the manual trigger node. Downstream nodes gain access to document bytes immediately.

**Step 4 — Pass-by-reference convention + `get_binary_stream()` helper**

Document the node authoring rules (§8.1–8.2) and add `get_binary_stream()` (§8.3). Required by Steps 5–7. Ensures node authors know to forward binary refs they do not modify.

**Step 5 — HTTP Request node binary response**

Detect binary `Content-Type`, attach `BinaryRef`. Offload handles persistence.

**Step 6 — Webhook binary upload**

Parse multipart/raw binary body, attach `BinaryRef`. Same offload path.

**Step 7 — `docrouter.create_document` node**

Implement the promotion node: `flow_blobs` → `files` + `docs` entry. Enables end-to-end: webhook receives PDF → create document → OCR → LLM.

**Step 8 — Binary serve endpoint**

Add `GET /v0/orgs/{orgId}/executions/{executionId}/binary-data`. Unlocks the frontend.

**Step 9 — Frontend binary display**

Extend the output panel, add `getFlowBinaryUrl()`, add SDK types.
