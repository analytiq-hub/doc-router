import type { Edge } from 'reactflow';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';
import { TOOL_IN_HANDLE } from '@docrouter/sdk';

const GRAPH_BLOCKED_MESSAGE =
  'Every node must be reachable from at least one trigger through the graph connections. Connect or remove stray nodes before saving.';

/** Saving or activating requires at least one trigger on the revision (covers an empty canvas). */
const MISSING_TRIGGER_MESSAGE =
  'Add at least one trigger node before saving or activating.';

export { GRAPH_BLOCKED_MESSAGE, MISSING_TRIGGER_MESSAGE };

function isToolEdge(edge: Pick<Edge, 'targetHandle' | 'data'>): boolean {
  if (edge.targetHandle === TOOL_IN_HANDLE) return true;
  const ct = (edge.data as { connectionType?: string } | undefined)?.connectionType;
  return ct === 'flows.tool';
}

/**
 * Computes nodes reachable along directed edges (`source → target`) starting from every trigger node.
 * Tool provider nodes are excluded from the save gate (backend parity) but included in `reachable`
 * when wired to a reachable tool consumer so the canvas does not mark them as stray.
 */
export function triggerReachabilityFromGraph(
  flowNodes: readonly FlowNode[],
  edges: readonly Pick<Edge, 'source' | 'target' | 'targetHandle' | 'data'>[],
  nodeTypesByKey: Record<string, FlowNodeType | undefined>,
): { reachable: Set<string>; allReachable: boolean; unreachableNodeIds: string[] } {
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    const cur = adj.get(e.source);
    if (cur) cur.push(e.target);
    else adj.set(e.source, [e.target]);
  }

  const queue: string[] = [];
  const reachable = new Set<string>();
  for (const n of flowNodes) {
    const nt = nodeTypesByKey[n.type];
    if (nt?.is_trigger) {
      reachable.add(n.id);
      queue.push(n.id);
    }
  }

  for (let i = 0; i < queue.length; i++) {
    const u = queue[i];
    const outs = adj.get(u);
    if (!outs) continue;
    for (const v of outs) {
      if (reachable.has(v)) continue;
      reachable.add(v);
      queue.push(v);
    }
  }

  for (const e of edges) {
    if (!isToolEdge(e)) continue;
    if (reachable.has(e.target)) reachable.add(e.source);
  }

  const unreachableNodeIds = flowNodes
    .filter((n) => {
      const nt = nodeTypesByKey[n.type];
      if (nt?.tool_provider) return false;
      return !reachable.has(n.id);
    })
    .map((n) => n.id);
  return {
    reachable,
    allReachable: unreachableNodeIds.length === 0,
    unreachableNodeIds,
  };
}
