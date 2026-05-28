/**
 * Pure helpers for JSON Schema–driven flow node parameters (`x-ui-*` vendor extensions)
 * and conditional visibility via `x-ui-show-when`.
 * @see docs/flow_parameter_schema_ui_plan.md
 */

export type DocRouterShowWhen = {
  field?: string;
  in?: unknown[];
  /** Alias for ``in`` — value must appear in the list. */
  oneOf?: unknown[];
  equals?: unknown;
  /** All clauses must pass (maps multi-field upstream ``displayOptions.show``). */
  all?: DocRouterShowWhen[];
};

/** Resource-dependent enum options (integration nodes with per-resource ``operation`` blocks). */
export type DocRouterEnumBy = {
  field: string;
  variants: Record<string, { enum?: unknown[]; 'x-ui-enum-names'?: unknown[] }>;
};

function hasEnumLikeSchema(sub: Record<string, unknown>): boolean {
  if (Array.isArray(sub.enum) && sub.enum.length > 0) return true;
  const eb = sub['x-ui-enum-by'] as DocRouterEnumBy | undefined;
  return Boolean(eb?.variants);
}

/** Coerce invalid / empty enum values to a schema default or first allowed option. */
export function coerceEnumParameterValue(
  sub: Record<string, unknown>,
  params: Record<string, unknown>,
  raw: unknown,
): unknown {
  const resolved = resolveEnumSchemaForParams(sub, params);
  const allowed = resolved.enum?.map(String) ?? [];
  if (allowed.length === 0) return raw;
  const current = raw === undefined || raw === null ? '' : String(raw);
  if (!current || !allowed.includes(current)) {
    const def = sub.default;
    if (def !== undefined && allowed.includes(String(def))) return def;
    return allowed[0];
  }
  return raw;
}

export function normalizeEnumParameters(
  parameterSchema: unknown,
  params: Record<string, unknown>,
): Record<string, unknown> {
  const props = getSchemaProperties(parameterSchema);
  const out = { ...params };
  for (const key of Object.keys(props)) {
    const sub = props[key];
    if (!hasEnumLikeSchema(sub)) continue;
    out[key] = coerceEnumParameterValue(sub, out, out[key]);
  }
  return out;
}

export function resolveEnumSchemaForParams(
  subschema: Record<string, unknown>,
  params: Record<string, unknown>,
): { enum?: unknown[]; 'x-ui-enum-names'?: unknown[] } {
  const base = {
    enum: subschema.enum as unknown[] | undefined,
    'x-ui-enum-names': subschema['x-ui-enum-names'] as unknown[] | undefined,
  };
  const eb = subschema['x-ui-enum-by'] as DocRouterEnumBy | undefined;
  if (!eb?.field || !eb.variants || typeof eb.variants !== 'object') {
    return base;
  }
  const key = String(params[eb.field] ?? '');
  const variant = eb.variants[key];
  if (!variant?.enum || !Array.isArray(variant.enum)) {
    return base;
  }
  return {
    enum: variant.enum,
    'x-ui-enum-names': variant['x-ui-enum-names'] as unknown[] | undefined,
  };
}

export function isObjectFieldsWidget(sub: Record<string, unknown> | undefined): boolean {
  if (!sub) return false;
  return sub['x-ui-widget'] === 'object_fields' && sub.type === 'object';
}

export function isCollectionFieldsWidget(sub: Record<string, unknown> | undefined): boolean {
  if (!sub) return false;
  return sub['x-ui-widget'] === 'collection_fields' && sub.type === 'object';
}

/** Merge defaults only for keys already present (optional collection fields). */
export function mergeCollectionFieldDefaults(
  subschema: Record<string, unknown>,
  raw: unknown,
): Record<string, unknown> {
  const props = subschema.properties as Record<string, Record<string, unknown>> | undefined;
  if (!props || typeof props !== 'object') {
    return typeof raw === 'object' && raw !== null && !Array.isArray(raw)
      ? { ...(raw as Record<string, unknown>) }
      : {};
  }
  const out =
    typeof raw === 'object' && raw !== null && !Array.isArray(raw)
      ? { ...(raw as Record<string, unknown>) }
      : {};
  for (const [sk, ss] of Object.entries(props)) {
    if (!Object.prototype.hasOwnProperty.call(out, sk)) continue;
    if (out[sk] === undefined) {
      out[sk] = defaultFromSubschema(ss);
    } else if (
      out[sk] === '' &&
      (Array.isArray(ss.enum) || ss['x-ui-enum-by'])
    ) {
      out[sk] = defaultFromSubschema(ss);
    }
  }
  return out;
}

export function defaultCollectionFieldValue(subschema: Record<string, unknown>): Record<string, unknown> {
  const base = defaultFromSubschema(subschema);
  if (typeof base === 'object' && base !== null && !Array.isArray(base)) {
    return { ...(base as Record<string, unknown>) };
  }
  return {};
}

/** Merge nested ``properties`` defaults for ``x-ui-widget: object_fields`` objects. */
export function mergeObjectFieldDefaults(
  subschema: Record<string, unknown>,
  raw: unknown,
): Record<string, unknown> {
  const props = subschema.properties as Record<string, Record<string, unknown>> | undefined;
  if (!props || typeof props !== 'object') {
    return typeof raw === 'object' && raw !== null && !Array.isArray(raw)
      ? { ...(raw as Record<string, unknown>) }
      : {};
  }
  const out =
    typeof raw === 'object' && raw !== null && !Array.isArray(raw)
      ? { ...(raw as Record<string, unknown>) }
      : {};
  for (const [sk, ss] of Object.entries(props)) {
    if (out[sk] === undefined) {
      out[sk] = defaultFromSubschema(ss);
    } else if (
      out[sk] === '' &&
      (Array.isArray(ss.enum) || ss['x-ui-enum-by'])
    ) {
      out[sk] = defaultFromSubschema(ss);
    }
  }
  return out;
}

export function defaultObjectFieldValue(subschema: Record<string, unknown>): Record<string, unknown> {
  const base = defaultFromSubschema(subschema);
  return mergeObjectFieldDefaults(subschema, base);
}

/** Renders only inside the composite widget for the named primary property (see ``x-ui-widget: credential_authentication``). */
export const UI_COMPANION_OF = 'x-ui-companion-of';

export function isCompanionUiProperty(sub: Record<string, unknown> | undefined): boolean {
  if (!sub) return false;
  const v = sub[UI_COMPANION_OF];
  return typeof v === 'string' && v.trim().length > 0;
}

/** Primary property key this companion row belongs to. */
export function companionUiPrimaryKey(sub: Record<string, unknown> | undefined): string | null {
  if (!sub) return null;
  const v = sub[UI_COMPANION_OF];
  return typeof v === 'string' && v.trim().length > 0 ? v.trim() : null;
}

/** Node exposes ``credential_authentication`` widget — suppress default per-slot credential panel below parameters. */
export function parameterSchemaUsesCredentialAuthenticationWidget(parameterSchema: unknown): boolean {
  const props = getSchemaProperties(parameterSchema);
  for (const k of Object.keys(props)) {
    if (props[k]?.['x-ui-widget'] === 'credential_authentication') return true;
  }
  return false;
}

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
  if (Array.isArray(sw.all) && sw.all.length > 0) {
    return sw.all.every((clause) => evalShowWhen(clause, params));
  }
  if (!sw.field || typeof sw.field !== 'string') return true;
  const raw = params[sw.field];
  if (Object.prototype.hasOwnProperty.call(sw, 'equals')) {
    return raw === sw.equals;
  }
  if (Array.isArray(sw.in)) {
    return sw.in.includes(raw);
  }
  if (Array.isArray(sw.oneOf)) {
    return sw.oneOf.includes(raw);
  }
  return true;
}

function evalShowWhenAny(clauses: unknown, params: Record<string, unknown>): boolean {
  if (!Array.isArray(clauses) || clauses.length === 0) return true;
  return clauses.some((clause) => evalShowWhen(clause, params));
}

/** A property is visible if it appears in root `properties` and its `x-ui-show-when` passes. */
export function isPropertyVisible(
  key: string,
  parameterSchema: unknown,
  params: Record<string, unknown>,
): boolean {
  const props = getSchemaProperties(parameterSchema);
  const sub = props[key];
  if (!sub) return false;
  if (Object.prototype.hasOwnProperty.call(sub, 'x-ui-show-when-any')) {
    return evalShowWhenAny(sub['x-ui-show-when-any'], params);
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
      out[k] = isObjectFieldsWidget(props[k])
        ? defaultObjectFieldValue(props[k])
        : isCollectionFieldsWidget(props[k])
          ? defaultCollectionFieldValue(props[k])
          : defaultFromSubschema(props[k]);
    } else if (isObjectFieldsWidget(props[k])) {
      out[k] = mergeObjectFieldDefaults(props[k], out[k]);
    } else if (isCollectionFieldsWidget(props[k])) {
      out[k] = mergeCollectionFieldDefaults(props[k], out[k]);
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
    } else if (
      props[key].type === 'object' &&
      out[key] !== null &&
      typeof out[key] === 'object' &&
      !Array.isArray(out[key]) &&
      Object.keys(out[key] as object).length === 0 &&
      props[key].default !== undefined &&
      typeof props[key].default === 'object' &&
      !Array.isArray(props[key].default)
    ) {
      out[key] = { ...(props[key].default as Record<string, unknown>) };
    } else if (
      out[key] === '' &&
      (Array.isArray(props[key].enum) || props[key]['x-ui-enum-by'])
    ) {
      out[key] = defaultFromSubschema(props[key]);
    } else if (isObjectFieldsWidget(props[key])) {
      out[key] = mergeObjectFieldDefaults(props[key], out[key]);
    } else if (isCollectionFieldsWidget(props[key])) {
      out[key] = mergeCollectionFieldDefaults(props[key], out[key]);
    }
  }
  return normalizeEnumParameters(parameterSchema, out);
}

export function applyParameterPatch(
  parameterSchema: unknown,
  currentMerged: Record<string, unknown>,
  patch: Record<string, unknown>,
): Record<string, unknown> {
  const next = normalizeEnumParameters(parameterSchema, { ...currentMerged, ...patch });
  return clearHiddenFieldsToDefaults(parameterSchema, next);
}
