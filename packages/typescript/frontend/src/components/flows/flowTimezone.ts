/** Sentinel for “use browser timezone” in the settings UI (persisted as IANA on save). */
export const FLOW_TIMEZONE_DEFAULT = 'DEFAULT';

export type FlowTimezoneOption = {
  key: string;
  label: string;
};

/** IANA timezone for the current browser (falls back to UTC). */
export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

function formatUtcOffsetMinutes(tz: string, at: Date = new Date()): string {
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      timeZoneName: 'shortOffset',
    }).formatToParts(at);
    const name = parts.find((p) => p.type === 'timeZoneName')?.value;
    if (name && name !== 'GMT') return name.replace('GMT', 'UTC');
  } catch {
    // ignore
  }
  return 'UTC';
}

/** Human-readable label for an IANA timezone (or ``DEFAULT``). */
export function flowTimezoneLabel(tz: string, browserDefault = browserTimezone()): string {
  const token = tz.trim();
  if (!token || token === FLOW_TIMEZONE_DEFAULT) {
    const resolved = browserDefault.trim() || 'UTC';
    return `Default — ${flowTimezoneLabel(resolved, resolved)}`;
  }
  try {
    const offset = formatUtcOffsetMinutes(token);
    const city = token.split('/').pop()?.replace(/_/g, ' ') ?? token;
    return `${city} (${offset})`;
  } catch {
    return token;
  }
}

/** Resolve stored setting to an IANA timezone name (browser default when unset). */
export function resolveFlowTimezone(
  settings: { timezone?: unknown } | null | undefined,
  browserDefault = browserTimezone(),
): string {
  const raw = settings?.timezone;
  const token = typeof raw === 'string' ? raw.trim() : '';
  if (!token || token === FLOW_TIMEZONE_DEFAULT) {
    return browserDefault.trim() || 'UTC';
  }
  return token;
}

/** Value for the settings picker (``DEFAULT`` when unset or matching browser). */
export function storedFlowTimezone(
  settings: { timezone?: unknown } | null | undefined,
  browserDefault = browserTimezone(),
): string {
  const resolved = resolveFlowTimezone(settings, browserDefault);
  if (resolved === browserDefault) return FLOW_TIMEZONE_DEFAULT;
  return resolved;
}

/** Persist concrete IANA timezone (browser default when unset or ``DEFAULT``). */
export function normalizeFlowSettingsForSave(
  settings: Record<string, unknown> | null | undefined,
  browserDefault = browserTimezone(),
): Record<string, unknown> {
  const base = { ...(settings || {}) };
  const raw = base.timezone;
  const token = typeof raw === 'string' ? raw.trim() : '';
  if (!token || token === FLOW_TIMEZONE_DEFAULT) {
    base.timezone = browserDefault.trim() || 'UTC';
  }
  return base;
}

let cachedTimezoneKeys: string[] | null = null;

export function listIanaTimezones(): string[] {
  if (cachedTimezoneKeys) return cachedTimezoneKeys;
  try {
    cachedTimezoneKeys = Intl.supportedValuesOf('timeZone').slice().sort((a, b) => a.localeCompare(b));
    return cachedTimezoneKeys;
  } catch {
    cachedTimezoneKeys = ['UTC'];
    return cachedTimezoneKeys;
  }
}

export function buildFlowTimezoneOptions(browserDefault = browserTimezone()): FlowTimezoneOption[] {
  const options: FlowTimezoneOption[] = [
    {
      key: FLOW_TIMEZONE_DEFAULT,
      label: flowTimezoneLabel(FLOW_TIMEZONE_DEFAULT, browserDefault),
    },
  ];
  for (const key of listIanaTimezones()) {
    options.push({ key, label: flowTimezoneLabel(key, browserDefault) });
  }
  return options;
}

export function filterFlowTimezoneOptions(
  options: FlowTimezoneOption[],
  query: string,
): FlowTimezoneOption[] {
  const q = query.trim().toLowerCase();
  if (!q) return options;
  return options.filter((o) => o.key.toLowerCase().includes(q) || o.label.toLowerCase().includes(q));
}

/** Stored timezone to persist after the settings modal saves. */
export function flowTimezoneForPersist(draft: string, browserDefault = browserTimezone()): string {
  const token = draft.trim();
  if (!token || token === FLOW_TIMEZONE_DEFAULT) {
    return browserDefault.trim() || 'UTC';
  }
  return token;
}
