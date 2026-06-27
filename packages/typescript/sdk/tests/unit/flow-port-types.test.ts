import type { FlowNodeType } from '../../src/types/flows';
import { outputPortType, outputPortTypes } from '../../src/flow-port-types';

const toolProvider: FlowNodeType = {
  key: 'flows.tool_code',
  label: 'Tool Code',
  description: 'x',
  category: 'AI',
  is_trigger: false,
  min_inputs: 0,
  max_inputs: 0,
  outputs: 1,
  output_labels: ['tool'],
  parameter_schema: {},
  tool_provider: true,
};

describe('flow-port-types', () => {
  it('defaults tool_provider outputs to flows.tool', () => {
    expect(outputPortTypes(toolProvider)).toEqual(['flows.tool']);
    expect(outputPortType(toolProvider, 0)).toBe('flows.tool');
  });

  it('honors explicit output_port_types on tool_provider nodes', () => {
    const nt: FlowNodeType = {
      ...toolProvider,
      output_port_types: ['flows.tool'],
    };
    expect(outputPortType(nt, 0)).toBe('flows.tool');
  });
});
