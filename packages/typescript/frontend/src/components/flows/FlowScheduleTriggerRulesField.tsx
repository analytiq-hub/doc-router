'use client';

import React from 'react';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline';
import { flowInputClass, flowLabelClass, flowSelectClass } from './flowUiClasses';
import { CRON_FORMAT_HINT, validateCronExpression } from './flowCronValidation';
import {
  coerceScheduleRuleValue,
  defaultScheduleIntervalRule,
  maxScheduleIntervalRules,
  scheduleIntervalBounds,
  type ScheduleIntervalRule,
  type ScheduleRuleValue,
} from './flowScheduleTriggerRules';

export type { ScheduleIntervalRule, ScheduleRuleValue };
export {
  coerceScheduleRuleValue,
  defaultScheduleIntervalRule,
  maxScheduleIntervalRules,
  scheduleIntervalBounds,
} from './flowScheduleTriggerRules';
export { validateScheduleRule } from './flowCronValidation';

const INTERVAL_FIELD_OPTIONS: { value: ScheduleIntervalRule['field']; label: string }[] = [
  { value: 'minutes', label: 'Minutes' },
  { value: 'hours', label: 'Hours' },
  { value: 'days', label: 'Days' },
  { value: 'cronExpression', label: 'Custom (Cron)' },
];

/**
 * Repeatable trigger interval rules (n8n Schedule Trigger “Trigger Rules”).
 * Edits the ``rule`` object on ``flows.trigger.schedule`` nodes.
 */
export const FlowScheduleTriggerRulesField: React.FC<{
  label: string;
  value: unknown;
  readOnly: boolean;
  onChange: (next: ScheduleRuleValue) => void;
}> = ({ label, value, readOnly, onChange }) => {
  const ruleValue = coerceScheduleRuleValue(value);
  const intervals = ruleValue.interval ?? [defaultScheduleIntervalRule()];
  const atRuleCap = intervals.length >= maxScheduleIntervalRules;

  const patchIntervals = (next: ScheduleIntervalRule[]) => {
    onChange({ interval: next.length > 0 ? next : [defaultScheduleIntervalRule()] });
  };

  const updateRule = (index: number, patch: Partial<ScheduleIntervalRule>) => {
    const next = intervals.map((row, i) => (i === index ? { ...row, ...patch } : row));
    patchIntervals(next);
  };

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-blue-100 bg-blue-50/80 px-3 py-2.5 text-sm text-gray-700">
        This flow runs on the schedule below once you <strong>activate</strong> it. To test without waiting,
        use <strong>Execute flow</strong> on the canvas.
      </div>

      <div className={flowLabelClass}>{label}</div>

      <div className="space-y-2">
        {intervals.map((row, index) => {
          const cronError =
            row.field === 'cronExpression' ? validateCronExpression(row.cronExpression ?? '') : null;
          return (
          <div
            key={index}
            className="space-y-2 rounded-md border border-gray-200 bg-gray-50/60 px-3 py-2.5"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Rule {index + 1}
              </span>
              {!readOnly && intervals.length > 1 ? (
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-red-600 hover:bg-red-50"
                  onClick={() => patchIntervals(intervals.filter((_, i) => i !== index))}
                  aria-label={`Remove rule ${index + 1}`}
                >
                  <TrashIcon className="h-3.5 w-3.5" aria-hidden />
                  Remove
                </button>
              ) : null}
            </div>

            <div>
              <label className="mb-0.5 block text-xs text-gray-600" htmlFor={`sched-field-${index}`}>
                Trigger interval
              </label>
              <select
                id={`sched-field-${index}`}
                className={flowSelectClass}
                value={row.field}
                disabled={readOnly}
                onChange={(e) =>
                  updateRule(index, { field: e.target.value as ScheduleIntervalRule['field'] })
                }
              >
                {INTERVAL_FIELD_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {row.field === 'minutes' ? (
              <div>
                <label className="mb-0.5 block text-xs text-gray-600" htmlFor={`sched-min-${index}`}>
                  Minutes between triggers
                </label>
                <input
                  id={`sched-min-${index}`}
                  type="number"
                  min={scheduleIntervalBounds.minutes.min}
                  max={scheduleIntervalBounds.minutes.max}
                  className={flowInputClass}
                  value={row.minutesInterval ?? 5}
                  readOnly={readOnly}
                  onChange={(e) => updateRule(index, { minutesInterval: Number(e.target.value) })}
                />
              </div>
            ) : null}

            {row.field === 'hours' ? (
              <div>
                <label className="mb-0.5 block text-xs text-gray-600" htmlFor={`sched-hr-${index}`}>
                  Hours between triggers
                </label>
                <input
                  id={`sched-hr-${index}`}
                  type="number"
                  min={scheduleIntervalBounds.hours.min}
                  max={scheduleIntervalBounds.hours.max}
                  className={flowInputClass}
                  value={row.hoursInterval ?? 1}
                  readOnly={readOnly}
                  onChange={(e) => updateRule(index, { hoursInterval: Number(e.target.value) })}
                />
              </div>
            ) : null}

            {row.field === 'days' ? (
              <div>
                <label className="mb-0.5 block text-xs text-gray-600" htmlFor={`sched-day-${index}`}>
                  Days between triggers
                </label>
                <input
                  id={`sched-day-${index}`}
                  type="number"
                  min={scheduleIntervalBounds.days.min}
                  max={scheduleIntervalBounds.days.max}
                  className={flowInputClass}
                  value={row.daysInterval ?? 1}
                  readOnly={readOnly}
                  onChange={(e) => updateRule(index, { daysInterval: Number(e.target.value) })}
                />
              </div>
            ) : null}

            {row.field === 'cronExpression' ? (
              <div>
                <label className="mb-0.5 block text-xs text-gray-600" htmlFor={`sched-cron-${index}`}>
                  Cron expression
                </label>
                <input
                  id={`sched-cron-${index}`}
                  className={
                    flowInputClass +
                    ' font-mono text-[11px]' +
                    (cronError ? ' border-red-400 focus:border-red-500 focus:ring-red-200' : '')
                  }
                  value={row.cronExpression ?? '0 * * * *'}
                  readOnly={readOnly}
                  placeholder="0 9 * * 1-5"
                  onChange={(e) => updateRule(index, { cronExpression: e.target.value })}
                />
                {cronError ? (
                  <p className="mt-0.5 text-[11px] text-red-600">{cronError}</p>
                ) : (
                  <p className="mt-0.5 text-[11px] text-gray-500">{CRON_FORMAT_HINT}</p>
                )}
              </div>
            ) : null}
          </div>
          );
        })}
      </div>

      {!readOnly ? (
        <div className="space-y-1">
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={atRuleCap}
            onClick={() => patchIntervals([...intervals, defaultScheduleIntervalRule()])}
          >
            <PlusIcon className="h-4 w-4" aria-hidden />
            Add rule
          </button>
          {atRuleCap ? (
            <p className="text-[11px] text-gray-500">
              Maximum {maxScheduleIntervalRules} rules (matches backend limit).
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};
