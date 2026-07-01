import type { DocRouterOrgApi } from '@/utils/api';

export const FLOW_RERUN_POLL_MS = 600;
export const FLOW_RERUN_MAX_WAIT_MS = 180_000;

export function getStatusFromError(err: unknown): number | undefined {
  if (err && typeof err === 'object' && 'status' in err && typeof (err as { status: unknown }).status === 'number') {
    return (err as { status: number }).status;
  }
  return undefined;
}

function sleepMs(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Poll lightweight flow result until execution_id matches the enqueued run. */
export async function pollFlowRerunUntilDone(
  api: DocRouterOrgApi,
  params: {
    flowId: string;
    documentId: string;
    execId: string;
    shouldContinue?: () => boolean;
  },
): Promise<void> {
  const deadline = Date.now() + FLOW_RERUN_MAX_WAIT_MS;
  const alive = params.shouldContinue ?? (() => true);

  while (Date.now() < deadline) {
    if (!alive()) return;

    try {
      const result = await api.getFlowDocumentResult({
        documentId: params.documentId,
        flowId: params.flowId,
      });
      if (!alive()) return;
      if (result.execution_id === params.execId) return;
    } catch (e) {
      const status = getStatusFromError(e);
      if (status !== 404) {
        console.warn('Flow rerun poll: result fetch failed', e);
      }
    }

    await sleepMs(FLOW_RERUN_POLL_MS);
  }

  throw new Error('Flow rerun timed out');
}
