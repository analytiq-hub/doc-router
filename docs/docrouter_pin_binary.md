# DocRouter Pinning Binary Output — Plan

This document specifies how DocRouter should support **pinning and editing binary output** for flow nodes (authoring/test-time overrides), similar to n8n’s “Edit output” UX, but extended to include DocRouter’s `BinaryRef` attachments.

Scope: **editor pin_data only** (stored on `flow_revisions.pin_data`), not execution-time binary outputs (which already exist via `FlowItem.binary` + GridFS `flow_blobs`).

---

## 1. Goals and non-goals

### Goals
- Allow users to **pin node outputs** that include both:
  - JSON items (`item.json`)
  - Binary attachments (`item.binary`)
- Allow users to **edit** pinned output with a modal that has:
  - **Json** tab (Monaco editor, same as today)
  - **Binary** tab where users can upload/manage files per item
- Support:
  - **Multiple items**
  - **Multiple files per item**
  - **Multiple binary properties per item** (e.g. `pdf`, `image`, `data`, `original`, etc.)
- When JSON item count and binary-item count differ, accept it:
  - Use \(N = \max(N_\text{json}, N_\text{binary})\)
  - Missing JSON items become empty JSON objects
  - Missing binary items become empty binary dicts

### Non-goals (for v1)
- Real-time streaming of upload progress/logs (no WebSocket/SSE in DocRouter flows UI today).
- Binary editing/transforming (no in-browser binary editor); only upload/remove/rename property.
- Sharing pinned binary blobs across revisions (keep lifecycle scoped to a single revision).

---

## 2. Definitions and current pinning model

### 2.1 Current pinning shape
`flow_revisions.pin_data` is keyed by **node id** and stores a `main` lane with output-slot arrays:

```json
{
  "<node_id>": {
    "main": [
      [
        { "json": { "...": "..." } }
      ]
    ]
  }
}
```

Notes:
- The UI currently edits **only the JSON items array** (not the `{ main: ... }` wrapper).
- The engine treats pinned outputs as executed node outputs and merges them into `run_data` before running downstream nodes.

### 2.2 Proposed pinned item shape (add `binary`)
Extend pinned items to allow:

```json
{ "json": { ... }, "binary": { "<name>": { ...FlowBinaryRef... } } }
```

Where each binary property is a **by-reference** descriptor:

```ts
type FlowBinaryRef = {
  mime_type: string;
  file_name?: string | null;
  storage_id: string;   // required for persisted pins
  file_size?: number | null;
}
```

No inline bytes are persisted in MongoDB for pins.

---

## 3. Storage and lifecycle of pinned binaries

### 3.1 New GridFS bucket: `flow_pins`
Add a dedicated GridFS bucket:
- **Bucket**: `flow_pins`
- **Purpose**: binaries referenced from `flow_revisions.pin_data`
- **Lifecycle**: retained as long as the revision exists and references them; garbage-collected when pins are removed or revision deleted.

Rationale:
- Avoid mixing pin blobs with execution blobs (`flow_blobs`) which are transient and deleted by execution retention.
- Avoid mixing with permanent customer documents (`files`).

### 3.2 `storage_id` format
Pinned binaries use:

```
flow_pins:<key>
```

Recommended key structure:

```
pin/<flow_revid>/<node_id>/<slot>/<item_index>/<property>/<safe_filename>
```

Example:

```
flow_pins:pin/65d.../node-3/0/2/pdf/invoice.pdf
```

### 3.3 Unpin and cleanup semantics

#### Unpin a node
When a node’s pin is removed (`pin_data[node_id]` deleted):
- Delete all `flow_pins` blobs under prefix:
  - `pin/<flow_revid>/<node_id>/`

#### Edit pins (replace)
When saving a revision with updated `pin_data[node_id]`:
- Compute the set of **referenced** `flow_pins:*` keys in the new pin payload.
- Delete any previously referenced `flow_pins` keys for that node that are no longer referenced.

#### Delete revision
When deleting a revision document:
- Delete all `flow_pins` blobs under prefix:
  - `pin/<flow_revid>/`

#### Safety
- Only delete `flow_pins` keys with the expected prefix.
- Never delete from `files` or `flow_blobs` as part of pin cleanup.

---

## 4. Backend design

### 4.1 Data model / validation

#### SDK types
Update `packages/typescript/sdk/src/types/flows.ts`:
- `FlowPinItem` becomes:
  - `{ json: unknown; binary?: Record<string, FlowBinaryRef> }`
- `FlowPinNodeOutput.main` continues to be `Array<FlowPinItem[] | null>`

#### Python coercion
Update flow pin coercion (where pin_data becomes `FlowItem` / `BinaryRef`) to:
- accept `binary` dict per item
- coerce each ref:
  - require `mime_type`
  - require `storage_id` for persisted pins
  - optional `file_name`, `file_size`

### 4.2 API endpoints

#### 4.2.1 Upload pinned binary
Add an authenticated upload route:

```
POST /v0/orgs/{orgId}/flows/{flowId}/revisions/{flowRevid}/pins/binary
Content-Type: multipart/form-data
```

Form fields:
- `node_id` (string, required)
- `slot` (int, default 0)
- `item_index` (int, required)
- `property` (string, required) — binary property name, e.g. `pdf`
- `file` (file, required)

Server behavior:
- Verify org access and that `{flowId, flowRevid}` are valid and belong to org.
- Save bytes to GridFS bucket `flow_pins` under the key format in §3.2.
- Return a JSON `FlowBinaryRef`:

```json
{
  "mime_type": "application/pdf",
  "file_name": "invoice.pdf",
  "storage_id": "flow_pins:pin/<flowRevid>/<nodeId>/0/2/pdf/invoice.pdf",
  "file_size": 12345
}
```

Notes:
- The client then embeds that object in `pin_data` when saving edits.
- This decouples blob upload from revision save (prevents huge JSON payloads / base64).

#### 4.2.2 Download/preview pinned binary
Add an authenticated route:

```
GET /v0/orgs/{orgId}/flows/{flowId}/revisions/{flowRevid}/pins/blob
    ?storage_id=flow_pins:...
    &action=view|download
```

Server behavior:
- Verify org access and flow/revision ownership.
- Validate:
  - bucket must be `flow_pins`
  - key must start with `pin/<flowRevid>/`
- Stream bytes back with `Content-Type` from stored metadata and optional `Content-Disposition`.

#### 4.2.3 Revision save / pin cleanup
In the existing “save revision” route:
- Compare previous revision’s `pin_data` vs new payload’s `pin_data`
- Perform cleanup per §3.3 (delete unreferenced blobs)

### 4.3 Storage metadata
When saving to GridFS, store metadata:
- `mime_type`
- `file_name`
- `organization_id`
- `flow_id`
- `flow_revid`
- `node_id`
- `slot`
- `item_index`
- `property`

This enables debugging and safe enforcement.

---

## 5. Frontend UX — Edit Output modal with Json + Binary

### 5.1 Modal structure
When clicking **Edit** on a node’s output:
- Show a tabbed modal:
  - **Json** tab: existing Monaco editor showing a JSON array of items (as today)
  - **Binary** tab: file manager UI for per-item attachments

Save applies to both tabs at once.

### 5.2 Json tab behavior
- Editor value is a JSON array: `unknown[]`
- Parse errors block save.
- On save, the array becomes the pinned `json` for each item.

### 5.3 Binary tab behavior

#### Data model in the UI
Represent pinned binaries as an array aligned by item index:

```ts
type UiPinnedBinaryItem = {
  // property name -> list of files for that property
  // (list enables multiple files per item and per property)
  [property: string]: FlowBinaryRef[];
};
type UiPinnedBinary = UiPinnedBinaryItem[];
```

Mapping to engine pin shape:
- Engine pin item `binary` remains a dict `property -> FlowBinaryRef`.
- To support **multiple files per property**, define the convention:
  - UI expands `property` to multiple *distinct* property keys at save-time, e.g.:
    - `file` → `file`, `file_2`, `file_3`
  - or allow nested lists in pinned schema (requires engine change).

**Recommendation (v1)**: allow multiple files by generating unique property keys:
- `pdf` (first)
- `pdf_2`, `pdf_3`, ...

This avoids changing the runtime `FlowItem.binary` type (`Record<string, BinaryRef>`).

#### UI interactions
For each item index \(i\):
- Show an “Item i” section
- Allow:
  - Add file
    - choose **property name** (text input, default `data`)
    - choose file (upload)
  - Remove file
  - Rename property key (optional v1)
  - View/download (uses pins blob endpoint)

#### Upload flow
When a file is added:
- Immediately `POST .../pins/binary` to get a `FlowBinaryRef` (storage_id etc.)
- Insert it into the UI state for that item/property

This ensures that when the user hits Save, pin_data is already by-reference.

### 5.4 Handling mismatch counts (json vs binary)
On Save:
- Let `jsonItems` be the parsed Json tab array (length `J`)
- Let `binItems` be the Binary tab array (length `B`)
- Compute `N = max(J, B)`
- For each `i in [0..N-1]`:
  - `json = jsonItems[i] ?? {}`
  - `binary = binItems[i] ?? {}`
- Build pin output lane:

```json
{ "main": [ [ { "json": ..., "binary": ... }, ... ] ] }
```

---

## 6. Engine behavior with pinned binaries

Pinned output substitution must:
- Skip node execution when pin exists (same as today)
- Provide downstream nodes with `FlowItem.binary` populated from pin_data
- Respect pass-by-reference:
  - pinned binaries are **already stored** (`flow_pins:`)
  - engine must not attempt to offload them to `flow_blobs`

Implementation detail:
- ensure the offload step only uploads when `BinaryRef.data` is set and `storage_id` is missing (already true today)

---

## 7. Rollout plan (implementation order)

1. **Backend foundation**
   - Add `flow_pins` bucket support in blob utils (same helpers can already target arbitrary bucket)
   - Add pins upload + pins blob endpoints
   - Extend pin_data coercion to accept `binary`
   - Add pin cleanup on revision save/delete

2. **SDK types**
   - Add `FlowBinaryRef`
   - Extend `FlowPinItem` to optionally include `binary`

3. **Frontend modal**
   - Add tabs (Json/Binary)
   - Implement per-item file upload UI + preview/download
   - Implement mismatch count rule in Save builder

4. **Tests**
   - Backend: pins upload route, pins blob route, cleanup behavior
   - Frontend: basic state mapping and save payload shape

