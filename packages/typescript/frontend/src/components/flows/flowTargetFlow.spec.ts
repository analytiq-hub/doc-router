import { describe, expect, it } from 'vitest';
import type { FlowNode } from '@docrouter/sdk';
import {
  flowEditorPath,
  targetFlowIdFromFlowNode,
  targetFlowSubtitle,
} from './flowTargetFlow';

describe('flowTargetFlow', () => {
  it('reads target_flow_id from flow tool and execute flow nodes', () => {
    const toolNode: FlowNode = {
      id: 't1',
      name: 'Gmail tool',
      type: 'flows.flow_tool',
      position: [0, 0],
      parameters: { target_flow_id: 'flow-abc' },
      disabled: false,
      on_error: 'stop',
    };
    expect(targetFlowIdFromFlowNode(toolNode)).toBe('flow-abc');
  });

  it('returns null for unrelated node types', () => {
    const node: FlowNode = {
      id: 'a1',
      name: 'Agent',
      type: 'flows.agent',
      position: [0, 0],
      parameters: { target_flow_id: 'ignored' },
      disabled: false,
      on_error: 'stop',
    };
    expect(targetFlowIdFromFlowNode(node)).toBeNull();
  });

  it('builds editor paths and subtitles', () => {
    expect(flowEditorPath('org1', 'flow-1')).toBe('/orgs/org1/flows/flow-1');
    expect(targetFlowSubtitle('flow-1', { 'flow-1': 'Send email' })).toBe('Flow: Send email');
    expect(targetFlowSubtitle('flow-2', {})).toBe('Flow: flow-2');
  });
});
