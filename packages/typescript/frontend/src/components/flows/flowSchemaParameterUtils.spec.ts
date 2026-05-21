import { describe, expect, it } from 'vitest';
import {
  applyParameterPatch,
  clearHiddenFieldsToDefaults,
  companionUiPrimaryKey,
  defaultFromSubschema,
  evalShowWhen,
  getOrderedKeys,
  getVisiblePropertyKeys,
  isCompanionUiProperty,
  mergeParameterDefaults,
  parameterSchemaUsesCredentialAuthenticationWidget,
  resolveEnumSchemaForParams,
} from './flowSchemaParameterUtils';

const schema = {
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
    expect(getOrderedKeys(schema)).toEqual(['url', 'body_mode', 'body_json']);
  });

  it('resolveEnumSchemaForParams uses x-ui-enum-by', () => {
    const sub = {
      type: 'string',
      enum: ['a', 'b'],
      'x-ui-enum-by': {
        field: 'resource',
        variants: {
          file: { enum: ['upload'], 'x-ui-enum-names': ['Upload'] },
          folder: { enum: ['create'], 'x-ui-enum-names': ['Create'] },
        },
      },
    };
    expect(resolveEnumSchemaForParams(sub, { resource: 'file' }).enum).toEqual(['upload']);
    expect(resolveEnumSchemaForParams(sub, { resource: 'folder' }).enum).toEqual(['create']);
  });

  it('evalShowWhen handles all (AND)', () => {
    const sw = {
      all: [
        { field: 'resource', equals: 'file' },
        { field: 'operation', in: ['upload'] },
      ],
    };
    expect(evalShowWhen(sw, { resource: 'file', operation: 'upload' })).toBe(true);
    expect(evalShowWhen(sw, { resource: 'file', operation: 'download' })).toBe(false);
  });

  it('evalShowWhen handles in and equals', () => {
    expect(evalShowWhen({ field: 'body_mode', in: ['json'] }, { body_mode: 'json' })).toBe(true);
    expect(evalShowWhen({ field: 'body_mode', in: ['json'] }, { body_mode: 'none' })).toBe(false);
    expect(evalShowWhen({ field: 'body_mode', equals: 'raw' }, { body_mode: 'raw' })).toBe(true);
    expect(evalShowWhen({ field: 'body_mode', equals: 'raw' }, { body_mode: 'json' })).toBe(false);
  });

  it('getVisiblePropertyKeys lists only visible keys', () => {
    const params = mergeParameterDefaults(schema, { body_mode: 'none' });
    expect(getVisiblePropertyKeys(schema, params)).toEqual(['url', 'body_mode']);
    const paramsJson = mergeParameterDefaults(schema, { body_mode: 'json' });
    expect(getVisiblePropertyKeys(schema, paramsJson)).toEqual(['url', 'body_mode', 'body_json']);
  });

  it('clearHiddenFieldsToDefaults resets hidden fields to schema defaults', () => {
    const params = mergeParameterDefaults(schema, {
      body_mode: 'json',
      body_json: '{"a":1}',
    });
    const cleared = clearHiddenFieldsToDefaults(schema, { ...params, body_mode: 'none' });
    expect(cleared.body_json).toBe('');
    expect(cleared.body_mode).toBe('none');
  });

  it('applyParameterPatch merges patch and clears hidden defaults', () => {
    const merged = mergeParameterDefaults(schema, {
      body_mode: 'json',
      body_json: 'hello',
    });
    const next = applyParameterPatch(schema, merged, { body_mode: 'none' });
    expect(next.body_mode).toBe('none');
    expect(next.body_json).toBe('');
  });

  it('mergeParameterDefaults fills missing keys from default keyword', () => {
    const m = mergeParameterDefaults(schema, {});
    expect(m.body_mode).toBe('none');
    expect(m.follow_redirects).toBeUndefined();
  });

  it('defaultFromSubschema uses type fallbacks without default keyword', () => {
    expect(defaultFromSubschema({ type: 'boolean' })).toBe(false);
    expect(defaultFromSubschema({ type: 'string' })).toBe('');
    expect(defaultFromSubschema({ type: 'array' })).toEqual([]);
  });

  it('isCompanionUiProperty and companionUiPrimaryKey read x-ui-companion-of', () => {
    expect(isCompanionUiProperty(undefined)).toBe(false);
    expect(isCompanionUiProperty({ 'x-ui-companion-of': 'authentication' })).toBe(true);
    expect(companionUiPrimaryKey({ 'x-ui-companion-of': 'authentication' })).toBe('authentication');
  });

  it('parameterSchemaUsesCredentialAuthenticationWidget detects credential_authentication widget', () => {
    expect(parameterSchemaUsesCredentialAuthenticationWidget(null)).toBe(false);
    expect(
      parameterSchemaUsesCredentialAuthenticationWidget({
        properties: { authentication: { 'x-ui-widget': 'credential_authentication' } },
      }),
    ).toBe(true);
  });
});
