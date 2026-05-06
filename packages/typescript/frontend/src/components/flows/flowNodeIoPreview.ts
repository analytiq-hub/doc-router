import type { Edge } from 'reactflow';
import type { FlowPinData, FlowPinNodeOutput } from '@docrouter/sdk';
import { parseHandleIndex } from './flowRf';

type RunData = Record<string, unknown> | null | undefined;

/**
 * When exactly one canvas edge targets `nodeId`, return that source id. Used for sole-parent → `_json` drags
 * in the node modal; `null` if merge (multiple sources) or no inbound edge.
 */
export function soleInboundParentFromEdges(nodeId: string, edges: Edge[]): string | null {
  const inc = edges.filter((e) => e.target === nodeId && typeof e.source === 'string');
  return inc.length === 1 ? inc[0].source : null;
}

type NodeRun = {
  /** `main[slot][item]` — executed node output lanes. */
  data?: { main?: unknown };
  status?: string;
  error?: unknown;
};

/** One lane-0 execution item as JSON preview + opaque binary refs (serialized `BinaryRef` dicts per property). */
export type LaneItemSnapshot = { json: unknown; binary: Record<string, unknown> };

function binaryMapFromLaneItem(it: unknown): Record<string, unknown> {
  if (it != null && typeof it === 'object' && 'binary' in it) {
    const b = (it as { binary?: unknown }).binary;
    if (b != null && typeof b === 'object' && !Array.isArray(b)) {
      return b as Record<string, unknown>;
    }
  }
  return {};
}

/** Lane `main[0]` item snapshots (`json` + `binary`) for run_data / execution entries. */
export function laneMain0Snapshots(runEntry: unknown): LaneItemSnapshot[] {
  if (!runEntry || typeof runEntry !== 'object') return [];
  const main = (runEntry as NodeRun).data?.main;
  if (!Array.isArray(main) || main.length === 0) return [];
  const lane = main[0];
  if (!Array.isArray(lane)) return [];
  const out: LaneItemSnapshot[] = [];
  for (const it of lane) {
    if (it != null && typeof it === 'object' && 'json' in (it as object)) {
      out.push({
        json: (it as { json?: unknown }).json ?? null,
        binary: binaryMapFromLaneItem(it),
      });
    } else if (it != null) {
      out.push({ json: it, binary: {} });
    } else {
      out.push({ json: null, binary: {} });
    }
  }
  return out;
}

/** Pin lane snapshots (binary is present only if callers stored it alongside `json`). */
export function laneMain0SnapshotsFromPin(pinOutput: FlowPinNodeOutput | null | undefined): LaneItemSnapshot[] {
  if (!pinOutput?.main?.length) return [];
  const lane = pinOutput.main[0];
  if (!lane || !Array.isArray(lane)) return [];
  const out: LaneItemSnapshot[] = [];
  for (const it of lane) {
    if (it != null && typeof it === 'object' && 'json' in (it as object)) {
      out.push({
        json: (it as { json?: unknown }).json ?? null,
        binary: binaryMapFromLaneItem(it),
      });
    } else if (it != null) {
      out.push({ json: it, binary: {} });
    } else {
      out.push({ json: null, binary: {} });
    }
  }
  return out;
}

function hasPinMainLane(pin: FlowPinNodeOutput | null | undefined): pin is FlowPinNodeOutput {
  return pin != null && typeof pin === 'object' && 'main' in pin && Array.isArray(pin.main);
}

/**
 * Merge revision pin outputs into the execution `run_data` shape so backend `_node[…]` preview
 * matches the INPUT panel (which prefers pin over `run_data` per {@link upstreamOutputItemsPreview}).
 */
export function runDataMergedWithPins(
  runData: RunData,
  pinData: FlowPinData | null | undefined,
): Record<string, unknown> {
  const out = { ...(runData ?? {}) } as Record<string, unknown>;
  if (!pinData) return out;
  for (const [nodeId, pin] of Object.entries(pinData)) {
    if (!hasPinMainLane(pin)) continue;
    out[nodeId] = { status: 'success', data: pin };
  }
  return out;
}

/** All `.json` values from output lane `main[0]` for a node's run entry. */
export function laneMain0ItemsJson(runEntry: unknown): unknown[] {
  return laneMain0Snapshots(runEntry).map((s) => s.json);
}

/** `.json` values from pin lane `main[0]` (`FlowPinNodeOutput` matches execution `data.main` shape without status wrapper). */
export function laneMain0ItemsJsonFromPin(pinOutput: FlowPinNodeOutput | null | undefined): unknown[] {
  return laneMain0SnapshotsFromPin(pinOutput).map((s) => s.json);
}

/** Parallel {@link upstreamOutputItemsPreview} binary maps keyed by attachment name. */
export function upstreamOutputBinariesPreview(
  fromNodeId: string,
  runData: RunData,
  pinData: FlowPinData | null | undefined,
): Record<string, unknown>[] {
  return upstreamOutputSnapshotsPreview(fromNodeId, runData, pinData).map((s) => s.binary);
}

export function upstreamOutputSnapshotsPreview(
  fromNodeId: string,
  runData: RunData,
  pinData: FlowPinData | null | undefined,
): LaneItemSnapshot[] {
  const pinned = pinData?.[fromNodeId];
  if (hasPinMainLane(pinned)) return laneMain0SnapshotsFromPin(pinned);
  if (!runData) return [];
  return laneMain0Snapshots(runData[fromNodeId]);
}

/** Preview items for upstream `fromNodeId`: prefer revision **pin** when present, else execution `run_data`. */
export function upstreamOutputItemsPreview(
  fromNodeId: string,
  runData: RunData,
  pinData: FlowPinData | null | undefined,
): unknown[] {
  return upstreamOutputSnapshotsPreview(fromNodeId, runData, pinData).map((s) => s.json);
}

/**
 * Item count on the **source** node's output lane `main[0]` when that node exists in `run_data`.
 * `undefined` means there is no run snapshot for the source (hide the edge item badge).
 */
export function edgeItemCountFromRunData(
  runData: RunData,
  sourceNodeId: string,
  pinData?: FlowPinData | null,
): number | undefined {
  if (!sourceNodeId) return undefined;
  const pinned = pinData?.[sourceNodeId];
  if (hasPinMainLane(pinned)) {
    return laneMain0ItemsJsonFromPin(pinned).length;
  }
  if (!runData) return undefined;
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
export function edgesWithRunDataItemCounts(
  edges: Edge[],
  runData: RunData,
  pinData?: FlowPinData | null,
): Edge[] {
  return edges.map((e) => {
    const next: Record<string, unknown> =
      typeof e.data === 'object' && e.data != null ? { ...(e.data as Record<string, unknown>) } : {};
    delete next.itemCount;
    const src = typeof e.source === 'string' ? e.source : '';
    const n =
      src && (runData || pinData)
        ? edgeItemCountFromRunData(runData, src, pinData ?? undefined)
        : undefined;
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
  pinData?: FlowPinData | null,
): {
  slots: { slot: number; fromNodeId: string; itemsJson: unknown[]; itemsBinaries: Record<string, unknown>[] }[];
  message: string | null;
} {
  const incoming = edges.filter((e) => e.target === nodeId);
  if (incoming.length === 0) {
    const selfPinned = pinData?.[nodeId];
    const selfSnaps = hasPinMainLane(selfPinned)
      ? laneMain0SnapshotsFromPin(selfPinned)
      : runData
        ? laneMain0Snapshots(runData[nodeId])
        : [];
    if (selfSnaps.length > 0) {
      return {
        slots: [
          {
            slot: 0,
            fromNodeId: nodeId,
            itemsJson: selfSnaps.map((s) => s.json),
            itemsBinaries: selfSnaps.map((s) => s.binary),
          },
        ],
        message: null,
      };
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
    const snaps = upstreamOutputSnapshotsPreview(fromNodeId, runData, pinData);
    return {
      slot: slotForDirectParent.get(fromNodeId) ?? 0,
      fromNodeId,
      itemsJson: snaps.map((s) => s.json),
      itemsBinaries: snaps.map((s) => s.binary),
    };
  });

  return { slots, message: null };
}

/** Output lane `main[0]` JSON items plus optional status/message for badges. */
export function buildNodeOutputPreview(
  nodeId: string,
  runData: RunData,
  pinData?: FlowPinData | null,
): { itemsJson: unknown[]; itemsBinaries: Record<string, unknown>[]; logs: string[]; message: string | null } {
  const pinned = pinData?.[nodeId];
  if (hasPinMainLane(pinned)) {
    const snaps = laneMain0SnapshotsFromPin(pinned);
    return {
      itemsJson: snaps.map((s) => s.json),
      itemsBinaries: snaps.map((s) => s.binary),
      logs: [],
      message: null,
    };
  }
  if (!runData) {
    return { itemsJson: [], itemsBinaries: [], logs: [], message: 'Run the workflow to see output data for this node.' };
  }
  const rec = runData[nodeId] as NodeRun | undefined;
  if (rec == null) {
    return { itemsJson: [], itemsBinaries: [], logs: [], message: null };
  }
  const snaps = laneMain0Snapshots(rec);
  const itemsJson = snaps.map((s) => s.json);
  const itemsBinaries = snaps.map((s) => s.binary);
  const rawLogs = (rec as unknown as { logs?: unknown }).logs;
  const logs = Array.isArray(rawLogs) ? rawLogs.filter((x) => typeof x === 'string') as string[] : [];
  const msg = rec.status && rec.status !== 'success' ? `Status: ${rec.status}` : null;
  return { itemsJson, itemsBinaries, logs, message: msg };
}
