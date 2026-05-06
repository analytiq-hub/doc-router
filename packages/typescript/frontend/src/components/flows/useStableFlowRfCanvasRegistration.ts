'use client';

import { useMemo } from 'react';
import FlowCanvasEdge from './FlowCanvasEdge';
import FlowCanvasNode from './FlowCanvasNode';
import { FLOW_RF_LABELED_EDGE_TYPE } from './flowRfCanvasTypes';

/**
 * Stable `nodeTypes` / `edgeTypes` objects for `<ReactFlow />` inside a client component.
 * React Flow warns in dev (#002) if these maps are recreated with the same keys each render.
 */
export function useStableFlowRfCanvasRegistration() {
  return useMemo(
    () => ({
      rfCanvasNodeTypes: { 'flow-node': FlowCanvasNode },
      rfCanvasEdgeTypes: { [FLOW_RF_LABELED_EDGE_TYPE]: FlowCanvasEdge },
    }),
    [],
  );
}
