import { apiClient } from '../../utils/api';

export type FlowExecutionBlobContext = {
  organizationId: string;
  flowId: string;
  executionId: string;
};

/** Fetches execution-scoped GridFS payload (`storage_id` must be `flow_blobs:...`); uses API session cookie / bearer. */
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
