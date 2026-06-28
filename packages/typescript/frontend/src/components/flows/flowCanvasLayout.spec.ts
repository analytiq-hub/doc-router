import { describe, expect, it } from 'vitest';
import type { Edge, Node } from 'reactflow';
import type { FlowNodeType } from '@docrouter/sdk';
import type { FlowRfNodeData } from './flowRf';
import {
  computeFlowCanvasLayout,
  flowCanvasLayoutNodes,
  flowCanvasLayoutTarget,
} from './flowCanvasLayout';
import { FLOW_CANVAS_GRID_PX } from './canvasGrid';

function rfNode(
  id: string,
  x: number,
  y: number,
  type = 'flows.code',
  selected = false,
): Node<FlowRfNodeData> {
  return {
    id,
    type: 'flow-node',
    position: { x, y },
    selected,
    data: {
      flowNode: {
        id,
        name: id,
        type,
        position: [x, y],
        parameters: {},
        disabled: false,
        on_error: 'stop',
        notes: null,
      },
    },
  };
}

function edge(source: string, target: string, tool = false): Edge {
  return {
    id: `${source}-${target}`,
    source,
    target,
    sourceHandle: 'out-0',
    targetHandle: tool ? 'in-tool' : 'in-0',
    data: tool ? { connectionType: 'flows.tool' as const } : { connectionType: 'main' as const },
  };
}

const nodeTypesByKey: Record<string, FlowNodeType> = {
  'flows.code': { key: 'flows.code', label: 'Code', inputs: 1, outputs: 1 } as FlowNodeType,
  'flows.trigger.manual': {
    key: 'flows.trigger.manual',
    label: 'Manual',
    inputs: 0,
    outputs: 1,
  } as FlowNodeType,
  'flows.agent': {
    key: 'flows.agent',
    label: 'Agent',
    inputs: 1,
    outputs: 1,
    tool_consumer: true,
  } as FlowNodeType,
  'flows.kb_tool': {
    key: 'flows.kb_tool',
    label: 'KB Tool',
    inputs: 0,
    outputs: 1,
    tool_provider: true,
  } as FlowNodeType,
  'flows.flow_tool': {
    key: 'flows.flow_tool',
    label: 'Flow Tool',
    inputs: 0,
    outputs: 1,
    tool_provider: true,
  } as FlowNodeType,
};

describe('computeFlowCanvasLayout', () => {
  it('layouts a linear main-flow left-to-right', () => {
    const nodes = [rfNode('a', 0, 0), rfNode('b', 400, 200), rfNode('c', 50, 500)];
    const edges = [edge('a', 'b'), edge('b', 'c')];

    const { nodes: laidOut } = computeFlowCanvasLayout({
      nodes,
      edges,
      nodeTypesByKey,
      target: 'all',
    });

    const byId = Object.fromEntries(laidOut.map((n) => [n.id, n]));
    expect(byId.a.x).toBeLessThan(byId.b.x);
    expect(byId.b.x).toBeLessThan(byId.c.x);
    laidOut.forEach((n) => {
      expect(n.x % FLOW_CANVAS_GRID_PX).toBe(0);
      expect(n.y % FLOW_CANVAS_GRID_PX).toBe(0);
    });
  });

  it('places tool providers below the agent and keeps trigger on the main row', () => {
    const nodes = [
      rfNode('trigger', 0, 0, 'flows.trigger.manual'),
      rfNode('agent', 200, 0, 'flows.agent'),
      rfNode('kb', 200, 200, 'flows.kb_tool'),
    ];
    const edges = [edge('trigger', 'agent'), edge('kb', 'agent', true)];

    const { nodes: laidOut } = computeFlowCanvasLayout({
      nodes,
      edges,
      nodeTypesByKey,
      target: 'all',
    });

    const byId = Object.fromEntries(laidOut.map((n) => [n.id, n]));
    expect(byId.kb.y).toBeGreaterThan(byId.agent.y);
    expect(byId.trigger.y).toBe(byId.agent.y);
    expect(byId.trigger.x).toBeLessThan(byId.agent.x);
  });

  it('spreads multiple tools horizontally below the agent', () => {
    const nodes = [
      rfNode('trigger', 0, 0, 'flows.trigger.manual'),
      rfNode('agent', 400, 300, 'flows.agent'),
      rfNode('kb', 100, 0, 'flows.kb_tool'),
      rfNode('flowTool', 500, 0, 'flows.flow_tool'),
    ];
    const edges = [
      edge('trigger', 'agent'),
      edge('kb', 'agent', true),
      edge('flowTool', 'agent', true),
    ];

    const { nodes: laidOut } = computeFlowCanvasLayout({
      nodes,
      edges,
      nodeTypesByKey,
      target: 'all',
    });

    const byId = Object.fromEntries(laidOut.map((n) => [n.id, n]));
    expect(byId.kb.y).toBeGreaterThan(byId.agent.y);
    expect(byId.flowTool.y).toBeGreaterThan(byId.agent.y);
    expect(byId.trigger.y).toBe(byId.agent.y);
    expect(byId.kb.x).not.toBe(byId.flowTool.x);
  });

  it('places fork branches below the main spine (split → ocr → llm diamond)', () => {
    const nodes = [
      rfNode('trigger', 0, 100, 'flows.trigger.manual'),
      rfNode('split', 300, 100, 'flows.code'),
      rfNode('ocr', 500, 0, 'flows.code'),
      rfNode('llm', 700, 100, 'flows.code'),
      rfNode('code', 900, 100, 'flows.code'),
    ];
    const edges = [
      edge('trigger', 'split'),
      edge('split', 'ocr'),
      edge('split', 'llm'),
      edge('ocr', 'llm'),
      edge('llm', 'code'),
    ];

    const { nodes: laidOut } = computeFlowCanvasLayout({
      nodes,
      edges,
      nodeTypesByKey,
      target: 'all',
    });

    const byId = Object.fromEntries(laidOut.map((n) => [n.id, n]));
    expect(byId.ocr.y).toBeGreaterThan(byId.split.y);
    expect(byId.llm.y).toBe(byId.split.y);
    expect(byId.code.y).toBe(byId.split.y);
    expect(byId.trigger.y).toBe(byId.split.y);
  });
});

describe('flowCanvasLayoutTarget', () => {
  it('uses selection when more than one node is selected', () => {
    const nodes = [rfNode('a', 0, 0, 'flows.code', true), rfNode('b', 0, 0, 'flows.code', true)];
    expect(flowCanvasLayoutTarget(nodes)).toBe('selection');
  });

  it('uses all when zero or one node is selected', () => {
    expect(flowCanvasLayoutTarget([rfNode('a', 0, 0)])).toBe('all');
    expect(flowCanvasLayoutTarget([rfNode('a', 0, 0, 'flows.code', true)])).toBe('all');
  });
});

describe('flowCanvasLayoutNodes', () => {
  it('returns selected nodes for selection target', () => {
    const nodes = [rfNode('a', 0, 0, 'flows.code', true), rfNode('b', 0, 0)];
    expect(flowCanvasLayoutNodes(nodes, 'selection').map((n) => n.id)).toEqual(['a']);
  });
});
