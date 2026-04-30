import type { Edge } from 'reactflow';
import { parseHandleIndex } from './flowRf';

type RunData = Record<string, unknown> | null | undefined;

type NodeRun = {
  /** `main[slot][item]` — executed node output lanes. */
  data?: { main?: unknown };
  status?: string;
  error?: unknown;
};

/** All `.json` values from output lane `main[0]` for a node's run entry. */
export function laneMain0ItemsJson(runEntry: unknown): unknown[] {
  if (!runEntry || typeof runEntry !== 'object') return [];
  const main = (runEntry as NodeRun).data?.main;
  if (!Array.isArray(main) || main.length === 0) return [];
  const lane = main[0];
  if (!Array.isArray(lane)) return [];
  const out: unknown[] = [];
  for (const it of lane) {
    if (it != null && typeof it === 'object' && 'json' in (it as object)) {
      out.push((it as { json?: unknown }).json ?? null);
    } else if (it != null) {
      out.push(it);
    } else {
      out.push(null);
    }
  }
  return out;
}

/**
 * Upstream per-slot preview for a node from a completed execution’s `run_data`
 * and the current graph edges — full item list (`itemsJson`) from each wire’s upstream lane `main[0]`.
 */
export function buildNodeInputPreview(
  nodeId: string,
  edges: Edge[],
  runData: RunData,
): { slots: { slot: number; fromNodeId: string; itemsJson: unknown[] }[]; message: string | null } {
  if (!runData) {
    return { slots: [], message: 'Run the workflow to see input data for this node.' };
  }
  const incoming = edges.filter((e) => e.target === nodeId);
  if (incoming.length === 0) {
    const selfRec = runData[nodeId] as unknown;
    const selfItems = laneMain0ItemsJson(selfRec);
    if (selfItems.length > 0) {
      return { slots: [{ slot: 0, fromNodeId: nodeId, itemsJson: selfItems }], message: null };
    }
    return { slots: [], message: 'This node has no input connections (trigger / source nodes have no wire in).' };
  }
  const slots: { slot: number; fromNodeId: string; itemsJson: unknown[] }[] = [];
  for (const e of incoming) {
    const slot = parseHandleIndex(e.targetHandle, 'in-') ?? 0;
    const fromNodeId = e.source;
    const rec = runData[fromNodeId] as unknown;
    slots.push({
      slot,
      fromNodeId,
      itemsJson: laneMain0ItemsJson(rec),
    });
  }
  slots.sort((a, b) => a.slot - b.slot);
  return { slots, message: null };
}

/** Output lane `main[0]` JSON items plus optional status/message for badges. */
export function buildNodeOutputPreview(
  nodeId: string,
  runData: RunData,
): { itemsJson: unknown[]; message: string | null } {
  if (!runData) {
    return { itemsJson: [], message: 'Run the workflow to see output data for this node.' };
  }
  const rec = runData[nodeId] as NodeRun | undefined;
  if (rec == null) {
    return { itemsJson: [], message: 'This node has not been executed in the latest run, or the run is still in progress.' };
  }
  const itemsJson = laneMain0ItemsJson(rec);
  const msg = rec.status && rec.status !== 'success' ? `Status: ${rec.status}` : null;
  return { itemsJson, message: msg };
}
