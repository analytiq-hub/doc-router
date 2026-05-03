import { describe, expect, it } from 'vitest';
import {
  applyParameterPatch,
  clearHiddenFieldsToDefaults,
  defaultFromSubschema,
  evalShowWhen,
  getOrderedKeys,
  getVisiblePropertyKeys,
  mergeParameterDefaults,
} from './flowSchemaParameterUtils';

const httpLikeSchema = {
  type: 'object',
  additionalProperties: false,
  'x-docrouter-order': ['body_mode', 'body_json', 'url'],
  properties: {
    url: { type: 'string', default: '' },
    body_mode: {
      type: 'string',
      enum: ['none', 'json', 'raw'],
      default: 'none',
    },
    body_json: {
      type: 'string',
      default: '',
      'x-docrouter-showWhen': { field: 'body_mode', in: ['json'] },
    },
  },
};

describe('flowSchemaParameterUtils', () => {
  it('getOrderedKeys respects x-docrouter-order then appends remaining', () => {
    expect(getOrderedKeys(httpLikeSchema)).toEqual(['body_mode', 'body_json', 'url']);
  });

  it('evalShowWhen handles in and equals', () => {
    expect(evalShowWhen({ field: 'body_mode', in: ['json'] }, { body_mode: 'json' })).toBe(true);
    expect(evalShowWhen({ field: 'body_mode', in: ['json'] }, { body_mode: 'none' })).toBe(false);
    expect(evalShowWhen({ field: 'body_mode', equals: 'raw' }, { body_mode: 'raw' })).toBe(true);
    expect(evalShowWhen({ field: 'body_mode', equals: 'raw' }, { body_mode: 'json' })).toBe(false);
  });

  it('getVisiblePropertyKeys lists only visible keys in order', () => {
    const params = mergeParameterDefaults(httpLikeSchema, { body_mode: 'none' });
    expect(getVisiblePropertyKeys(httpLikeSchema, params)).toEqual(['body_mode', 'url']);
    const paramsJson = mergeParameterDefaults(httpLikeSchema, { body_mode: 'json' });
    expect(getVisiblePropertyKeys(httpLikeSchema, paramsJson)).toEqual(['body_mode', 'body_json', 'url']);
  });

  it('clearHiddenFieldsToDefaults resets hidden fields to schema defaults', () => {
    const params = mergeParameterDefaults(httpLikeSchema, {
      body_mode: 'json',
      body_json: '{"a":1}',
    });
    const cleared = clearHiddenFieldsToDefaults(httpLikeSchema, { ...params, body_mode: 'none' });
    expect(cleared.body_json).toBe('');
    expect(cleared.body_mode).toBe('none');
  });

  it('applyParameterPatch merges patch and clears hidden defaults', () => {
    const merged = mergeParameterDefaults(httpLikeSchema, {
      body_mode: 'json',
      body_json: 'hello',
    });
    const next = applyParameterPatch(httpLikeSchema, merged, { body_mode: 'none' });
    expect(next.body_mode).toBe('none');
    expect(next.body_json).toBe('');
  });

  it('mergeParameterDefaults fills missing keys from default keyword', () => {
    const m = mergeParameterDefaults(httpLikeSchema, {});
    expect(m.body_mode).toBe('none');
    expect(m.follow_redirects).toBeUndefined();
  });

  it('defaultFromSubschema uses type fallbacks without default keyword', () => {
    expect(defaultFromSubschema({ type: 'boolean' })).toBe(false);
    expect(defaultFromSubschema({ type: 'string' })).toBe('');
    expect(defaultFromSubschema({ type: 'array' })).toEqual([]);
  });
});
