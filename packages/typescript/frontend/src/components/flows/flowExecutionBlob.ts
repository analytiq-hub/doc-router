import { apiClient } from '../../utils/api';

export type FlowExecutionBlobContext = {
  organizationId: string;
  flowId: string;
  executionId: string;
};

/** Revision-scoped pin blobs (`flow_pins:` / org `files:`) without an execution trace. */
export type FlowRevisionPinBlobContext = {
  organizationId: string;
  flowId: string;
  flowRevid: string;
};

const EXECUTION_FETCHABLE_STORAGE_PREFIXES = ['flow_blobs:', 'flow_pins:', 'files:'] as const;
const REVISION_PIN_FETCHABLE_STORAGE_PREFIXES = ['flow_pins:', 'files:'] as const;

function storageIdHasPrefix(storageId: string, prefixes: readonly string[]): boolean {
  return prefixes.some((prefix) => storageId.startsWith(prefix));
}

function blobFromArrayBufferResponse(res: {
  data: ArrayBuffer;
  headers: Record<string, unknown>;
}): { blob: Blob; downloadName: string | null } {
  const cd = res.headers['content-disposition'];
  let downloadName: string | null = null;
  if (typeof cd === 'string') {
    const m = cd.match(/filename\*=UTF-8''([^;\s]+)|filename="([^"]+)"/i);
    const raw = m?.[1] ?? m?.[2];
    if (raw) {
      try {
        downloadName = decodeURIComponent(raw.replace(/^"|"$/g, ''));
      } catch {
        downloadName = raw.replace(/^"|"$/g, '');
      }
    }
  }
  const mimeHdr = res.headers['content-type'];
  const mime =
    typeof mimeHdr === 'string' && mimeHdr.trim() ? mimeHdr.split(';')[0].trim() : 'application/octet-stream';
  return { blob: new Blob([res.data], { type: mime }), downloadName };
}

/** True when the execution blob endpoint can resolve this ``storage_id``. */
export function isFetchableExecutionBlobStorageId(storageId: string | undefined | null): boolean {
  if (!storageId || !storageId.trim()) return false;
  return storageIdHasPrefix(storageId, EXECUTION_FETCHABLE_STORAGE_PREFIXES);
}

/** True when the revision pin blob endpoint can resolve this ``storage_id``. */
export function isFetchableRevisionPinBlobStorageId(storageId: string | undefined | null): boolean {
  if (!storageId || !storageId.trim()) return false;
  return storageIdHasPrefix(storageId, REVISION_PIN_FETCHABLE_STORAGE_PREFIXES);
}

/** True when either execution or revision pin context can fetch this ``storage_id``. */
export function canFetchFlowBinaryRef(
  storageId: string | undefined | null,
  executionCtx: FlowExecutionBlobContext | null | undefined,
  pinCtx: FlowRevisionPinBlobContext | null | undefined,
): boolean {
  if (!storageId || !storageId.trim()) return false;
  if (executionCtx && isFetchableExecutionBlobStorageId(storageId)) return true;
  if (pinCtx && isFetchableRevisionPinBlobStorageId(storageId)) return true;
  return false;
}

/** Fetches binary payload for an execution trace (`storage_id`: `flow_blobs:…`, `flow_pins:…`, or `files:…`). */
export async function fetchFlowExecutionBlob(
  ctx: FlowExecutionBlobContext,
  storageId: string,
  opts?: { action?: 'view' | 'download' },
): Promise<{ blob: Blob; downloadName: string | null }> {
  const action = opts?.action ?? 'download';
  const res = await apiClient.get<ArrayBuffer>(
    `/v0/orgs/${encodeURIComponent(ctx.organizationId)}/flows/${encodeURIComponent(ctx.flowId)}/executions/${encodeURIComponent(ctx.executionId)}/blob`,
    { params: { storage_id: storageId, action }, responseType: 'arraybuffer' },
  );
  return blobFromArrayBufferResponse(res);
}

/** Fetches revision-scoped pin blobs (`flow_pins:` or org `files:`). */
export async function fetchFlowRevisionPinBlob(
  ctx: FlowRevisionPinBlobContext,
  storageId: string,
  opts?: { action?: 'view' | 'download' },
): Promise<{ blob: Blob; downloadName: string | null }> {
  const action = opts?.action ?? 'download';
  const res = await apiClient.get<ArrayBuffer>(
    `/v0/orgs/${encodeURIComponent(ctx.organizationId)}/flows/${encodeURIComponent(ctx.flowId)}/revisions/${encodeURIComponent(ctx.flowRevid)}/pins/blob`,
    { params: { storage_id: storageId, action }, responseType: 'arraybuffer' },
  );
  return blobFromArrayBufferResponse(res);
}

/** Resolve a binary ref via execution trace when available, else revision pin scope. */
export async function fetchFlowBinaryRef(
  storageId: string,
  executionCtx: FlowExecutionBlobContext | null | undefined,
  pinCtx: FlowRevisionPinBlobContext | null | undefined,
  opts?: { action?: 'view' | 'download' },
): Promise<{ blob: Blob; downloadName: string | null }> {
  if (executionCtx && isFetchableExecutionBlobStorageId(storageId)) {
    return fetchFlowExecutionBlob(executionCtx, storageId, opts);
  }
  if (pinCtx && isFetchableRevisionPinBlobStorageId(storageId)) {
    return fetchFlowRevisionPinBlob(pinCtx, storageId, opts);
  }
  throw new Error('Cannot download this binary attachment.');
}
