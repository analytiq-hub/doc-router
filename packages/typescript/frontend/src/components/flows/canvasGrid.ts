import type { Node } from 'reactflow';
import type { FlowNode } from '@docrouter/sdk';

/**
 * Canvas dot spacing and drag snap step (px).
 * Keep in sync with `<Background gap={…}>`.
 */
export const FLOW_CANVAS_GRID_PX = 24;

export function snapToFlowGrid(p: { x: number; y: number }): { x: number; y: number } {
  const g = FLOW_CANVAS_GRID_PX;
  return {
    x: Math.round(p.x / g) * g,
    y: Math.round(p.y / g) * g,
  };
}

/** Snap every node’s canvas position (and `flowNode.position`) to the flow grid. */
export function snapRfNodesPositions<T extends { flowNode: FlowNode }>(nodes: Node<T>[]): Node<T>[] {
  return nodes.map((n) => {
    const pos = snapToFlowGrid(n.position);
    if (pos.x === n.position.x && pos.y === n.position.y) return n;
    return {
      ...n,
      position: pos,
      data: {
        ...n.data,
        flowNode: {
          ...n.data.flowNode,
          position: [pos.x, pos.y],
        },
      },
    };
  });
}
