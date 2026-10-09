'use client';

import type { EdgeTypes, NodeTypes } from 'reactflow';
import FlowCanvasEdge from './FlowCanvasEdge';
import FlowCanvasNode from './FlowCanvasNode';
import { FLOW_RF_LABELED_EDGE_TYPE } from './flowRfCanvasTypes';

/**
 * Stable `nodeTypes` / `edgeTypes` for `<ReactFlow />`.
 * Must be module singletons — React Flow warns in dev (#002) if these maps are recreated each render.
 */
export const RF_CANVAS_NODE_TYPES: NodeTypes = {
  'flow-node': FlowCanvasNode,
};

export const RF_CANVAS_EDGE_TYPES: EdgeTypes = {
  [FLOW_RF_LABELED_EDGE_TYPE]: FlowCanvasEdge,
};
