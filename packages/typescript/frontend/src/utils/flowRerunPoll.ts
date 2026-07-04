import type { DocRouterOrgApi } from '@/utils/api';
import type { FlowExecutionStatus } from '@docrouter/sdk';

export const FLOW_RERUN_POLL_MS = 600;
/** Safety cap for stuck runs; bulk flows with heavy OCR/LLM can run far longer than 3 minutes. */
export const FLOW_RERUN_MAX_WAIT_MS = 60 * 60 * 1000;

const TERMINAL_EXECUTION_STATUSES = new Set<FlowExecutionStatus>([
  'success',
  'error',
  'stopped',
  'interrupted',
]);

export function getStatusFromError(err: unknown): number | undefined {
  if (err && typeof err === 'object' && 'status' in err && typeof (err as { status: unknown }).status === 'number') {
    return (err as { status: number }).status;
  }
  return undefined;
}

function sleepMs(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function executionFailureMessage(status: FlowExecutionStatus): string {
  switch (status) {
    case 'error':
      return 'Flow execution failed';
    case 'stopped':
      return 'Flow execution stopped';
    case 'interrupted':
      return 'Flow execution interrupted';
    default:
      return `Flow execution ended with status ${status}`;
  }
}

/** Poll execution status until the run reaches a terminal state. */
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
      const execution = await api.getExecution(params.flowId, params.execId);
      if (!alive()) return;

      if (execution.status === 'success') return;
      if (TERMINAL_EXECUTION_STATUSES.has(execution.status)) {
        throw new Error(executionFailureMessage(execution.status));
      }
    } catch (e) {
      if (e instanceof Error && e.message.startsWith('Flow execution')) {
        throw e;
      }
      const status = getStatusFromError(e);
      if (status !== 404) {
        console.warn('Flow rerun poll: execution fetch failed', e);
      }
    }

    await sleepMs(FLOW_RERUN_POLL_MS);
  }

  throw new Error('Flow rerun timed out');
}
