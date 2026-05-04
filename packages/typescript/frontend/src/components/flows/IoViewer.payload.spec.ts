import { describe, expect, it } from 'vitest';
import { parseFlowValueDragPayload, payloadToExpression, type FlowValueDragPayload } from './IoViewer';

function jp(nodeId: string, source: 'nodeOutput' | 'nodeInput', path: (string | number)[], display?: string): FlowValueDragPayload {
  return {
    kind: 'jsonPath',
    nodeId,
    source,
    path,
    exampleValue: null,
    ...(display ? { nodeDisplayName: display } : {}),
  };
}

describe('payloadToExpression', () => {
  it('uses _json only for this node nodeInput (configured inbound)', () => {
    const p = jp('n-current', 'nodeInput', ['url']);
    expect(payloadToExpression(p, 'n-current')).toBe('=_json["url"]');
  });

  it('uses _node for upstream nodeOutput when multiple inbound parents or sole parent not passed', () => {
    const p = jp('n-upstream', 'nodeOutput', ['sku'], 'Parse');
    expect(payloadToExpression(p, 'n-current')).toBe('=_node["Parse"].json["sku"]');
  });

  it('uses _json for nodeOutput when it is the sole inbound parent of the configured node', () => {
    const p = jp('n-upstream', 'nodeOutput', ['sku'], 'Parse');
    expect(payloadToExpression(p, 'n-current', 0, { soleInboundParentNodeId: 'n-upstream' })).toBe('=_json["sku"]');
  });

  it('uses _node by id when upstream has no display name', () => {
    const p = jp('n-upstream', 'nodeOutput', ['sku']);
    expect(payloadToExpression(p, 'n-current')).toBe('=_node["n-upstream"].json["sku"]');
  });

  it('uses _node for own nodeOutput (same id)', () => {
    const p = jp('n-current', 'nodeOutput', ['x'], 'Echo');
    expect(payloadToExpression(p, 'n-current')).toBe('=_node["Echo"].json["x"]');
  });

  it('does not treat mismatched nodeInput as _json', () => {
    const p = jp('n-other', 'nodeInput', ['x']);
    expect(payloadToExpression(p, 'n-current')).toBe('=_node["n-other"].json["x"]');
  });

  it('serializes numeric and nested path segments (same as runtime indexing)', () => {
    expect(payloadToExpression(jp('n-current', 'nodeInput', [0, 'items', 2]), 'n-current')).toBe('=_json[0]["items"][2]');
    expect(
      payloadToExpression(jp('u', 'nodeOutput', ['foo', 'bar-baz'], 'Up'), 'x', 0, { soleInboundParentNodeId: 'u' }),
    ).toBe('=_json["foo"]["bar-baz"]');
  });

  it('builds contextVar expressions from root name and path', () => {
    const p: FlowValueDragPayload = {
      kind: 'contextVar',
      varName: '_execution',
      path: ['flow_id'],
      exampleValue: null,
    };
    expect(payloadToExpression(p)).toBe('=_execution["flow_id"]');
  });

  it('uses output slot index for non-zero lanes', () => {
    const p = jp('up', 'nodeOutput', ['z'], 'Up');
    expect(payloadToExpression(p, 'cur', 1)).toBe('=_node["Up"].output[1].json["z"]');
  });
});

describe('parseFlowValueDragPayload', () => {
  it('accepts jsonPath with optional nodeDisplayName', () => {
    const raw = JSON.stringify({
      kind: 'jsonPath',
      source: 'nodeOutput',
      nodeId: 'n1',
      nodeDisplayName: 'Parse',
      path: ['sku'],
      exampleValue: 1,
    });
    expect(parseFlowValueDragPayload(raw)).toEqual({
      kind: 'jsonPath',
      source: 'nodeOutput',
      nodeId: 'n1',
      nodeDisplayName: 'Parse',
      path: ['sku'],
      exampleValue: 1,
    });
  });

  it('accepts contextVar', () => {
    const raw = JSON.stringify({
      kind: 'contextVar',
      varName: '_json',
      path: [],
      exampleValue: null,
    });
    expect(parseFlowValueDragPayload(raw)).not.toBeNull();
  });

  it('returns null for invalid JSON', () => {
    expect(parseFlowValueDragPayload('{')).toBeNull();
  });

  it('returns null when jsonPath missing nodeId or path is not an array', () => {
    expect(parseFlowValueDragPayload(JSON.stringify({ kind: 'jsonPath', source: 'nodeInput', path: [] }))).toBeNull();
    expect(
      parseFlowValueDragPayload(
        JSON.stringify({ kind: 'jsonPath', source: 'nodeInput', nodeId: 'x', path: 'bad', exampleValue: null }),
      ),
    ).toBeNull();
  });

  it('returns null when contextVar missing varName', () => {
    expect(parseFlowValueDragPayload(JSON.stringify({ kind: 'contextVar', path: [], exampleValue: null }))).toBeNull();
  });

  it('returns null for unknown kind', () => {
    expect(parseFlowValueDragPayload(JSON.stringify({ kind: 'other', x: 1 }))).toBeNull();
  });
});
