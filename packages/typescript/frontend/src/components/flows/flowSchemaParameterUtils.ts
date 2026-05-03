/**
 * Pure helpers for JSON Schema–driven flow node parameters (`x-docrouter-*` extensions).
 * @see docs/flow_parameter_schema_ui_plan.md
 */

export type DocRouterShowWhen = {
  field: string;
  in?: unknown[];
  equals?: unknown;
};

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

export function isPropertyVisible(
  key: string,
  schemaProps: Record<string, Record<string, unknown>>,
  params: Record<string, unknown>,
): boolean {
  const sub = schemaProps[key];
  if (!sub) return false;
  return evalShowWhen(sub['x-docrouter-showWhen'], params);
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
 * Keys whose `x-docrouter-showWhen` passes for the given parameter snapshot.
 * Uses the same visibility rules as the form renderer.
 */
export function getVisiblePropertyKeys(parameterSchema: unknown, params: Record<string, unknown>): string[] {
  const props = getSchemaProperties(parameterSchema);
  return getOrderedKeys(parameterSchema).filter((k) => isPropertyVisible(k, props, params));
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
    if (!isPropertyVisible(k, props, out)) {
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
