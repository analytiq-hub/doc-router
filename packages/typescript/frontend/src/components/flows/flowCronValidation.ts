/**
 * Lightweight schedule/cron checks in the UI.
 *
 * Authoritative cron validation is Python **croniter** via
 * ``validate_cron_expression`` in ``packages/python/analytiq_data/flows/triggers/cron_exprs.py``
 * (``croniter.is_valid``). This module only rejects empty expressions before save; it does **not**
 * mirror croniter's full grammar. Expressions that pass here may still fail on save, and
 * croniter may accept forms this UI never pre-validates. Keep parity tests in
 * ``packages/python/tests/flows/test_trigger_cron_exprs.py`` when changing either side.
 *
 * Interval bounds and max rule count must stay aligned with ``cron_exprs.py`` and
 * ``flows.trigger.schedule`` parameter schema.
 */

import type { ScheduleIntervalRule } from './flowScheduleTriggerRules';
import { maxScheduleIntervalRules } from './flowScheduleTriggerRules';

/** Non-empty check only — semantic validation is croniter on the backend (see module doc). */
export function validateCronExpression(expr: string): string | null {
  const trimmed = (expr || '').trim();
  if (!trimmed) {
    return 'Cron expression is required';
  }
  return null;
}

export const CRON_FORMAT_HINT =
  'Cron syntax is validated on save (Python croniter). Typical 5-field form: minute hour day-of-month month day-of-week. Example: 0 9 * * 1-5';

/** Return an error message when a rule is out of backend bounds, else ``null``. */
export function validateScheduleRule(rule: ScheduleIntervalRule): string | null {
  if (rule.field === 'minutes') {
    const n = rule.minutesInterval ?? 5;
    if (n < 1 || n > 59) {
      return 'minutesInterval must be between 1 and 59';
    }
    return null;
  }
  if (rule.field === 'hours') {
    const n = rule.hoursInterval ?? 1;
    if (n < 1 || n > 23) {
      return 'hoursInterval must be between 1 and 23';
    }
    return null;
  }
  if (rule.field === 'days') {
    const n = rule.daysInterval ?? 1;
    if (n < 1 || n > 31) {
      return 'daysInterval must be between 1 and 31';
    }
    return null;
  }
  if (rule.field === 'cronExpression') {
    return validateCronExpression(rule.cronExpression ?? '');
  }
  return null;
}

/** Validate every custom-cron rule inside a schedule trigger ``rule`` blob (non-empty only). */
export function validateScheduleRuleParameter(rule: unknown): string | null {
  if (!rule || typeof rule !== 'object') {
    return 'Trigger rules are required';
  }
  const interval = (rule as { interval?: unknown }).interval;
  if (!Array.isArray(interval) || interval.length === 0) {
    return 'Add at least one trigger rule';
  }
  if (interval.length > maxScheduleIntervalRules) {
    return `At most ${maxScheduleIntervalRules} trigger rules are allowed`;
  }
  for (let i = 0; i < interval.length; i += 1) {
    const entry = interval[i];
    if (!entry || typeof entry !== 'object') continue;
    const field = (entry as { field?: unknown }).field;
    if (field !== 'cronExpression') continue;
    const cronExpr = String((entry as { cronExpression?: unknown }).cronExpression ?? '');
    const err = validateCronExpression(cronExpr);
    if (err) {
      return `Rule ${i + 1}: ${err}`;
    }
  }
  return null;
}
