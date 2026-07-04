import type { FlowExecution } from '@docrouter/sdk';

const RESUMABLE_STATUSES = new Set(['stopped', 'error', 'interrupted']);

type RunDataEntry = {
  status?: string;
  items_total?: number;
  items_completed?: number;
  data?: { main?: unknown[][] };
};

function runDataEntries(runData: Record<string, unknown> | null | undefined): RunDataEntry[] {
  if (!runData) return [];
  return Object.values(runData).filter(
    (v): v is RunDataEntry => v != null && typeof v === 'object',
  );
}

export function executionHasResumableBatch(runData: Record<string, unknown> | null | undefined): boolean {
  return runDataEntries(runData).some((entry) => {
    const status = entry.status;
    if (status !== 'partial' && status !== 'error' && status !== 'running') return false;
    const total = entry.items_total;
    const completed = entry.items_completed;
    if (typeof total === 'number' && typeof completed === 'number') {
      return total > 0 && completed < total;
    }
    const lane = entry.data?.main?.[0];
    return Array.isArray(lane) && lane.length > 0 && typeof total === 'number' && lane.length < total;
  });
}

export function batchItemsRemainingFromExecution(execution: FlowExecution): number | null {
  const runData = execution.run_data as Record<string, unknown> | undefined;
  let best: number | null = null;
  for (const entry of runDataEntries(runData)) {
    const total = entry.items_total;
    const completed = entry.items_completed;
    if (typeof total !== 'number' || total <= 0) continue;
    const done = typeof completed === 'number' ? completed : entry.data?.main?.[0]?.length ?? 0;
    if (done >= total) continue;
    const remaining = total - done;
    if (best == null || remaining > best) best = remaining;
  }
  return best;
}

export function canResumeExecution(execution: FlowExecution): boolean {
  if (execution.resumed_by) return false;
  const nodes = execution.completed_nodes;
  if (!nodes?.length) return false;
  return RESUMABLE_STATUSES.has(execution.status);
}

export function resumeExecutionLabel(execution: FlowExecution): string {
  const remaining = batchItemsRemainingFromExecution(execution);
  if (remaining != null && remaining > 0) {
    return `Resume (${remaining} item${remaining === 1 ? '' : 's'} remaining)`;
  }
  return 'Resume from checkpoint';
}
