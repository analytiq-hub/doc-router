import type { Node } from 'reactflow';
import type { FlowRfNodeData } from './flowRf';

export type FlowSourceRef = {
  previous_node_id: string;
  previous_node_output?: number;
  previous_node_run?: number;
};

function isSourceRef(v: unknown): v is FlowSourceRef {
  return Boolean(v && typeof v === 'object' && typeof (v as FlowSourceRef).previous_node_id === 'string');
}

/** First provenance record for an input slot (``run_data[node].source[slot][0]``). */
export function primarySourceRef(source: unknown, slotIndex = 0): FlowSourceRef | null {
  if (!Array.isArray(source)) return null;
  const slot = source[slotIndex];
  if (!Array.isArray(slot) || slot.length === 0) return null;
  const first = slot[0];
  return isSourceRef(first) ? first : null;
}

export function nodeLabelFromId(nodes: Array<Node<FlowRfNodeData>>, nodeId: string): string {
  const n = nodes.find((x) => x.id === nodeId);
  const name = n?.data?.flowNode?.name?.trim();
  return name || nodeId;
}

/** Compact overview line, e.g. ``← Manual trigger``. */
export function formatUpstreamSummary(
  source: unknown,
  nodes: Array<Node<FlowRfNodeData>>,
  slotIndex = 0,
): string | null {
  const ref = primarySourceRef(source, slotIndex);
  if (!ref) return null;
  return `← ${nodeLabelFromId(nodes, ref.previous_node_id)}`;
}

/** Schema-mode caption, e.g. ``from Manual trigger · item 0``. */
export function formatItemLineage(opts: {
  source?: unknown;
  pairedItem?: unknown;
  nodes: Array<Node<FlowRfNodeData>>;
  sourceSlot?: number;
}): string | null {
  const ref = primarySourceRef(opts.source, opts.sourceSlot ?? 0);
  if (!ref) return null;
  const name = nodeLabelFromId(opts.nodes, ref.previous_node_id);
  const pi = opts.pairedItem;
  if (typeof pi === 'number') {
    return `from ${name} · item ${pi}`;
  }
  if (Array.isArray(pi) && pi.length > 0 && typeof pi[0] === 'number') {
    return `from ${name} · item ${pi[0]}`;
  }
  return `from ${name}`;
}

/** Read ``paired_item`` from the first item in ``run_data[node].data.main[0]``. */
export function pairedItemFromRunEntry(entry: unknown): unknown {
  if (!entry || typeof entry !== 'object') return undefined;
  const data = (entry as { data?: unknown }).data;
  if (!data || typeof data !== 'object') return undefined;
  const main = (data as { main?: unknown }).main;
  if (!Array.isArray(main) || !Array.isArray(main[0]) || main[0].length === 0) return undefined;
  const it = main[0][0];
  if (!it || typeof it !== 'object') return undefined;
  return (it as Record<string, unknown>).paired_item;
}
