import type { Edge as RFEdge, Node as RFNode } from 'reactflow';
import type { FlowConnections, FlowNode, FlowNodeConnection, FlowNodeType, FlowRevision } from '@docrouter/sdk';

export type FlowRFNodeData = {
  flowNode: FlowNode;
  nodeType?: FlowNodeType;
};

const OUT_HANDLE_PREFIX = 'out-';
const IN_HANDLE_PREFIX = 'in-';

export function revisionToRF(
  revision: FlowRevision,
  nodeTypesByKey: Record<string, FlowNodeType> = {},
): { nodes: RFNode<FlowRFNodeData>[]; edges: RFEdge[] } {
  const nodes: RFNode<FlowRFNodeData>[] = (revision.nodes || []).map((n) => ({
    id: n.id,
    type: 'flow-node',
    position: { x: n.position?.[0] ?? 0, y: n.position?.[1] ?? 0 },
    data: { flowNode: n, nodeType: nodeTypesByKey[n.type] },
  }));

  const edges: RFEdge[] = [];
  const conns = (revision.connections || {}) as FlowConnections;
  for (const [srcId, lanes] of Object.entries(conns)) {
    const main = lanes?.main || [];
    for (let outIdx = 0; outIdx < main.length; outIdx++) {
      const slot = main[outIdx];
      if (!slot) continue;
      for (const c of slot) {
        const edgeId = `${srcId}:${outIdx}->${c.dest_node_id}:${c.index}:${c.connection_type}`;
        edges.push({
          id: edgeId,
          source: srcId,
          target: c.dest_node_id,
          sourceHandle: `${OUT_HANDLE_PREFIX}${outIdx}`,
          targetHandle: `${IN_HANDLE_PREFIX}${c.index}`,
          type: 'default',
        });
      }
    }
  }

  return { nodes, edges };
}

function parseHandleIndex(handle: string | null | undefined, prefix: string): number | null {
  if (!handle) return null;
  if (!handle.startsWith(prefix)) return null;
  const idx = Number(handle.slice(prefix.length));
  return Number.isFinite(idx) ? idx : null;
}

export function rfToConnections(edges: RFEdge[]): FlowConnections {
  const connections: FlowConnections = {};

  const ensureSlot = (src: string, outIdx: number) => {
    if (!connections[src]) connections[src] = { main: [] };
    const main = connections[src].main;
    while (main.length <= outIdx) main.push(null);
    if (main[outIdx] == null) main[outIdx] = [];
    return main[outIdx] as FlowNodeConnection[];
  };

  for (const e of edges) {
    const outIdx = parseHandleIndex(e.sourceHandle, OUT_HANDLE_PREFIX);
    const inIdx = parseHandleIndex(e.targetHandle, IN_HANDLE_PREFIX);
    if (outIdx == null || inIdx == null) continue;
    const slot = ensureSlot(e.source, outIdx);
    slot.push({ dest_node_id: e.target, connection_type: 'main', index: inIdx });
  }

  return connections;
}

export function rfToRevision(
  rfNodes: RFNode<FlowRFNodeData>[],
  rfEdges: RFEdge[],
  current: FlowRevision,
): { base_flow_revid: string; name: string; nodes: FlowNode[]; connections: FlowConnections; settings: Record<string, unknown>; pin_data: Record<string, unknown> | null } {
  const nodes: FlowNode[] = rfNodes.map((n) => {
    const original = n.data?.flowNode;
    return {
      ...(original as FlowNode),
      id: n.id,
      position: [Math.round(n.position.x), Math.round(n.position.y)],
    };
  });
  const connections = rfToConnections(rfEdges);
  return {
    base_flow_revid: current.flow_revid ?? '',
    name: 'Flow',
    nodes,
    connections,
    settings: current.settings || {},
    pin_data: current.pin_data ?? null,
  };
}

