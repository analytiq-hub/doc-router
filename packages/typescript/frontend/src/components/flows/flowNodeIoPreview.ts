import type { Edge } from 'reactflow';
import { parseHandleIndex } from './flowRf';

type RunData = Record<string, unknown> | null | undefined;

/**
 * Upstream per-slot preview for a node from a completed execution’s `run_data`
 * and the current graph edges. Best-effort: uses first item on the first output lane.
 */
export function buildNodeInputPreview(
  nodeId: string,
  edges: Edge[],
  runData: RunData,
): { slots: { slot: number; fromNodeId: string; payload: unknown }[]; message: string | null } {
  if (!runData) {
    return { slots: [], message: 'Run the workflow to see input data for this node.' };
  }
  const incoming = edges.filter((e) => e.target === nodeId);
  if (incoming.length === 0) {
    // Trigger/source nodes have no wires in. For them, show their own emitted data as "input" when available.
    const selfRec = runData[nodeId] as { data?: { main?: Array<Array<{ json?: unknown } | null> | null> } } | null;
    const selfMain0 = selfRec?.data?.main?.[0];
    const selfFirst = Array.isArray(selfMain0) && selfMain0.length > 0 ? selfMain0[0] : null;
    const selfPayload =
      selfFirst && typeof selfFirst === 'object' && 'json' in (selfFirst as object) ? (selfFirst as { json: unknown }).json : selfFirst;
    if (selfPayload != null) {
      return { slots: [{ slot: 0, fromNodeId: nodeId, payload: selfPayload }], message: null };
    }
    return { slots: [], message: 'This node has no input connections (trigger / source nodes have no wire in).' };
  }
  const slots: { slot: number; fromNodeId: string; payload: unknown }[] = [];
  for (const e of incoming) {
    const slot = parseHandleIndex(e.targetHandle, 'in-') ?? 0;
    const fromNodeId = e.source;
    const rec = runData[fromNodeId] as {
      data?: { main?: Array<Array<{ json?: unknown } | null> | null> };
    } | null;
    const main0 = rec?.data?.main?.[0];
    const first = Array.isArray(main0) && main0.length > 0 ? main0[0] : null;
    const payload = first && typeof first === 'object' && 'json' in (first as object) ? (first as { json: unknown }).json : first;
    slots.push({ slot, fromNodeId, payload: payload ?? null });
  }
  slots.sort((a, b) => a.slot - b.slot);
  return { slots, message: null };
}

export function buildNodeOutputPreview(
  nodeId: string,
  runData: RunData,
): { data: unknown; message: string | null } {
  if (!runData) {
    return { data: null, message: 'Run the workflow to see output data for this node.' };
  }
  type NodeRun = {
    data?: { main?: unknown[] };
    status?: string;
    error?: unknown;
  };
  const rec = runData[nodeId] as NodeRun | undefined;
  if (rec == null) {
    return { data: null, message: 'This node has not been executed in the latest run, or the run is still in progress.' };
  }
  return { data: rec, message: rec.status && rec.status !== 'success' ? `Status: ${rec.status}` : null };
}
