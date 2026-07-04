/**
 * Shared helpers for `run_data[node_id]` entries from the flow engine.
 */

export type FlowRunDataEntry = {
  status?: string;
  items_total?: number;
  items_completed?: number;
  data?: { main?: unknown[][] };
};

export function flowRunDataEntry(
  runData: Record<string, unknown> | null | undefined,
  nodeId: string,
): FlowRunDataEntry | undefined {
  if (!runData) return undefined;
  const rec = runData[nodeId];
  return rec && typeof rec === 'object' ? (rec as FlowRunDataEntry) : undefined;
}

export function flowRunDataEntries(
  runData: Record<string, unknown> | null | undefined,
): FlowRunDataEntry[] {
  if (!runData) return [];
  return Object.values(runData).filter(
    (v): v is FlowRunDataEntry => v != null && typeof v === 'object',
  );
}

export function batchItemsCompletedFromEntry(entry: FlowRunDataEntry): number | null {
  if (typeof entry.items_completed === 'number') {
    return entry.items_completed;
  }
  const lane = entry.data?.main?.[0];
  if (Array.isArray(lane)) {
    return lane.length;
  }
  return null;
}

export function batchEntryIsIncomplete(entry: FlowRunDataEntry): boolean {
  const total = entry.items_total;
  if (typeof total !== 'number' || total <= 0) return false;
  const completed = batchItemsCompletedFromEntry(entry);
  if (completed == null) return false;
  return completed < total;
}
