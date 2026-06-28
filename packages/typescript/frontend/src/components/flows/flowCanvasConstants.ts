import { MarkerType, type EdgeMarker, type Node } from 'reactflow';

/** ~half the default React Flow closed-arrow marker (20×20). */
export const FLOW_EDGE_MARKER: EdgeMarker = {
  type: MarkerType.ArrowClosed,
  width: 10,
  height: 10,
};

/** Visual footprint for fit-to-view (120px wrapper + label below the 96px body). */
export const FLOW_NODE_FIT_WIDTH_PX = 120;
export const FLOW_NODE_FIT_HEIGHT_PX = 136;

export const FLOW_CANVAS_FIT_PADDING = 0.2;
export const FLOW_CANVAS_FIT_MIN_ZOOM = 0.35;
export const FLOW_CANVAS_FIT_MAX_ZOOM = 1;

export type FlowCanvasFitViewOptions = {
  padding?: number;
  minZoom?: number;
  maxZoom?: number;
  duration?: number;
  nodes?: Array<{ id: string }>;
};

/** Bounds from node positions + stable layout footprint (ignores stale/zero measurements). */
export function getFlowCanvasNodesBounds(
  nodes: Node[],
): { x: number; y: number; width: number; height: number } {
  const visible = nodes.filter((n) => !n.hidden);
  if (!visible.length) return { x: 0, y: 0, width: 0, height: 0 };

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const node of visible) {
    const w =
      typeof node.width === 'number' && node.width > 0 ? node.width : FLOW_NODE_FIT_WIDTH_PX;
    const h =
      typeof node.height === 'number' && node.height > 0 ? node.height : FLOW_NODE_FIT_HEIGHT_PX;
    minX = Math.min(minX, node.position.x);
    minY = Math.min(minY, node.position.y);
    maxX = Math.max(maxX, node.position.x + w);
    maxY = Math.max(maxY, node.position.y + h);
  }

  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}
