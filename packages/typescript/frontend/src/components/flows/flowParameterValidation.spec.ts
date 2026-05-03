import { describe, expect, it } from 'vitest';
import {
  compileParameterValidator,
  getValueAtInstancePath,
  isExpressionValue,
  substituteRootParametersForAjv,
  validateFlowParameters,
} from './flowParameterValidation';

describe('flowParameterValidation', () => {
  it('detects expression strings', () => {
    expect(isExpressionValue('=foo')).toBe(true);
    expect(isExpressionValue('GET')).toBe(false);
    expect(isExpressionValue('')).toBe(false);
  });

  it('resolves instance paths', () => {
    const data = { a: [{ b: 'x' }] };
    expect(getValueAtInstancePath(data, '/a/0/b')).toBe('x');
    expect(getValueAtInstancePath(data, '')).toBe(data);
  });

  it('substitutes expressions before AJV', () => {
    const rootSchema = {
      type: 'object',
      properties: {
        url: { type: 'string', minLength: 1 },
        timeout_seconds: { type: 'number', minimum: 1 },
      },
    };
    const subst = substituteRootParametersForAjv(
      { url: '=$json.url', timeout_seconds: 0 },
      rootSchema as Record<string, unknown>,
    );
    expect(subst.url).toBe('__EXPR__');
    expect(subst.timeout_seconds).toBe(0);
  });

  it('maps timeout_seconds violation after substitution', () => {
    const schema = {
      type: 'object',
      additionalProperties: false,
      properties: {
        url: { type: 'string', minLength: 1, default: '' },
        timeout_seconds: { type: 'number', minimum: 1, default: 30 },
      },
    };
    const validate = compileParameterValidator(schema);
    const r = validateFlowParameters(validate, schema, {
      url: '=$json.url',
      timeout_seconds: 0,
    });
    expect(r.errorsByField.timeout_seconds).toBeDefined();
    expect(r.errorsByField.url).toBeUndefined();
    expect(r.valid).toBe(false);
  });

  it('applies x-ui-regex when value is not an expression', () => {
    const schema = {
      type: 'object',
      properties: {
        url: {
          type: 'string',
          minLength: 1,
          'x-ui-regex': '^https?://\\S+$',
          'x-ui-regex-message': 'Must be HTTP/S',
        },
      },
    };
    const validate = compileParameterValidator(schema);
    const bad = validateFlowParameters(validate, schema as Record<string, unknown>, {
      url: 'not-a-url',
    });
    expect(bad.errorsByField.url).toBe('Must be HTTP/S');
    const okExpr = validateFlowParameters(validate, schema as Record<string, unknown>, {
      url: '=$json.x',
    });
    expect(okExpr.errorsByField.url).toBeUndefined();
    const okLit = validateFlowParameters(validate, schema as Record<string, unknown>, {
      url: 'https://a.b',
    });
    expect(okLit.errorsByField.url).toBeUndefined();
  });

  it('applies x-ui-require-when for visible empty strings', () => {
    const schema = {
      type: 'object',
      properties: {
        body_mode: { type: 'string', default: 'none' },
        body_json: {
          type: 'string',
          default: '',
          'x-ui-show-when': { field: 'body_mode', in: ['json'] },
          'x-ui-require-when': { field: 'body_mode', in: ['json'] },
          'x-ui-require-message': 'Need JSON',
        },
      },
    };
    const validate = compileParameterValidator(schema);
    const bad = validateFlowParameters(validate, schema as Record<string, unknown>, {
      body_mode: 'json',
      body_json: '',
    });
    expect(bad.errorsByField.body_json).toBe('Need JSON');
    const okHidden = validateFlowParameters(validate, schema as Record<string, unknown>, {
      body_mode: 'none',
      body_json: '',
    });
    expect(okHidden.errorsByField.body_json).toBeUndefined();
  });

  it('maps nested list item errors to row keys', () => {
    const schema = {
      type: 'object',
      properties: {
        query_params: {
          type: 'array',
          items: {
            type: 'object',
            required: ['name', 'value'],
            properties: {
              name: { type: 'string' },
              value: { type: 'string' },
            },
            additionalProperties: false,
          },
        },
      },
    };
    const validate = compileParameterValidator(schema);
    const r = validateFlowParameters(validate, schema as Record<string, unknown>, {
      query_params: [{ name: 'a' }],
    });
    expect(r.listRowErrorsByField.query_params?.[0]).toMatch(/Row 1:/);
    expect(r.errorsByField.query_params).toMatch(/Row 1:/);
    expect(r.valid).toBe(false);
  });
});
