import { describe, expect, it } from 'vitest';
import type { Node } from 'reactflow';
import {
  FLOW_NODE_FIT_HEIGHT_PX,
  FLOW_NODE_FIT_WIDTH_PX,
  getFlowCanvasNodesBounds,
} from './flowCanvasConstants';

describe('getFlowCanvasNodesBounds', () => {
  it('uses stable footprint when nodes are not measured yet', () => {
    const nodes = [
      { id: 'a', position: { x: 0, y: 0 }, hidden: false },
      { id: 'b', position: { x: 200, y: 100 }, hidden: false },
    ] as Node[];

    expect(getFlowCanvasNodesBounds(nodes)).toEqual({
      x: 0,
      y: 0,
      width: 200 + FLOW_NODE_FIT_WIDTH_PX,
      height: 100 + FLOW_NODE_FIT_HEIGHT_PX,
    });
  });

  it('ignores hidden nodes', () => {
    const nodes = [
      { id: 'a', position: { x: 0, y: 0 }, hidden: false },
      { id: 'b', position: { x: 500, y: 0 }, hidden: true },
    ] as Node[];

    expect(getFlowCanvasNodesBounds(nodes)).toEqual({
      x: 0,
      y: 0,
      width: FLOW_NODE_FIT_WIDTH_PX,
      height: FLOW_NODE_FIT_HEIGHT_PX,
    });
  });
});
