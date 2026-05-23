import { describe, expect, it } from 'vitest';
import { validateScheduleRule, validateScheduleRuleParameter } from './flowCronValidation';
import { coerceScheduleRuleValue } from './flowScheduleTriggerRules';

describe('coerceScheduleRuleValue', () => {
  it('returns default hourly rule for empty input', () => {
    expect(coerceScheduleRuleValue({})).toEqual({
      interval: [{ field: 'hours', hoursInterval: 1 }],
    });
  });

  it('preserves multiple rules', () => {
    expect(
      coerceScheduleRuleValue({
        interval: [
          { field: 'minutes', minutesInterval: 15 },
          { field: 'cronExpression', cronExpression: '0 9 * * *' },
        ],
      }),
    ).toEqual({
      interval: [
        { field: 'minutes', minutesInterval: 15, hoursInterval: 1, daysInterval: 1, cronExpression: '0 * * * *' },
        { field: 'cronExpression', minutesInterval: 5, hoursInterval: 1, daysInterval: 1, cronExpression: '0 9 * * *' },
      ],
    });
  });
});

describe('validateScheduleRule', () => {
  it('accepts values within backend bounds', () => {
    expect(validateScheduleRule({ field: 'minutes', minutesInterval: 1 })).toBeNull();
    expect(validateScheduleRule({ field: 'minutes', minutesInterval: 59 })).toBeNull();
    expect(validateScheduleRule({ field: 'hours', hoursInterval: 23 })).toBeNull();
    expect(validateScheduleRule({ field: 'days', daysInterval: 31 })).toBeNull();
  });

  it('rejects out-of-range intervals with messages matching Python cron_exprs', () => {
    expect(validateScheduleRule({ field: 'minutes', minutesInterval: 0 })).toBe(
      'minutesInterval must be between 1 and 59',
    );
    expect(validateScheduleRule({ field: 'minutes', minutesInterval: 60 })).toBe(
      'minutesInterval must be between 1 and 59',
    );
    expect(validateScheduleRule({ field: 'hours', hoursInterval: 0 })).toBe(
      'hoursInterval must be between 1 and 23',
    );
    expect(validateScheduleRule({ field: 'hours', hoursInterval: 24 })).toBe(
      'hoursInterval must be between 1 and 23',
    );
    expect(validateScheduleRule({ field: 'days', daysInterval: 0 })).toBe(
      'daysInterval must be between 1 and 31',
    );
    expect(validateScheduleRule({ field: 'days', daysInterval: 32 })).toBe(
      'daysInterval must be between 1 and 31',
    );
  });
});
