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
 * Item count on the **source** node's output lane `main[0]` when that node exists in `run_data`.
 * `undefined` means there is no run snapshot for the source (hide the edge item badge).
 */
export function edgeItemCountFromRunData(runData: RunData, sourceNodeId: string): number | undefined {
  if (!runData || !sourceNodeId) return undefined;
  const rec = runData[sourceNodeId];
  if (rec == null || typeof rec !== 'object') return undefined;
  return laneMain0ItemsJson(rec).length;
}

/** All nodes that feed ``nodeId`` (direct sources and every transitive predecessor), excluding ``nodeId``. */
export function collectUpstreamClosure(nodeId: string, edges: Edge[]): Set<string> {
  const rev = new Map<string, string[]>();
  for (const e of edges) {
    if (typeof e.target !== 'string' || typeof e.source !== 'string') continue;
    const arr = rev.get(e.target) ?? [];
    arr.push(e.source);
    rev.set(e.target, arr);
  }

  const out = new Set<string>();
  const stack: string[] = [];
  for (const e of edges) {
    if (e.target === nodeId && typeof e.source === 'string') stack.push(e.source);
  }
  while (stack.length > 0) {
    const n = stack.pop()!;
    if (out.has(n)) continue;
    out.add(n);
    const ps = rev.get(n);
    if (ps) {
      for (const p of ps) stack.push(p);
    }
  }
  return out;
}

/**
 * Order nodes in ``closure`` by **graph distance toward** ``sinkId``:
 * immediate parents of ``sinkId`` first, then their parents, and so on (backward BFS).
 * Within each layer, ids are sorted lexically for stability.
 */
function orderUpstreamByDistanceSinkward(sinkId: string, edges: Edge[], closure: Set<string>): string[] {
  const rev = new Map<string, string[]>();
  for (const e of edges) {
    if (typeof e.target !== 'string' || typeof e.source !== 'string') continue;
    const arr = rev.get(e.target) ?? [];
    arr.push(e.source);
    rev.set(e.target, arr);
  }

  const ordered: string[] = [];
  const visited = new Set<string>();

  let frontier = [
    ...new Set(edges.filter((e) => e.target === sinkId && typeof e.source === 'string').map((e) => e.source as string)),
  ]
    .filter((id) => closure.has(id))
    .sort();

  while (frontier.length > 0) {
    for (const n of frontier) {
      if (visited.has(n)) continue;
      visited.add(n);
      ordered.push(n);
    }

    const next = new Set<string>();
    for (const n of frontier) {
      for (const p of rev.get(n) ?? []) {
        if (closure.has(p) && !visited.has(p)) next.add(p);
      }
    }
    frontier = [...next].sort();
  }

  for (const id of [...closure].sort()) {
    if (!visited.has(id)) ordered.push(id);
  }

  return ordered;
}

/** Strips any stale `itemCount` on edges, then sets it from `run_data` when the source node has a run entry. */
export function edgesWithRunDataItemCounts(edges: Edge[], runData: RunData): Edge[] {
  return edges.map((e) => {
    const next: Record<string, unknown> =
      typeof e.data === 'object' && e.data != null ? { ...(e.data as Record<string, unknown>) } : {};
    delete next.itemCount;
    const n = runData ? edgeItemCountFromRunData(runData, e.source) : undefined;
    if (n !== undefined) next.itemCount = n;
    return { ...e, data: next };
  });
}

/**
 * Upstream preview for a node: **transitive closure** feeding this node, ordered **sinkward layers** —
 * immediate parents first, then their parents, and so on. Uses each predecessor’s executed output lane
 * `main[0]` from `run_data`. Direct merge inputs retain their `slot` index for `· in N` labels.
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

  const closure = collectUpstreamClosure(nodeId, edges);
  const ordered = orderUpstreamByDistanceSinkward(nodeId, edges, closure);

  const slotForDirectParent = new Map<string, number>();
  for (const e of incoming) {
    if (typeof e.source !== 'string') continue;
    slotForDirectParent.set(e.source, parseHandleIndex(e.targetHandle, 'in-') ?? 0);
  }

  const slots = ordered.map((fromNodeId) => {
    const rec = runData[fromNodeId] as unknown;
    return {
      slot: slotForDirectParent.get(fromNodeId) ?? 0,
      fromNodeId,
      itemsJson: laneMain0ItemsJson(rec),
    };
  });

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
