import { describe, expect, it } from 'vitest';
import { triggerReachabilityFromGraph } from './flowTriggerReachability';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';

const triggerT: FlowNodeType = {
  key: 'flows.trigger.manual',
  label: 'Manual',
  is_trigger: true,
  inputs: 0,
  outputs: 1,
};
const processP: FlowNodeType = {
  key: 'flows.process',
  label: 'Process',
  is_trigger: false,
  inputs: 1,
  outputs: 1,
};

const byKey: Record<string, FlowNodeType | undefined> = {
  [triggerT.key]: triggerT,
  [processP.key]: processP,
};

function nf(id: string, type: string): FlowNode {
  return { id, name: id, type, position: [0, 0], parameters: {}, disabled: false, on_error: 'stop', notes: null };
}

describe('triggerReachabilityFromGraph', () => {
  it('marks chain from trigger as reachable', () => {
    const nodes = [nf('t', triggerT.key), nf('a', processP.key)];
    const edges = [{ source: 't', target: 'a' }];
    const r = triggerReachabilityFromGraph(nodes, edges, byKey);
    expect(r.allReachable).toBe(true);
    expect([...r.reachable].sort()).toEqual(['a', 't']);
  });

  it('flags orphan not downstream of trigger', () => {
    const nodes = [nf('t', triggerT.key), nf('o', processP.key)];
    const edges: { source: string; target: string }[] = [];
    const r = triggerReachabilityFromGraph(nodes, edges, byKey);
    expect(r.allReachable).toBe(false);
    expect(r.unreachableNodeIds).toEqual(['o']);
  });

  it('handles multiple triggers', () => {
    const nodes = [
      nf('t1', triggerT.key),
      nf('t2', triggerT.key),
      nf('x', processP.key),
      nf('y', processP.key),
    ];
    const edges = [
      { source: 't1', target: 'x' },
      { source: 't2', target: 'y' },
    ];
    const r = triggerReachabilityFromGraph(nodes, edges, byKey);
    expect(r.allReachable).toBe(true);
  });

  it('empty node list is all reachable', () => {
    const r = triggerReachabilityFromGraph([], [], byKey);
    expect(r.allReachable).toBe(true);
  });

  it('excludes wired tool_provider nodes from save blocking (backend parity)', () => {
    const agent: FlowNodeType = {
      key: 'flows.agent',
      label: 'Agent',
      is_trigger: false,
      min_inputs: 1,
      max_inputs: 1,
      outputs: 1,
      output_labels: ['out'],
      parameter_schema: {},
      tool_consumer: true,
    };
    const toolCode: FlowNodeType = {
      key: 'flows.tool_code',
      label: 'Tool Code',
      is_trigger: false,
      min_inputs: 0,
      max_inputs: 0,
      outputs: 1,
      output_labels: ['tool'],
      parameter_schema: {},
      tool_provider: true,
      output_port_types: ['flows.tool'],
    };
    const keys: Record<string, FlowNodeType | undefined> = {
      [triggerT.key]: triggerT,
      [agent.key]: agent,
      [toolCode.key]: toolCode,
    };
    const nodes = [nf('t', triggerT.key), nf('a', agent.key), nf('tool', toolCode.key)];
    const edges = [
      { source: 't', target: 'a' },
      { source: 'tool', target: 'a', targetHandle: 'in-tool', data: { connectionType: 'flows.tool' } },
    ];
    const r = triggerReachabilityFromGraph(nodes, edges, keys);
    expect(r.allReachable).toBe(true);
    expect(r.reachable.has('tool')).toBe(true);
  });
});
