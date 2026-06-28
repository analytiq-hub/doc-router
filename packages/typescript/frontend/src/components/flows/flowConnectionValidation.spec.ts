import { describe, expect, it } from 'vitest';
import type { FlowNodeType } from '@docrouter/sdk';
import { TOOL_IN_HANDLE } from './flowRf';
import { isValidFlowConnection } from './flowConnectionValidation';

const toolCodeType: FlowNodeType = {
  key: 'flows.tool_code',
  label: 'Tool Code',
  category: 'AI',
  is_trigger: false,
  min_inputs: 0,
  max_inputs: 0,
  outputs: 1,
  output_labels: ['tool'],
  output_port_types: ['flows.tool'],
  tool_provider: true,
  parameter_schema: { type: 'object', properties: {} },
};

const codeType: FlowNodeType = {
  key: 'flows.code',
  label: 'Code',
  category: 'Generic',
  is_trigger: false,
  min_inputs: 1,
  max_inputs: 1,
  outputs: 1,
  parameter_schema: { type: 'object', properties: {} },
};

const agentType: FlowNodeType = {
  key: 'flows.agent',
  label: 'Agent',
  category: 'AI',
  is_trigger: false,
  min_inputs: 1,
  max_inputs: 1,
  outputs: 1,
  tool_consumer: true,
  parameter_schema: { type: 'object', properties: {} },
};

const byKey = {
  'flows.tool_code': toolCodeType,
  'flows.code': codeType,
  'flows.agent': agentType,
};

function node(id: string, type: string, nodeType?: FlowNodeType) {
  return {
    id,
    data: {
      flowNode: { type, id, name: id, position: [0, 0], parameters: {} },
      nodeType,
    },
  };
}

describe('isValidFlowConnection', () => {
  it('allows tool provider → agent on in-tool', () => {
    expect(
      isValidFlowConnection(
        {
          source: 'tool',
          target: 'agent',
          sourceHandle: 'out-0',
          targetHandle: TOOL_IN_HANDLE,
        },
        [node('tool', 'flows.tool_code', toolCodeType), node('agent', 'flows.agent', agentType)],
        byKey,
      ),
    ).toBe(true);
  });

  it('rejects main-path connection into a tool provider', () => {
    expect(
      isValidFlowConnection(
        {
          source: 'code',
          target: 'tool',
          sourceHandle: 'out-0',
          targetHandle: 'in-0',
        },
        [node('code', 'flows.code', codeType), node('tool', 'flows.tool_code', toolCodeType)],
        byKey,
      ),
    ).toBe(false);
  });

  it('rejects tool provider → main consumer', () => {
    expect(
      isValidFlowConnection(
        {
          source: 'tool',
          target: 'code',
          sourceHandle: 'out-0',
          targetHandle: 'in-0',
        },
        [node('tool', 'flows.tool_code', toolCodeType), node('code', 'flows.code', codeType)],
        byKey,
      ),
    ).toBe(false);
  });
});
