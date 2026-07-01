import { finalizePersistedFlowNodeParameters } from './flow-parameter-merge';
import { edgeConnectionType } from './flow-port-types';
import type {
  FlowConnectionType,
  FlowConnections,
  FlowNode,
  FlowNodeConnection,
  FlowNodeType,
  FlowRevision,
  SaveRevisionParams,
} from './types/flows';

/** React Flow data payload (rendered in the app; `nodeType` is optional in saved graphs). */
export type FlowRfNodeData = {
  flowNode: FlowNode;
  nodeType?: FlowNodeType;
};

/** Canvas node shape (compatible with `reactflow` `Node<FlowRfNodeData>`). */
export type FlowRfNode = {
  id: string;
  type?: string;
  position: { x: number; y: number };
  data: FlowRfNodeData;
};

/** Canvas edge shape (compatible with `reactflow` `Edge`). */
export type FlowRfEdge = {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  type?: string;
  data?: { connectionType?: FlowConnectionType };
};

const OUT_HANDLE_PREFIX = 'out-';
const IN_HANDLE_PREFIX = 'in-';
export const TOOL_IN_HANDLE = 'in-tool';
export const TOOL_OUT_HANDLE = 'out-tool';

export function revisionToRF(
  revision: FlowRevision,
  nodeTypesByKey: Record<string, FlowNodeType> = {},
): { nodes: FlowRfNode[]; edges: FlowRfEdge[] } {
  const nodes: FlowRfNode[] = (revision.nodes || []).map((n) => ({
    id: n.id,
    type: 'flow-node',
    position: { x: n.position?.[0] ?? 0, y: n.position?.[1] ?? 0 },
    data: { flowNode: n, nodeType: nodeTypesByKey[n.type] },
  }));

  const edges: FlowRfEdge[] = [];
  const conns = (revision.connections || {}) as FlowConnections;
  for (const [srcId, lanes] of Object.entries(conns)) {
    const main = lanes?.main || [];
    for (let outIdx = 0; outIdx < main.length; outIdx++) {
      const slot = main[outIdx];
      if (!slot) continue;
      for (const c of slot) {
        const edgeId = `${srcId}:${outIdx}->${c.dest_node_id}:${c.index}:${c.connection_type}`;
        const isTool = c.connection_type === 'flows.tool';
        edges.push({
          id: edgeId,
          source: srcId,
          target: c.dest_node_id,
          sourceHandle: `${OUT_HANDLE_PREFIX}${outIdx}`,
          targetHandle: isTool ? TOOL_IN_HANDLE : `${IN_HANDLE_PREFIX}${c.index}`,
          type: 'default',
          data: { connectionType: c.connection_type },
          ...(isTool ? { style: { stroke: '#f59e0b', strokeWidth: 1.5, strokeDasharray: '6 4' } } : {}),
        });
      }
    }
  }

  return { nodes, edges };
}

export function parseHandleIndex(handle: string | null | undefined, prefix: string): number | null {
  if (!handle) return null;
  if (!handle.startsWith(prefix)) return null;
  const idx = Number(handle.slice(prefix.length));
  return Number.isFinite(idx) ? idx : null;
}

export function rfToConnections(edges: FlowRfEdge[]): FlowConnections {
  const connections: FlowConnections = {};

  const ensureSlot = (src: string, outIdx: number) => {
    if (!connections[src]) connections[src] = { main: [] };
    const main = connections[src].main;
    while (main.length <= outIdx) main.push(null);
    if (main[outIdx] == null) main[outIdx] = [];
    return main[outIdx] as FlowNodeConnection[];
  };

  const toolIndexByTarget: Record<string, number> = {};

  for (const e of edges) {
    const outIdx = parseHandleIndex(e.sourceHandle, OUT_HANDLE_PREFIX);
    if (outIdx == null) continue;
    const ct = edgeConnectionType(e);
    let inIdx: number;
    if (e.targetHandle === TOOL_IN_HANDLE || ct === 'flows.tool') {
      inIdx = toolIndexByTarget[e.target] ?? 0;
      toolIndexByTarget[e.target] = inIdx + 1;
    } else {
      const parsed = parseHandleIndex(e.targetHandle, IN_HANDLE_PREFIX);
      if (parsed == null) continue;
      inIdx = parsed;
    }
    const slot = ensureSlot(e.source, outIdx);
    slot.push({
      dest_node_id: e.target,
      connection_type: ct,
      index: inIdx,
    });
  }

  return connections;
}

/**
 * How many *target* (input) handles a node should display for wiring.
 * Matches engine semantics: slots are `0..count-1` and must be within `max_inputs` when set.
 */
export function inputHandleCount(nt: FlowNodeType | undefined | null): number {
  if (!nt) return 1;
  if (nt.max_inputs != null) return Math.max(0, nt.max_inputs);
  return Math.max(0, nt.min_inputs);
}

export function rfToRevision(
  rfNodes: FlowRfNode[],
  rfEdges: FlowRfEdge[],
  current: FlowRevision,
  name: string,
): Omit<SaveRevisionParams, 'base_flow_revid'> & { base_flow_revid: string } {
  const nodes: FlowNode[] = rfNodes.map((n) => {
    const original = n.data?.flowNode;
    const schema = n.data?.nodeType?.parameter_schema;
    const parameters = finalizePersistedFlowNodeParameters(
      schema,
      (original?.parameters ?? {}) as Record<string, unknown>,
    );
    return {
      ...(original as FlowNode),
      id: n.id,
      position: [Math.round(n.position.x), Math.round(n.position.y)],
      parameters,
    };
  });
  const connections = rfToConnections(rfEdges);
  return {
    base_flow_revid: current.flow_revid ?? '',
    name,
    nodes,
    connections,
    settings: current.settings || {},
    pin_data: current.pin_data ?? null,
  };
}

/**
 * Stable fingerprint of the editable revision payload (name + graph + settings).
 * Excludes `flow_revid` and version metadata from `current` (only settings/pin_data are pulled).
 * Includes node position so layout-only moves are saveable; the server excludes position from
 * `graph_hash` so those saves do not bump flow version.
 */
export function revisionContentFingerprint(
  name: string,
  rfNodes: FlowRfNode[],
  rfEdges: FlowRfEdge[],
  current: FlowRevision,
): string {
  const body = rfToRevision(rfNodes, rfEdges, current, name);
  return JSON.stringify({
    name: body.name,
    nodes: body.nodes,
    connections: body.connections,
    settings: body.settings,
    pin_data: body.pin_data,
  });
}
