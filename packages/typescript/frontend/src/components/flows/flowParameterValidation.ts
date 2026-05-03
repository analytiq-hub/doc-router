/**
 * AJV validation for flow node `parameters` against `parameter_schema`.
 * @see docs/node_param_validation.md
 */
import Ajv, { type ErrorObject, type ValidateFunction } from 'ajv';

const ajv = new Ajv({ allErrors: true, strict: false });

export function isExpressionValue(value: unknown): boolean {
  return typeof value === 'string' && value.startsWith('=');
}

/** Traverse JSON instance pointer (`/a/0/b`) per AJV `instancePath`. */
export function getValueAtInstancePath(data: unknown, instancePath: string): unknown {
  if (instancePath === '' || instancePath === '/') return data;
  const segments = instancePath.replace(/^\//, '').split('/').filter(Boolean);
  let cur: unknown = data;
  for (const seg of segments) {
    if (cur == null) return undefined;
    if (Array.isArray(cur)) {
      const i = Number(seg);
      if (!Number.isFinite(i)) return undefined;
      cur = cur[i];
    } else if (typeof cur === 'object') {
      cur = (cur as Record<string, unknown>)[seg];
    } else {
      return undefined;
    }
  }
  return cur;
}

function errorTouchesExpressionValue(err: ErrorObject, rootData: Record<string, unknown>): boolean {
  if (err.keyword === 'required') {
    return false;
  }
  const v = getValueAtInstancePath(rootData, err.instancePath ?? '');
  return isExpressionValue(v);
}

function fieldKeyForUi(err: ErrorObject): string | null {
  if (err.keyword === 'required') {
    const mp =
      err.params && typeof err.params === 'object' && 'missingProperty' in err.params
        ? (err.params as { missingProperty?: string }).missingProperty
        : undefined;
    if (typeof mp !== 'string') return null;
    const parent = err.instancePath ?? '';
    if (parent === '' || parent === '/') return mp;
    const segments = parent.replace(/^\//, '').split('/').filter(Boolean);
    return segments[0] ?? mp;
  }
  const segments = (err.instancePath ?? '').replace(/^\//, '').split('/').filter(Boolean);
  return segments[0] ?? null;
}

export type ParameterValidationResult = {
  valid: boolean;
  /** First message per top-level schema property key (for inline UI). */
  errorsByField: Record<string, string>;
};

export function compileParameterValidator(
  parameterSchema: Record<string, unknown> | null | undefined,
): ValidateFunction | null {
  if (!parameterSchema || typeof parameterSchema !== 'object') return null;
  try {
    return ajv.compile(parameterSchema);
  } catch {
    return null;
  }
}

export function validateMergedParametersWithValidator(
  validate: ValidateFunction | null,
  mergedParams: Record<string, unknown>,
): ParameterValidationResult {
  if (!validate) {
    return { valid: true, errorsByField: {} };
  }
  const ok = validate(mergedParams);
  if (ok || !validate.errors?.length) {
    return { valid: true, errorsByField: {} };
  }

  const errorsByField: Record<string, string> = {};
  for (const err of validate.errors) {
    if (errorTouchesExpressionValue(err, mergedParams)) continue;
    const key = fieldKeyForUi(err);
    if (!key) continue;
    if (errorsByField[key]) continue;
    errorsByField[key] = err.message ?? 'Invalid value';
  }
  return { valid: false, errorsByField };
}

/** One-shot validate (prefer compiled validator + {@link validateMergedParametersWithValidator} in UI). */
export function validateMergedParameters(
  parameterSchema: Record<string, unknown> | null | undefined,
  mergedParams: Record<string, unknown>,
): ParameterValidationResult {
  return validateMergedParametersWithValidator(compileParameterValidator(parameterSchema), mergedParams);
}
