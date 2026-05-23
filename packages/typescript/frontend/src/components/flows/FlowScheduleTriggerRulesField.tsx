'use client';

import React from 'react';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline';
import { flowInputClass, flowLabelClass, flowSelectClass } from './flowUiClasses';
import { CRON_FORMAT_HINT, validateCronExpression } from './flowCronValidation';

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

const INTERVAL_FIELD_OPTIONS: { value: ScheduleIntervalRule['field']; label: string }[] = [
  { value: 'minutes', label: 'Minutes' },
  { value: 'hours', label: 'Hours' },
  { value: 'days', label: 'Days' },
  { value: 'cronExpression', label: 'Custom (Cron)' },
];

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
  const intervals = ruleValue.interval ?? [defaultIntervalRule()];

  const patchIntervals = (next: ScheduleIntervalRule[]) => {
    onChange({ interval: next.length > 0 ? next : [defaultIntervalRule()] });
  };

  const updateRule = (index: number, patch: Partial<ScheduleIntervalRule>) => {
    const next = intervals.map((row, i) => (i === index ? { ...row, ...patch } : row));
    patchIntervals(next);
  };

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-blue-100 bg-blue-50/80 px-3 py-2.5 text-sm text-gray-700">
        This flow runs on the schedule below once you <strong>activate</strong> it. To test without waiting,
        use <strong>Execute workflow</strong> on the canvas.
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
                  min={1}
                  max={59}
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
                  min={1}
                  max={23}
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
                  min={1}
                  max={31}
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
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
          onClick={() => patchIntervals([...intervals, defaultIntervalRule()])}
        >
          <PlusIcon className="h-4 w-4" aria-hidden />
          Add rule
        </button>
      ) : null}
    </div>
  );
};
