import React from 'react';
import { flowLabelClass } from './flowUiClasses';

const flowParamHintClass = 'mb-1.5 text-[11px] leading-snug text-gray-500';
const checkboxClass =
  'h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60';

/** Multi-select checkboxes for `type: array` + `items.enum` flow parameters. */
export const FlowEnumMultiCheckboxField: React.FC<{
  label: string;
  description?: string;
  value: unknown;
  options: string[];
  enumNames?: string[];
  readOnly?: boolean;
  onChange: (next: string[]) => void;
}> = ({ label, description, value, options, enumNames, readOnly = false, onChange }) => {
  const selected = Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === 'string')
    : [];

  const toggle = (option: string) => {
    if (readOnly) return;
    const next = selected.includes(option)
      ? selected.filter((entry) => entry !== option)
      : [...selected, option];
    onChange(next);
  };

  return (
    <div>
      <span className={flowLabelClass}>{label}</span>
      {description ? <p className={flowParamHintClass}>{description}</p> : null}
      <div className="flex flex-wrap gap-3">
        {options.map((option, idx) => (
          <label key={option} className="inline-flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              className={checkboxClass}
              checked={selected.includes(option)}
              disabled={readOnly}
              onChange={() => toggle(option)}
            />
            {enumNames?.[idx] != null && String(enumNames[idx]).trim().length > 0
              ? String(enumNames[idx])
              : option}
          </label>
        ))}
      </div>
    </div>
  );
};
