import { describe, expect, it } from 'vitest';
import {
  compileParameterValidator,
  getValueAtInstancePath,
  isExpressionValue,
  validateMergedParametersWithValidator,
} from './flowParameterValidation';

describe('flowParameterValidation', () => {
  it('detects expression strings', () => {
    expect(isExpressionValue('=foo')).toBe(true);
    expect(isExpressionValue('=GET')).toBe(true);
    expect(isExpressionValue('GET')).toBe(false);
    expect(isExpressionValue('')).toBe(false);
  });

  it('resolves instance paths', () => {
    const data = { a: [{ b: 'x' }] };
    expect(getValueAtInstancePath(data, '/a/0/b')).toBe('x');
    expect(getValueAtInstancePath(data, '')).toBe(data);
  });

  it('maps timeout_seconds violation to field key', () => {
    const schema = {
      type: 'object',
      additionalProperties: false,
      properties: {
        timeout_seconds: { type: 'number', minimum: 1, default: 30 },
      },
    };
    const validate = compileParameterValidator(schema);
    const r = validateMergedParametersWithValidator(validate, { timeout_seconds: 0 });
    expect(r.valid).toBe(false);
    expect(r.errorsByField.timeout_seconds).toBeDefined();
  });

  it('skips validation errors for expression-valued fields', () => {
    const schema = {
      type: 'object',
      additionalProperties: false,
      required: ['url'],
      properties: {
        url: { type: 'string', default: '' },
        timeout_seconds: { type: 'number', minimum: 1, default: 30 },
      },
    };
    const validate = compileParameterValidator(schema);
    const r = validateMergedParametersWithValidator(validate, {
      url: '=$json.url',
      timeout_seconds: 0,
    });
    expect(r.errorsByField.url).toBeUndefined();
    expect(r.errorsByField.timeout_seconds).toBeDefined();
  });
});
