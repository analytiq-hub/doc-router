import FlowCanvasEdge from './FlowCanvasEdge';
import FlowCanvasNode from './FlowCanvasNode';

/** Custom edge `type` string; must match edges and `defaultEdgeOptions.type`. */
export const FLOW_RF_LABELED_EDGE_TYPE = 'flowLabeled' as const;

/** Stable references for React Flow (avoids dev warning #002 on remounts). */
export const flowRfNodeTypes = {
  'flow-node': FlowCanvasNode,
} as const;

export const flowRfEdgeTypes = {
  [FLOW_RF_LABELED_EDGE_TYPE]: FlowCanvasEdge,
} as const;
