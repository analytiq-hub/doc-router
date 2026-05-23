export type ScheduleIntervalRule = {
  field: 'minutes' | 'hours' | 'days' | 'cronExpression';
  minutesInterval?: number;
  hoursInterval?: number;
  daysInterval?: number;
  cronExpression?: string;
};

export type ScheduleRuleValue = {
  interval?: ScheduleIntervalRule[];
};

/** Must match ``MAX_SCHEDULE_INTERVAL_RULES`` in ``cron_exprs.py`` (schedule trigger schema ``maxItems``). */
export const maxScheduleIntervalRules = 20;

/** Must match ``schedule_rule_to_interval_seconds`` in ``cron_exprs.py`` (UI min/max attrs). */
export const scheduleIntervalBounds = {
  minutes: { min: 1, max: 59 },
  hours: { min: 1, max: 23 },
  days: { min: 1, max: 31 },
} as const;

function defaultIntervalRule(): ScheduleIntervalRule {
  return { field: 'hours', hoursInterval: 1 };
}

function coerceOneRule(raw: unknown): ScheduleIntervalRule {
  if (!raw || typeof raw !== 'object') return defaultIntervalRule();
  const o = raw as Record<string, unknown>;
  const field = o.field;
  const f: ScheduleIntervalRule['field'] =
    field === 'minutes' || field === 'hours' || field === 'days' || field === 'cronExpression'
      ? field
      : 'hours';
  return {
    field: f,
    minutesInterval: typeof o.minutesInterval === 'number' ? o.minutesInterval : 5,
    hoursInterval: typeof o.hoursInterval === 'number' ? o.hoursInterval : 1,
    daysInterval: typeof o.daysInterval === 'number' ? o.daysInterval : 1,
    cronExpression: typeof o.cronExpression === 'string' ? o.cronExpression : '0 * * * *',
  };
}

/** Normalise stored ``rule`` parameter (``{ interval: [...] }``). */
export function coerceScheduleRuleValue(raw: unknown): ScheduleRuleValue {
  if (raw && typeof raw === 'object') {
    const interval = (raw as ScheduleRuleValue).interval;
    if (Array.isArray(interval) && interval.length > 0) {
      return { interval: interval.map(coerceOneRule) };
    }
  }
  return { interval: [defaultIntervalRule()] };
}

export function defaultScheduleIntervalRule(): ScheduleIntervalRule {
  return defaultIntervalRule();
}
