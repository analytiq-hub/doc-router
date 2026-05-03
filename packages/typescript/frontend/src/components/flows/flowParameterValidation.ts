/**
 * Parameter validation: AJV on expression-substituted payloads, plus frontend-only
 * `x-ui-regex` (URL-like literals) and row-level errors for name_value_list.
 * Conditional non-empty rules use JSON Schema (`minLength`, `allOf`/`if`/`then`).
 * @see docs/node_param_validation.md
 */
import Ajv, { type ErrorObject, type ValidateFunction } from 'ajv';
import { getOrderedKeys, getSchemaProperties, isPropertyVisible } from './flowSchemaParameterUtils';

const ajv = new Ajv({ allErrors: true, strict: false });

const EXPR_STRING_SENTINEL = '__EXPR__';

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

function sentinelForLeafSchema(sub: Record<string, unknown>): unknown {
  const t = sub.type;
  if (t === 'string') return EXPR_STRING_SENTINEL;
  if (t === 'number' || t === 'integer') return 0;
  if (t === 'boolean') return false;
  if (t === 'array') return [];
  if (t === 'object') return {};
  return EXPR_STRING_SENTINEL;
}

/** Replace expression strings with type-compatible sentinels so AJV can validate literals normally. */
export function substituteExpressionsForAjv(
  value: unknown,
  schemaFragment: Record<string, unknown> | undefined,
): unknown {
  if (schemaFragment == null || typeof schemaFragment !== 'object') {
    return value;
  }
  const sub = schemaFragment as Record<string, unknown>;
  if (isExpressionValue(value)) {
    return sentinelForLeafSchema(sub);
  }
  const t = sub.type;
  if (t === 'array' && Array.isArray(value) && sub.items) {
    return value.map((el) => substituteExpressionsForAjv(el, sub.items as Record<string, unknown>));
  }
  if (t === 'object' && value && typeof value === 'object' && !Array.isArray(value) && sub.properties) {
    const props = sub.properties as Record<string, unknown>;
    const obj = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(obj)) {
      out[k] = substituteExpressionsForAjv(obj[k], props[k] as Record<string, unknown> | undefined);
    }
    return out;
  }
  return value;
}

export function substituteRootParametersForAjv(
  mergedParams: Record<string, unknown>,
  rootSchema: Record<string, unknown>,
): Record<string, unknown> {
  const props = (rootSchema.properties || {}) as Record<string, Record<string, unknown>>;
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(mergedParams)) {
    const sub = props[key];
    out[key] = sub ? substituteExpressionsForAjv(mergedParams[key], sub) : mergedParams[key];
  }
  return out;
}

function requiredChildInstancePath(parentInstancePath: string, missingProperty: string): string {
  const base = parentInstancePath === '' || parentInstancePath === '/' ? '' : parentInstancePath;
  return `${base}/${missingProperty}`.replace(/\/{2,}/g, '/');
}

function matchListRow(instancePath: string): { field: string; row: number } | null {
  const p = instancePath.startsWith('/') ? instancePath : `/${instancePath}`;
  const m = p.match(/^\/([^/]+)\/(\d+)(?:\/|$)/);
  if (!m) return null;
  return { field: m[1], row: Number(m[2]) };
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
  errorsByField: Record<string, string>;
  /** name_value_list fields: row index → message */
  listRowErrorsByField: Record<string, Record<number, string>>;
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

function collectAjvErrors(
  validate: ValidateFunction,
  errorsByField: Record<string, string>,
  listRowErrorsByField: Record<string, Record<number, string>>,
): void {
  for (const err of validate.errors ?? []) {
    const msg = err.message ?? 'Invalid value';
    let pathForRow = err.instancePath ?? '';
    if (err.keyword === 'required') {
      const mp =
        err.params && typeof err.params === 'object' && 'missingProperty' in err.params
          ? (err.params as { missingProperty?: string }).missingProperty
          : undefined;
      if (typeof mp === 'string') {
        pathForRow = requiredChildInstancePath(err.instancePath ?? '', mp);
      }
    }
    const lr = matchListRow(pathForRow);
    if (lr) {
      if (!listRowErrorsByField[lr.field]) listRowErrorsByField[lr.field] = {};
      const rowMsg = `Row ${lr.row + 1}: ${msg}`;
      listRowErrorsByField[lr.field][lr.row] = rowMsg;
      if (!errorsByField[lr.field]) errorsByField[lr.field] = rowMsg;
    } else {
      const fk = fieldKeyForUi(err);
      if (fk && !errorsByField[fk]) errorsByField[fk] = msg;
    }
  }
}

function applyUiRegexExtensions(
  rootSchema: Record<string, unknown>,
  mergedParams: Record<string, unknown>,
  errorsByField: Record<string, string>,
): void {
  const schemaProps = getSchemaProperties(rootSchema);
  const orderedKeys = getOrderedKeys(rootSchema);
  for (const key of orderedKeys) {
    if (!isPropertyVisible(key, rootSchema, mergedParams)) continue;
    const sub = schemaProps[key];
    const v = mergedParams[key];

    const regexRaw = sub['x-ui-regex'];
    if (typeof regexRaw === 'string' && regexRaw.length > 0) {
      const msg =
        typeof sub['x-ui-regex-message'] === 'string'
          ? (sub['x-ui-regex-message'] as string)
          : 'Invalid format';
      if (typeof v === 'string' && !isExpressionValue(v)) {
        try {
          const re = new RegExp(regexRaw);
          if (!re.test(v) && !errorsByField[key]) {
            errorsByField[key] = msg;
          }
        } catch {
          /* ignore invalid regex */
        }
      }
    }
  }
}

function countListErrors(listRowErrorsByField: Record<string, Record<number, string>>): number {
  let n = 0;
  for (const k of Object.keys(listRowErrorsByField)) {
    n += Object.keys(listRowErrorsByField[k]).length;
  }
  return n;
}

/** Full validation used by the node parameter form. */
export function validateFlowParameters(
  validate: ValidateFunction | null,
  rootSchema: Record<string, unknown> | undefined,
  mergedParams: Record<string, unknown>,
): ParameterValidationResult {
  const errorsByField: Record<string, string> = {};
  const listRowErrorsByField: Record<string, Record<number, string>> = {};

  if (!rootSchema || typeof rootSchema !== 'object') {
    return { valid: true, errorsByField, listRowErrorsByField };
  }

  const subst = substituteRootParametersForAjv(mergedParams, rootSchema);

  if (validate) {
    const ok = validate(subst);
    if (!ok) {
      collectAjvErrors(validate, errorsByField, listRowErrorsByField);
    }
  }

  applyUiRegexExtensions(rootSchema, mergedParams, errorsByField);

  const valid =
    Object.keys(errorsByField).length === 0 && countListErrors(listRowErrorsByField) === 0;

  return { valid, errorsByField, listRowErrorsByField };
}
