/**
 * Pure helpers for JSON Schema–driven flow node parameters (`x-ui-*` vendor extensions)
 * and conditional visibility via JSON Schema `allOf` + `if` / `then`.
 * @see docs/flow_parameter_schema_ui_plan.md
 */

import Ajv, { type ValidateFunction } from 'ajv';

export type DocRouterShowWhen = {
  field: string;
  in?: unknown[];
  equals?: unknown;
};

const ifAjv = new Ajv({ strict: false, allErrors: false });
const ifValidatorCache = new Map<string, ValidateFunction>();

export function getSchemaProperties(parameterSchema: unknown): Record<string, Record<string, unknown>> {
  const props = (parameterSchema as { properties?: unknown } | null | undefined)?.properties;
  if (!props || typeof props !== 'object') return {};
  return props as Record<string, Record<string, unknown>>;
}

/** Default value for a property when the schema defines one, else type-appropriate fallbacks. */
export function defaultFromSubschema(sub: Record<string, unknown>): unknown {
  if (Object.prototype.hasOwnProperty.call(sub, 'default') && sub.default !== undefined) {
    return sub.default;
  }
  const t = sub.type;
  if (t === 'boolean') return false;
  if (t === 'string') return '';
  if (t === 'number' || t === 'integer') return 0;
  if (t === 'array') return [];
  if (t === 'object') return {};
  return null;
}

export function evalShowWhen(showWhen: unknown, params: Record<string, unknown>): boolean {
  if (showWhen == null || showWhen === false) return true;
  if (typeof showWhen !== 'object') return true;
  const sw = showWhen as DocRouterShowWhen;
  if (!sw.field || typeof sw.field !== 'string') return true;
  const raw = params[sw.field];
  if (Object.prototype.hasOwnProperty.call(sw, 'equals')) {
    return raw === sw.equals;
  }
  if (Array.isArray(sw.in)) {
    return sw.in.includes(raw);
  }
  return true;
}

/**
 * `if` subschemas from root `allOf` entries whose `then.properties` includes `propertyKey`.
 * Visibility is true if any of these `if` schemas validate against the full parameter object.
 */
export function getIfBranchesForPropertyKey(
  rootSchema: Record<string, unknown>,
  propertyKey: string,
): Record<string, unknown>[] {
  const allOf = rootSchema.allOf;
  if (!Array.isArray(allOf)) return [];
  const out: Record<string, unknown>[] = [];
  for (const raw of allOf) {
    if (!raw || typeof raw !== 'object') continue;
    const item = raw as { if?: unknown; then?: unknown };
    const thenProps = (item.then as { properties?: Record<string, unknown> } | undefined)?.properties;
    if (!thenProps || !Object.prototype.hasOwnProperty.call(thenProps, propertyKey)) continue;
    if (item.if && typeof item.if === 'object') {
      out.push(item.if as Record<string, unknown>);
    }
  }
  return out;
}

/** Validate full parameter object against an `if` fragment (Draft 7 style object). */
export function instanceMatchesIfSchema(ifSchema: Record<string, unknown>, params: Record<string, unknown>): boolean {
  let key: string;
  try {
    key = JSON.stringify(ifSchema);
  } catch {
    key = '__bad__';
  }
  let validate = ifValidatorCache.get(key);
  if (!validate) {
    const wrapped: Record<string, unknown> =
      ifSchema.type === 'object' ? { ...ifSchema } : { type: 'object', ...ifSchema };
    try {
      validate = ifAjv.compile(wrapped);
    } catch {
      return false;
    }
    ifValidatorCache.set(key, validate);
  }
  return Boolean(validate(params));
}

/**
 * A property is visible if:
 * - it appears in root `properties`, and
 * - either there is no `allOf` branch targeting it via `then.properties[key]`, **or**
 *   at least one such branch's `if` validates against `params`, **or** (legacy)
 *   `x-ui-show-when` passes when no `if`/`then` branches apply.
 */
export function isPropertyVisible(
  key: string,
  parameterSchema: unknown,
  params: Record<string, unknown>,
): boolean {
  const props = getSchemaProperties(parameterSchema);
  const sub = props[key];
  if (!sub) return false;

  const root = parameterSchema as Record<string, unknown>;
  const branches = getIfBranchesForPropertyKey(root, key);
  if (branches.length > 0) {
    return branches.some((ifSch) => instanceMatchesIfSchema(ifSch, params));
  }
  return evalShowWhen(sub['x-ui-show-when'], params);
}

/**
 * Property keys in schema iteration order. Matches declaration order in hand-authored Python dicts
 * (insertion order) and JSON `properties` key order from the API — no separate order list is used.
 */
export function getOrderedKeys(parameterSchema: unknown): string[] {
  const props = getSchemaProperties(parameterSchema);
  return Object.keys(props);
}

/**
 * Keys whose visibility passes for the given parameter snapshot.
 */
export function getVisiblePropertyKeys(parameterSchema: unknown, params: Record<string, unknown>): string[] {
  return getOrderedKeys(parameterSchema).filter((k) => isPropertyVisible(k, parameterSchema, params));
}

/**
 * Sets values for properties that are not visible to their schema defaults (hidden fields cleared).
 */
export function clearHiddenFieldsToDefaults(
  parameterSchema: unknown,
  params: Record<string, unknown>,
): Record<string, unknown> {
  const props = getSchemaProperties(parameterSchema);
  const out = { ...params };
  for (const k of Object.keys(props)) {
    if (!isPropertyVisible(k, parameterSchema, out)) {
      out[k] = defaultFromSubschema(props[k]);
    }
  }
  return out;
}

/** Fill missing keys from schema defaults so booleans and enums display correctly before first edit. */
export function mergeParameterDefaults(
  parameterSchema: unknown,
  params: Record<string, unknown>,
): Record<string, unknown> {
  const props = getSchemaProperties(parameterSchema);
  const out = { ...params };
  for (const key of Object.keys(props)) {
    if (out[key] === undefined) {
      out[key] = defaultFromSubschema(props[key]);
    }
  }
  return out;
}

export function applyParameterPatch(
  parameterSchema: unknown,
  currentMerged: Record<string, unknown>,
  patch: Record<string, unknown>,
): Record<string, unknown> {
  const next = { ...currentMerged, ...patch };
  return clearHiddenFieldsToDefaults(parameterSchema, next);
}
