import { describe, expect, it } from 'vitest';
import type { FlowNode } from '@docrouter/sdk';
import {
  exampleArgumentsFromSchema,
  toolArgumentsSchemaForNode,
  toolNameFromNode,
} from './toolTestUtils';

describe('toolTestUtils', () => {
  it('exampleArgumentsFromSchema fills required keys', () => {
    expect(
      exampleArgumentsFromSchema({
        type: 'object',
        properties: { q: { type: 'string' }, n: { type: 'integer', default: 2 } },
        required: ['q'],
      }),
    ).toEqual({ q: '', n: 2 });
  });

  it('toolArgumentsSchemaForNode reads tool_code parameters_schema', () => {
    const node: FlowNode = {
      id: 't1',
      name: 'Tool',
      type: 'flows.tool_code',
      position: [0, 0],
      parameters: {
        parameters_schema: { type: 'object', properties: { city: { type: 'string' } } },
      },
      disabled: false,
      on_error: 'stop',
      notes: null,
    };
    expect(toolArgumentsSchemaForNode(node, { key: 'flows.tool_code' } as never).properties).toHaveProperty(
      'city',
    );
  });

  it('toolNameFromNode reads parameters.tool_name', () => {
    const node: FlowNode = {
      id: 't1',
      name: 'Tool',
      type: 'flows.tool_code',
      position: [0, 0],
      parameters: { tool_name: 'weather' },
      disabled: false,
      on_error: 'stop',
      notes: null,
    };
    expect(toolNameFromNode(node)).toBe('weather');
  });
});
