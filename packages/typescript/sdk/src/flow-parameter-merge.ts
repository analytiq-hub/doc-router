/**
 * Merge JSON Schema `default` values into flow node parameters before persist/run.
 * Mirrors the editor UI (`mergeParameterDefaults` / `clearHiddenFieldsToDefaults`) so
 * untouched defaults are not saved as empty objects.
 */

export function getSchemaProperties(parameterSchema: unknown): Record<string, Record<string, unknown>> {
  const props = (parameterSchema as { properties?: unknown } | null | undefined)?.properties;
  if (!props || typeof props !== 'object') return {};
  return props as Record<string, Record<string, unknown>>;
}

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
  const sw = showWhen as { field?: string; equals?: unknown; in?: unknown[] };
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
  parameterSchema: unknown,
  params: Record<string, unknown>,
): boolean {
  const props = getSchemaProperties(parameterSchema);
  const sub = props[key];
  if (!sub) return false;
  return evalShowWhen(sub['x-ui-show-when'], params);
}

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

/**
 * Parameters as stored on the wire after applying schema defaults (for save / run snapshot).
 */
export function finalizePersistedFlowNodeParameters(
  parameterSchema: unknown | null | undefined,
  parameters: Record<string, unknown> | undefined | null,
): Record<string, unknown> {
  const params = { ...(parameters ?? {}) };
  if (parameterSchema == null) return params;
  return clearHiddenFieldsToDefaults(parameterSchema, mergeParameterDefaults(parameterSchema, params));
}
