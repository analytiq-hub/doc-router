import { describe, expect, it } from 'vitest';
import { validateCronExpression, validateScheduleRuleParameter } from './flowCronValidation';

describe('validateCronExpression', () => {
  it('accepts non-empty expressions (semantic check is backend croniter)', () => {
    expect(validateCronExpression('0 9 * * 1-5')).toBeNull();
    expect(validateCronExpression('0 * * * 1,2,3-1')).toBeNull();
    expect(validateCronExpression('0 * * * * 1')).toBeNull();
  });

  it('rejects empty', () => {
    expect(validateCronExpression('   ')).toMatch(/required/i);
  });
});

describe('validateScheduleRuleParameter', () => {
  it('reports rule index for empty cron', () => {
    expect(
      validateScheduleRuleParameter({
        interval: [{ field: 'cronExpression', cronExpression: '  ' }],
      }),
    ).toMatch(/Rule 1:/);
  });

  it('rejects more than the max interval rules', () => {
    const interval = Array.from({ length: 21 }, () => ({
      field: 'hours' as const,
      hoursInterval: 1,
    }));
    expect(validateScheduleRuleParameter({ interval })).toBe(
      'At most 20 trigger rules are allowed',
    );
  });
});
