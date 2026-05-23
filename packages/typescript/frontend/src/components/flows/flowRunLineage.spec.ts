import { describe, expect, it } from 'vitest';
import type { Node } from 'reactflow';
import {
  formatItemLineage,
  formatUpstreamSummary,
  primarySourceRef,
} from './flowRunLineage';

const nodes = [
  {
    id: 't1',
    data: { flowNode: { name: 'Manual trigger' } },
  },
] as Node[];

describe('flowRunLineage', () => {
  it('reads slot-indexed source', () => {
    const source = [[{ previous_node_id: 't1', previous_node_output: 0, previous_node_run: 0 }]];
    expect(primarySourceRef(source, 0)?.previous_node_id).toBe('t1');
    expect(formatUpstreamSummary(source, nodes)).toBe('← Manual trigger');
    expect(formatItemLineage({ source, pairedItem: 0, nodes })).toBe('from Manual trigger · item 0');
  });
});
