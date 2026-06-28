import { describe, expect, it } from 'vitest';
import { FLOW_BUILTIN_ICON_KEYS } from './FlowNodeTypeIcon';

describe('FlowNodeTypeIcon', () => {
  it('registers icon keys for AI palette nodes', () => {
    for (const key of [
      'chat_trigger',
      'agent',
      'tool_code',
      'flow_tool',
      'execute_flow',
      'knowledge_base',
      'tool_executor',
      'tool_trigger',
    ]) {
      expect(FLOW_BUILTIN_ICON_KEYS).toContain(key);
    }
  });
});
