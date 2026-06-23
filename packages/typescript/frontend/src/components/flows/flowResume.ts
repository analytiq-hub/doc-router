import type { FlowExecution } from '@docrouter/sdk';

const RESUMABLE_STATUSES = new Set(['stopped', 'error', 'interrupted']);

export function canResumeExecution(execution: FlowExecution): boolean {
  if (execution.resumed_by) return false;
  const nodes = execution.completed_nodes;
  if (!nodes?.length) return false;
  return RESUMABLE_STATUSES.has(execution.status);
}
