import type { FlowNodeType, FlowRevision } from '../../src/types/flows';
import {
  inputHandleCount,
  revisionContentFingerprint,
  revisionToRF,
  rfToConnections,
  rfToRevision,
} from '../../src/flow-rf';

const simpleNodeType: FlowNodeType = {
  key: 'tests.passthrough',
  label: 'Passthrough',
  description: 'x',
  category: 'Test',
  is_trigger: false,
  min_inputs: 1,
  max_inputs: 1,
  outputs: 1,
  output_labels: ['out'],
  parameter_schema: {},
};

const mergeNodeType: FlowNodeType = {
  key: 'tests.merge2',
  label: 'Merge',
  description: 'm',
  category: 'Test',
  is_trigger: false,
  min_inputs: 2,
  max_inputs: 2,
  outputs: 1,
  output_labels: ['out'],
  parameter_schema: {},
};

function _node(id: string, x: number, y: number, type: string, name: string): FlowRevision['nodes'][0] {
  return {
    id,
    name,
    type,
    position: [x, y],
    parameters: {},
    disabled: false,
    on_error: 'stop',
    notes: null,
  };
}

function baseRev(nodes: FlowRevision['nodes'], connections: FlowRevision['connections']): FlowRevision {
  return {
    flow_revid: 'rev-1',
    flow_id: 'f-1',
    flow_version: 1,
    graph_hash: 'h',
    nodes,
    connections,
    settings: { k: 1 },
    pin_data: null,
    engine_version: 1,
  };
}

describe('flow-rf', () => {
  it('round-trips a single edge through RF', () => {
    const a = _node('A', 0, 0, 'tests.passthrough', 'A');
    const b = _node('B', 200, 0, 'tests.passthrough', 'B');
    const rev = baseRev(
      [a, b],
      { A: { main: [[{ dest_node_id: 'B', connection_type: 'main', index: 0 }]] } },
    );
    const byKey = { 'tests.passthrough': simpleNodeType };
    const { nodes, edges } = revisionToRF(rev, byKey);
    expect(nodes).toHaveLength(2);
    expect(edges).toHaveLength(1);
    expect(edges[0].source).toBe('A');
    expect(edges[0].target).toBe('B');
    expect(edges[0].sourceHandle).toBe('out-0');
    expect(edges[0].targetHandle).toBe('in-0');
    const conns = rfToConnections(edges);
    expect(conns).toEqual(rev.connections);
    const out = rfToRevision(nodes, edges, rev, 'Flow name');
    expect(out.name).toBe('Flow name');
    expect(out.connections).toEqual(rev.connections);
    expect(out.settings).toEqual(rev.settings);
  });

  it('supports sparse output slots and multiple edges from one output', () => {
    const t = _node('T', 0, 0, 'tests.passthrough', 'T');
    const l = _node('L', 100, 0, 'tests.passthrough', 'L');
    const r = _node('R', 100, 80, 'tests.passthrough', 'R');
    const rev = baseRev(
      [t, l, r],
      {
        T: {
          main: [
            [
              { dest_node_id: 'L', connection_type: 'main', index: 0 },
              { dest_node_id: 'R', connection_type: 'main', index: 0 },
            ],
            null,
          ],
        },
      },
    );
    const byKey = { 'tests.passthrough': simpleNodeType };
    const { nodes, edges } = revisionToRF(rev, byKey);
    expect(edges).toHaveLength(2);
    const back = rfToConnections(edges);
    expect(back.T?.main[0]).toEqual(rev.connections.T?.main[0]);
    // Trailing `null` output slot is not preserved when there are no edges from that slot.
    const out = rfToRevision(nodes, edges, rev, 'N');
    expect(out.connections.T?.main[0]).toEqual(rev.connections.T?.main[0]);
  });

  it('maps second input on merge (index=1)', () => {
    const a = _node('A', 0, 0, 'tests.passthrough', 'A');
    const b = _node('B', 0, 50, 'tests.passthrough', 'B');
    const m = _node('M', 200, 25, 'tests.merge2', 'M');
    const rev = baseRev(
      [a, b, m],
      {
        A: { main: [[{ dest_node_id: 'M', connection_type: 'main', index: 0 }]] },
        B: { main: [[{ dest_node_id: 'M', connection_type: 'main', index: 1 }]] },
        M: { main: [[]] },
      },
    );
    const byKey = { 'tests.passthrough': simpleNodeType, 'tests.merge2': mergeNodeType };
    const { edges } = revisionToRF(rev, byKey);
    const mEdges = edges.filter((e) => e.target === 'M');
    expect(mEdges.map((e) => e.targetHandle).sort()).toEqual(['in-0', 'in-1']);
    const { nodes } = revisionToRF(rev, byKey);
    const back = rfToRevision(nodes, edges, rev, 'M');
    const conns = rfToConnections(edges);
    // Sources with no outgoing edges are omitted (acceptable for the editor round-trip).
    expect(conns.A).toEqual(rev.connections.A);
    expect(conns.B).toEqual(rev.connections.B);
    expect(back.connections.A).toEqual(rev.connections.A);
    expect(back.connections.B).toEqual(rev.connections.B);
  });

  it('inputHandleCount uses max_inputs when set', () => {
    expect(inputHandleCount(mergeNodeType)).toBe(2);
    expect(
      inputHandleCount({
        ...simpleNodeType,
        min_inputs: 0,
        max_inputs: 0,
      } as FlowNodeType),
    ).toBe(0);
  });

  it('fingerprint is stable for identical graph', () => {
    const rev = baseRev(
      [_node('A', 1, 2, 'tests.passthrough', 'A')],
      {},
    );
    const { nodes, edges } = revisionToRF(rev, { 'tests.passthrough': simpleNodeType });
    const fp1 = revisionContentFingerprint('F', nodes, edges, rev);
    const fp2 = revisionContentFingerprint('F', nodes, edges, rev);
    expect(fp1).toBe(fp2);
    const fp3 = revisionContentFingerprint('Other', nodes, edges, rev);
    expect(fp3).not.toBe(fp1);
  });
});
