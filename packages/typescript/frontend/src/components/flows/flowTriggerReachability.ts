import type { Edge } from 'reactflow';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';

const GRAPH_BLOCKED_MESSAGE =
  'Every node must be reachable from at least one trigger through the graph connections. Connect or remove stray nodes before saving.';

/** Saving or activating requires at least one trigger on the revision (covers an empty canvas). */
const MISSING_TRIGGER_MESSAGE =
  'Add at least one trigger node before saving or activating.';

export { GRAPH_BLOCKED_MESSAGE, MISSING_TRIGGER_MESSAGE };

/**
 * Computes nodes reachable along directed edges (`source → target`) starting from every trigger node.
 */
export function triggerReachabilityFromGraph(
  flowNodes: readonly FlowNode[],
  edges: readonly Pick<Edge, 'source' | 'target'>[],
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

  const unreachableNodeIds = flowNodes.filter((n) => !reachable.has(n.id)).map((n) => n.id);
  return {
    reachable,
    allReachable: unreachableNodeIds.length === 0,
    unreachableNodeIds,
  };
}
