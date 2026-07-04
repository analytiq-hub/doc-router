import type { FlowExecution } from '@docrouter/sdk';

import {
  batchEntryIsIncomplete,
  batchItemsCompletedFromEntry,
  flowRunDataEntries,
} from './flowRunDataEntry';

const RESUMABLE_STATUSES = new Set(['stopped', 'error', 'interrupted']);

export function executionHasResumableBatch(runData: Record<string, unknown> | null | undefined): boolean {
  return flowRunDataEntries(runData).some((entry) => {
    const status = entry.status;
    if (status !== 'partial' && status !== 'error' && status !== 'running') return false;
    return batchEntryIsIncomplete(entry);
  });
}

export function batchItemsRemainingFromExecution(execution: FlowExecution): number | null {
  const runData = execution.run_data as Record<string, unknown> | undefined;
  let best: number | null = null;
  for (const entry of flowRunDataEntries(runData)) {
    const total = entry.items_total;
    if (typeof total !== 'number' || total <= 0) continue;
    const done = batchItemsCompletedFromEntry(entry);
    if (done == null || done >= total) continue;
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
