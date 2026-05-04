import { describe, expect, it } from 'vitest';
import {
  FLOW_EXPR_REMOVED_NODE_SENTINEL,
  flowCanvasDisplayName,
  rewriteExpressionFieldsDeep,
  rewriteNodePrimaryRefsInExpression,
  rewriteNodePrimaryRefsRemove,
} from './flowExpressionNodeRefs';

describe('flowCanvasDisplayName', () => {
  it('uses trimmed name when non-empty', () => {
    expect(flowCanvasDisplayName({ id: 'x', name: '  Hello  ' })).toBe('Hello');
  });

  it('falls back to id when name empty', () => {
    expect(flowCanvasDisplayName({ id: 'nid-1', name: '   ' })).toBe('nid-1');
  });
});

describe('rewriteNodePrimaryRefsInExpression', () => {
  it('rewrites matching _node bracket keys', () => {
    const body = `_node['Lane A'].json['x'] + _node["Lane A"].output[1].json`;
    const next = rewriteNodePrimaryRefsInExpression(body, 'Lane A', 'Renamed');
    expect(next).toContain('_node["Renamed"].json');
    expect(next).toContain('_node["Renamed"].output[1].json');
    expect(next).not.toContain('Lane A');
  });

  it('does not rewrite other nodes', () => {
    const body = `_node['A'].x + _node['AB'].y`;
    expect(rewriteNodePrimaryRefsInExpression(body, 'A', 'Z')).toBe(`_node["Z"].x + _node['AB'].y`);
  });
});

describe('rewriteNodePrimaryRefsRemove', () => {
  it('substitutes sentinel key', () => {
    const body = `_node['Gone'].json`;
    const out = rewriteNodePrimaryRefsRemove(body, 'Gone');
    expect(out).toBe(`_node[${JSON.stringify(FLOW_EXPR_REMOVED_NODE_SENTINEL)}].json`);
  });
});

describe('rewriteExpressionFieldsDeep', () => {
  it('only touches strings starting with =', () => {
    const params = {
      url: '=_node["Up"].json',
      note: 'not an expression',
      nested: { body_json: '={"a": _node["Up"].json}' },
    };
    const out = rewriteExpressionFieldsDeep(params, (b) => rewriteNodePrimaryRefsInExpression(b, 'Up', 'New')) as typeof params;
    expect(out.note).toBe('not an expression');
    expect(out.url).toBe('=_node["New"].json');
    expect(out.nested.body_json).toBe('={"a": _node["New"].json}');
  });
});
