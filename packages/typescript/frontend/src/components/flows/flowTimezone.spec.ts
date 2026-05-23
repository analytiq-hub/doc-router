import { describe, expect, it } from 'vitest';
import {
  FLOW_TIMEZONE_DEFAULT,
  flowTimezoneForPersist,
  flowTimezoneLabel,
  normalizeFlowSettingsForSave,
  resolveFlowTimezone,
  storedFlowTimezone,
} from './flowTimezone';

const BROWSER_TZ = 'America/Los_Angeles';

describe('flowTimezone', () => {
  it('resolves DEFAULT to browser timezone', () => {
    expect(resolveFlowTimezone({}, BROWSER_TZ)).toBe(BROWSER_TZ);
    expect(resolveFlowTimezone({ timezone: FLOW_TIMEZONE_DEFAULT }, BROWSER_TZ)).toBe(BROWSER_TZ);
  });

  it('resolves explicit IANA timezone', () => {
    expect(resolveFlowTimezone({ timezone: 'America/Chicago' }, BROWSER_TZ)).toBe('America/Chicago');
  });

  it('formats DEFAULT label with browser timezone', () => {
    expect(flowTimezoneLabel(FLOW_TIMEZONE_DEFAULT, BROWSER_TZ)).toContain('Default');
    expect(flowTimezoneLabel(FLOW_TIMEZONE_DEFAULT, BROWSER_TZ)).toContain('Los Angeles');
  });

  it('storedFlowTimezone falls back to DEFAULT when unset or browser-matched', () => {
    expect(storedFlowTimezone({}, BROWSER_TZ)).toBe(FLOW_TIMEZONE_DEFAULT);
    expect(storedFlowTimezone({ timezone: BROWSER_TZ }, BROWSER_TZ)).toBe(FLOW_TIMEZONE_DEFAULT);
    expect(storedFlowTimezone({ timezone: 'Europe/Berlin' }, BROWSER_TZ)).toBe('Europe/Berlin');
  });

  it('normalizeFlowSettingsForSave persists browser timezone for default', () => {
    expect(normalizeFlowSettingsForSave({}, BROWSER_TZ)).toEqual({ timezone: BROWSER_TZ });
    expect(normalizeFlowSettingsForSave({ timezone: FLOW_TIMEZONE_DEFAULT }, BROWSER_TZ)).toEqual({
      timezone: BROWSER_TZ,
    });
    expect(normalizeFlowSettingsForSave({ timezone: 'Europe/Berlin' }, BROWSER_TZ)).toEqual({
      timezone: 'Europe/Berlin',
    });
  });

  it('flowTimezoneForPersist maps DEFAULT to browser timezone', () => {
    expect(flowTimezoneForPersist(FLOW_TIMEZONE_DEFAULT, BROWSER_TZ)).toBe(BROWSER_TZ);
    expect(flowTimezoneForPersist('Europe/Berlin', BROWSER_TZ)).toBe('Europe/Berlin');
  });
});
