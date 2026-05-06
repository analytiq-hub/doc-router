# n8n Binary Blob Implementation

This document describes in detail how n8n handles binary data — the data model, storage backends, execution flow, node helpers, REST API, and frontend display. It is a reference for porting binary support to DocRouter.

---

## 1. Data model

### `IBinaryData`

Defined in `packages/workflow/src/Interfaces.ts`:

```typescript
export interface IBinaryData {
  [key: string]: string | number | undefined;
  data: string;            // Base64-encoded content (in-memory mode) or the mode name (external)
  mimeType: string;        // e.g. "application/pdf", "image/png"
  fileType?: BinaryFileType; // Categorised: 'text'|'json'|'image'|'audio'|'video'|'pdf'|'html'
  fileName?: string;       // Original file name
  directory?: string;      // Optional directory hint
  fileExtension?: string;  // Extension without dot, e.g. "pdf"
  fileSize?: string;       // Human-readable, e.g. "245 KB" (note: string, not number)
  id?: string;             // External storage reference: "<mode>:<fileId>"
}
```

The `id` field is absent when data is held in memory as base64. When external storage is used, `id` is set and `data` holds just the mode name (e.g. `"filesystem-v2"`) as a sentinel.

`BinaryFileType` is inferred at storage time via the `fileTypeFromMimeType()` utility.

### `IBinaryKeyData` and `INodeExecutionData`

A single execution item can carry multiple named binary properties:

```typescript
export interface IBinaryKeyData {
  [propertyName: string]: IBinaryData;
}

export interface INodeExecutionData {
  json: IDataObject;        // Structured JSON output
  binary?: IBinaryKeyData;  // Optional binary outputs, keyed by property name
  pairedItem?: ...;
  index?: number;
}
```

A node that downloads two attachments might produce:
```typescript
{
  json: { subject: "Invoice" },
  binary: {
    attachment_0: { mimeType: "application/pdf", fileName: "invoice.pdf", id: "filesystem-v2:..." },
    attachment_1: { mimeType: "image/png", fileName: "logo.png", data: "iVBORw0KGgo..." },
  }
}
```

---

## 2. Storage backends

**File:** `packages/core/src/BinaryData/BinaryData.service.ts`

`BinaryDataService` is a DI-injected singleton that routes all reads and writes through the active storage manager. Three modes are supported:

| Mode | Description |
|---|---|
| `default` | In-memory. Binary content is base64-encoded into `IBinaryData.data`. No files on disk. |
| `filesystem-v2` | Local disk. Files written to `{storagePath}/workflows/{wfId}/executions/{execId}/binary_data/{fileId}`. A `.metadata` JSON sidecar stores `fileName` and `mimeType`. |
| `s3` | AWS S3 or S3-compatible. File stored as an S3 object; metadata in `x-amz-meta-*` headers. |

`filesystem` (without `-v2`) is a legacy mode that is automatically upgraded on startup.

### Manager interface

All three backends implement:

```typescript
interface Manager {
  store(workflowId, executionId, bufferOrStream, metadata): Promise<WriteResult>;
  getAsBuffer(fileId: string): Promise<Buffer>;
  getAsStream(fileId: string, chunkSize?: number): Promise<Readable>;
  getMetadata(fileId: string): Promise<Metadata>;
  copyByFileId(workflowId, executionId, sourceFileId): Promise<string>;
  copyByFilePath(workflowId, executionId, sourcePath, metadata): Promise<WriteResult>;
  rename(oldFileId, newFileId): Promise<void>;
  deleteMany?(ids): Promise<void>;   // filesystem only
}
```

### The `id` format

`IBinaryData.id` = `"<mode>:<fileId>"`

Example: `"filesystem-v2:workflows/123/executions/456/binary_data/abc-def"`

`BinaryDataService` splits on `:` to find the correct manager:

```typescript
async getAsStream(binaryDataId: string, chunkSize?: number) {
  const [mode, fileId] = binaryDataId.split(':');
  return await this.getManager(mode).getAsStream(fileId, chunkSize);
}
```

---

## 3. Writing binary data

### `prepareBinaryData()`

**File:** `packages/core/src/NodeExecuteFunctions.ts`

The primary helper nodes use to create an `IBinaryData` object from a raw buffer or stream:

```typescript
async function prepareBinaryData(
  binaryData: Buffer | Readable,
  executionId: string,
  workflowId: string,
  filePath?: string,   // hints for fileName and extension
  mimeType?: string,
): Promise<IBinaryData>
```

Steps:
1. Determines `mimeType` from the argument, `Content-Type` header, or `fileType` library detection.
2. Extracts `fileName` from `Content-Disposition`, the URL path, or `filePath`.
3. Derives `fileExtension` and `fileType` category.
4. Calls `setBinaryDataBuffer()` to hand off to the storage backend.

### `setBinaryDataBuffer()`

```typescript
async function setBinaryDataBuffer(
  binaryData: IBinaryData,
  bufferOrStream: Buffer | Readable,
  workflowId: string,
  executionId: string,
): Promise<IBinaryData> {
  return await Container.get(BinaryDataService).store(
    workflowId, executionId, bufferOrStream, binaryData,
  );
}
```

In `default` mode: encodes the buffer as base64 into `binaryData.data`.  
In external modes: writes the file, sets `binaryData.id`, clears `binaryData.data` to the mode name.

---

## 4. Reading binary data

The pattern used everywhere a node reads binary:

```typescript
const binaryData = this.helpers.assertBinaryData(itemIndex, propertyName);

let fileContent: Buffer | Readable;
if (binaryData.id) {
  fileContent = await this.helpers.getBinaryStream(binaryData.id);
} else {
  fileContent = Buffer.from(binaryData.data, 'base64');
}
```

`assertBinaryData()` throws a descriptive error if the property is missing.  
`getBinaryStream()` delegates to `BinaryDataService.getAsStream()`.

---

## 5. Flow through execution

### Run data structure

```
IRunData {
  [nodeName: string]: ITaskData[]     // one per execution attempt
}
ITaskData {
  data: ITaskDataConnections
}
ITaskDataConnections {
  main: Array<INodeExecutionData[] | null>   // per output slot
}
```

Binary data lives inside `INodeExecutionData` objects. In external storage mode, only the `id` string travels through the data structure — the file bytes stay on disk or in S3.

### Serialization

Execution data is persisted via the `flatted` library (handles circular references):

```typescript
import { stringify, parse } from 'flatted';
const serialized = stringify(runData);  // Stores ids, not raw bytes
```

### Duplication on retry

`BinaryDataService.duplicateBinaryData()` copies binary files when an execution is retried, rewiring all `id` references to point at the new `executionId`.

### Webhook edge case: temp IDs

When a webhook fires before an `executionId` is assigned, binaries are stored under a `temp` placeholder:

```
filesystem-v2:workflows/123/executions/temp/binary_data/abc-def
```

The `restore-binary-data-id` lifecycle hook renames the files once the execution ID is known:

```typescript
// packages/cli/src/execution-lifecycle-hooks/restore-binary-data-id.ts
const correctFileId = fileId.replace('temp', executionId);
await binaryDataService.rename(fileId, correctFileId);
// Also patches the id string inside run_data in place
```

---

## 6. HTTP Request node — binary response

**File:** `packages/nodes-base/nodes/HttpRequest/V3/HttpRequestV3.node.ts`

The node detects a binary response by checking `Content-Type`:

```typescript
const binaryContentTypes = [
  'application/pdf', 'image/', 'audio/', 'video/',
  'application/gzip', 'application/zip', ...
];

if (binaryContentTypes.some(ct => responseContentType.includes(ct))) {
  const binaryData = await this.helpers.prepareBinaryData(
    responseBody,         // Buffer | Readable
    undefined,
    responseContentType,
  );
  newItem.binary![outputPropertyName] = binaryData;
}
```

The property name `outputPropertyName` defaults to `"data"` and is configurable.

---

## 7. Webhook node — binary uploads

**File:** `packages/nodes-base/nodes/Webhook/Webhook.node.ts`

**Multipart form data** (file uploads):
```typescript
if (req.contentType === 'multipart/form-data') {
  for (const file of uploadedFiles) {
    returnItem.binary![propertyName] = await context.nodeHelpers.copyBinaryFile(
      file.filepath,           // temp path written by Express file-upload middleware
      file.originalFilename,
      file.mimetype,
    );
  }
}
```

**Raw binary body** (e.g. `Content-Type: application/octet-stream`):
```typescript
const tmpFile = await tmp.file({ prefix: 'n8n-webhook-' });
await pipeline(req, createWriteStream(tmpFile.path));
returnItem.binary = {
  [propertyName]: await context.nodeHelpers.copyBinaryFile(tmpFile.path, fileName, contentType),
};
await tmpFile.cleanup();
```

In both cases the file is first written to `/tmp`, then handed to `copyBinaryFile()` which moves it into binary storage and returns a populated `IBinaryData`.

---

## 8. Specialized binary nodes

### ReadBinaryFile / WriteBinaryFile

```typescript
// Read: stream from disk into binary storage
const stream = await this.helpers.createReadStream(filePath);
newItem.binary![propertyName] = await this.helpers.prepareBinaryData(stream, filePath);

// Write: stream from binary storage to disk
const binaryData = this.helpers.assertBinaryData(i, propertyName);
const content = binaryData.id
  ? await this.helpers.getBinaryStream(binaryData.id)
  : Buffer.from(binaryData.data, 'base64');
await this.helpers.writeContentToFile(fileName, content, flag);
```

### MoveBinaryData

Copies binary properties between keys on the same item, or promotes a binary value into the `json` field (e.g. for text files). Does not re-write the file — just moves the `IBinaryData` reference.

---

## 9. REST API — serving binary data to the browser

**File:** `packages/cli/src/controllers/binary-data.controller.ts`

Single endpoint:
```
GET /binary-data?id=<binaryDataId>&action=view|download&fileName=…&mimeType=…
```

Logic:
1. Splits `id` to find the storage mode.
2. Fetches metadata (file name, mime type) if not in query params.
3. Sets `Content-Type` and optionally `Content-Disposition: attachment` for downloads.
4. Streams the file via `BinaryDataService.getAsStream(id)`.

The streaming response means large files (GB+) are never fully loaded into the Node.js process.

---

## 10. Frontend display

**Files:** `packages/editor-ui/src/components/BinaryDataDisplay.vue`, `BinaryDataDisplayEmbed.vue`

The display component:

1. If no `id` (in-memory): creates a `data:` URI from the base64 `data` field.
2. If `id` (external): fetches via `/binary-data?id=...&action=view`.

Rendering by `fileType`:

| fileType | Display |
|---|---|
| `image` | `<img :src="url">` |
| `video` | `<video><source :src="url" :type="mimeType"></video>` |
| `audio` | `<audio><source>` |
| `pdf` | PDF embed viewer |
| `json` | JSON tree component |
| `html` | Safe HTML renderer |
| other | Generic `<embed>` or download link |

URL construction (`workflows.store.ts`):
```typescript
function getBinaryUrl(binaryDataId, action, fileName, mimeType): string {
  const url = new URL(`${restUrl}/binary-data`);
  url.searchParams.append('id', binaryDataId);
  url.searchParams.append('action', action);   // 'view' or 'download'
  if (fileName) url.searchParams.append('fileName', fileName);
  if (mimeType) url.searchParams.append('mimeType', mimeType);
  return url.toString();
}
```

---

## 11. Key files summary

| File | Purpose |
|---|---|
| `packages/workflow/src/Interfaces.ts` | `IBinaryData`, `IBinaryKeyData`, `INodeExecutionData` interfaces |
| `packages/core/src/BinaryData/BinaryData.service.ts` | Central orchestrator; routes reads/writes to the active manager |
| `packages/core/src/BinaryData/types.ts` | `Manager` interface, `BinaryData.Config`, `Metadata` type |
| `packages/core/src/BinaryData/FileSystem.manager.ts` | Disk storage implementation |
| `packages/core/src/BinaryData/ObjectStore.manager.ts` | S3 storage implementation |
| `packages/core/src/NodeExecuteFunctions.ts` | `prepareBinaryData`, `setBinaryDataBuffer`, `getBinaryStream`, `assertBinaryData` |
| `packages/nodes-base/nodes/HttpRequest/V3/HttpRequestV3.node.ts` | Binary response detection and packaging |
| `packages/nodes-base/nodes/Webhook/Webhook.node.ts` | Binary upload ingestion (multipart + raw body) |
| `packages/nodes-base/nodes/ReadBinaryFile/ReadBinaryFile.node.ts` | Read file from disk into binary storage |
| `packages/nodes-base/nodes/WriteBinaryFile/WriteBinaryFile.node.ts` | Write binary storage content to disk |
| `packages/nodes-base/nodes/MoveBinaryData/MoveBinaryData.node.ts` | Rearrange binary properties on items |
| `packages/cli/src/controllers/binary-data.controller.ts` | `GET /binary-data` streaming endpoint |
| `packages/cli/src/execution-lifecycle-hooks/restore-binary-data-id.ts` | Fixes temp IDs after webhook executions |
| `packages/cli/src/databases/repositories/execution.repository.ts` | Serialization via `flatted` |
| `packages/editor-ui/src/components/BinaryDataDisplay.vue` | Binary data viewer shell |
| `packages/editor-ui/src/components/BinaryDataDisplayEmbed.vue` | Type-specific embed rendering |
| `packages/editor-ui/src/stores/workflows.store.ts` | `getBinaryUrl()` helper |
| `packages/nodes-base/utils/binary.ts` | Conversion utilities (JSON→spreadsheet, PDF extraction) |
