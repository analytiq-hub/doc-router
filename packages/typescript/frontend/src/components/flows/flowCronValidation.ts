/** Lightweight cron field checks in the UI; authoritative validation is ``croniter`` on the backend. */

export function validateCronExpression(expr: string): string | null {
  const trimmed = (expr || '').trim();
  if (!trimmed) {
    return 'Cron expression is required';
  }
  return null;
}

export const CRON_FORMAT_HINT =
  'Cron syntax is validated on save (Python croniter). Typical 5-field form: minute hour day-of-month month day-of-week. Example: 0 9 * * 1-5';

/** Validate every custom-cron rule inside a schedule trigger ``rule`` blob (non-empty only). */
export function validateScheduleRuleParameter(rule: unknown): string | null {
  if (!rule || typeof rule !== 'object') {
    return 'Trigger rules are required';
  }
  const interval = (rule as { interval?: unknown }).interval;
  if (!Array.isArray(interval) || interval.length === 0) {
    return 'Add at least one trigger rule';
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
