import { describe, expect, it } from 'vitest';
import { coerceScheduleRuleValue } from './FlowScheduleTriggerRulesField';

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
