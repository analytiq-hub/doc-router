import React from 'react';
import { flowLabelClass } from './flowUiClasses';

const flowParamHintClass = 'mb-1.5 text-[11px] leading-snug text-gray-500';
const checkboxClass =
  'h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60';

export const FlowTextractFeaturePickerField: React.FC<{
  label: string;
  description?: string;
  value: unknown;
  options: string[];
  readOnly?: boolean;
  onChange: (next: string[]) => void;
}> = ({ label, description, value, options, readOnly = false, onChange }) => {
  const selected = Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === 'string')
    : [];

  const toggle = (feature: string) => {
    if (readOnly) return;
    const next = selected.includes(feature)
      ? selected.filter((entry) => entry !== feature)
      : [...selected, feature];
    onChange(next);
  };

  return (
    <div>
      <span className={flowLabelClass}>{label}</span>
      {description ? <p className={flowParamHintClass}>{description}</p> : null}
      <div className="flex flex-wrap gap-3">
        {options.map((feature) => (
          <label key={feature} className="inline-flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              className={checkboxClass}
              checked={selected.includes(feature)}
              disabled={readOnly}
              onChange={() => toggle(feature)}
            />
            {feature}
          </label>
        ))}
      </div>
    </div>
  );
};
