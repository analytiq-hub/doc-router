import { describe, expect, it } from 'vitest';
import {
  applyParameterPatch,
  clearHiddenFieldsToDefaults,
  defaultFromSubschema,
  evalShowWhen,
  getOrderedKeys,
  getVisiblePropertyKeys,
  mergeParameterDefaults,
  instanceMatchesIfSchema,
} from './flowSchemaParameterUtils';

/** Same ordering as before — visibility via `allOf` / `if` / `then` (HTTP-style). */
const httpLikeSchema = {
  type: 'object',
  additionalProperties: false,
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
    },
  },
  allOf: [
    {
      if: { properties: { body_mode: { enum: ['json'] } } },
      then: { properties: { body_json: {} } },
    },
  ],
};

/** Legacy port-style schema still using `x-ui-show-when`. */
const legacyShowWhenSchema = {
  type: 'object',
  additionalProperties: false,
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
      'x-ui-show-when': { field: 'body_mode', in: ['json'] },
    },
  },
};

describe('flowSchemaParameterUtils', () => {
  it('getOrderedKeys follows properties declaration order', () => {
    expect(getOrderedKeys(httpLikeSchema)).toEqual(['url', 'body_mode', 'body_json']);
  });

  it('evalShowWhen handles in and equals', () => {
    expect(evalShowWhen({ field: 'body_mode', in: ['json'] }, { body_mode: 'json' })).toBe(true);
    expect(evalShowWhen({ field: 'body_mode', in: ['json'] }, { body_mode: 'none' })).toBe(false);
    expect(evalShowWhen({ field: 'body_mode', equals: 'raw' }, { body_mode: 'raw' })).toBe(true);
    expect(evalShowWhen({ field: 'body_mode', equals: 'raw' }, { body_mode: 'json' })).toBe(false);
  });

  it('instanceMatchesIfSchema validates full params against if fragment', () => {
    expect(
      instanceMatchesIfSchema({ properties: { body_mode: { enum: ['json'] } } }, { body_mode: 'json' }),
    ).toBe(true);
    expect(
      instanceMatchesIfSchema({ properties: { body_mode: { enum: ['json'] } } }, { body_mode: 'none' }),
    ).toBe(false);
  });

  it('getVisiblePropertyKeys lists only visible keys (JSON Schema allOf if/then)', () => {
    const params = mergeParameterDefaults(httpLikeSchema, { body_mode: 'none' });
    expect(getVisiblePropertyKeys(httpLikeSchema, params)).toEqual(['url', 'body_mode']);
    const paramsJson = mergeParameterDefaults(httpLikeSchema, { body_mode: 'json' });
    expect(getVisiblePropertyKeys(httpLikeSchema, paramsJson)).toEqual(['url', 'body_mode', 'body_json']);
  });

  it('getVisiblePropertyKeys lists only visible keys (legacy x-ui-show-when)', () => {
    const params = mergeParameterDefaults(legacyShowWhenSchema, { body_mode: 'none' });
    expect(getVisiblePropertyKeys(legacyShowWhenSchema, params)).toEqual(['url', 'body_mode']);
    const paramsJson = mergeParameterDefaults(legacyShowWhenSchema, { body_mode: 'json' });
    expect(getVisiblePropertyKeys(legacyShowWhenSchema, paramsJson)).toEqual(['url', 'body_mode', 'body_json']);
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
