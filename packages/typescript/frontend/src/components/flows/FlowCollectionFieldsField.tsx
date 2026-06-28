'use client';

import React from 'react';
import { TrashIcon } from '@heroicons/react/24/outline';
import { flowSelectClass } from './flowUiClasses';
import { FlowParamLabel } from './FlowParamLabel';
import { defaultFromSubschema, mergeCollectionFieldDefaults } from './flowSchemaParameterUtils';

function propertyTitle(subschema: Record<string, unknown>, key: string): string {
  const titleRaw = subschema.title;
  return typeof titleRaw === 'string' && titleRaw.trim().length > 0 ? titleRaw.trim() : key;
}

/**
 * Optional object fields (n8n-style collection): start empty, add via dropdown, remove per row.
 */
export const FlowCollectionFieldsField: React.FC<{
  label: string;
  description?: string;
  addLabel: string;
  subschema: Record<string, unknown>;
  value: unknown;
  readOnly: boolean;
  onChange: (next: Record<string, unknown>) => void;
  renderProperty: (
    propertyKey: string,
    propertySchema: Record<string, unknown>,
    ctx: {
      params: Record<string, unknown>;
      setField: (fieldKey: string, value: unknown) => void;
      idPrefix: string;
      suppressLabel: boolean;
    },
  ) => React.ReactNode;
  idPrefix: string;
}> = ({ label, description, addLabel, subschema, value, readOnly, onChange, renderProperty, idPrefix }) => {
  const nestedProps = (subschema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const propertyOrder = Object.keys(nestedProps);
  const obj = mergeCollectionFieldDefaults(subschema, value);

  const activeKeys = propertyOrder.filter((k) => Object.prototype.hasOwnProperty.call(obj, k));
  const availableKeys = propertyOrder.filter((k) => !Object.prototype.hasOwnProperty.call(obj, k));

  const addFilter = (key: string) => {
    if (!key || readOnly) return;
    onChange({ ...obj, [key]: defaultFromSubschema(nestedProps[key]) });
  };

  const removeFilter = (key: string) => {
    if (readOnly) return;
    const next = { ...obj };
    delete next[key];
    onChange(next);
  };

  return (
    <div className="space-y-2">
      <FlowParamLabel
        label={label}
        description={description}
        wrapperClassName="border-b border-gray-200 pb-1"
        className="text-[11px] font-semibold uppercase tracking-wide text-gray-500"
      />

      {activeKeys.map((key) => {
        const propSchema = nestedProps[key];
        const propTitle = propertyTitle(propSchema, key);
        const nestedCtx = {
          params: obj,
          setField: (fieldKey: string, fieldValue: unknown) => {
            onChange({ ...obj, [fieldKey]: fieldValue });
          },
          idPrefix: `${idPrefix}${key}-`,
          suppressLabel: true,
        };
        return (
          <div key={key} className="space-y-1 border-b border-gray-100 pb-2 last:border-b-0">
            <div className="flex items-center gap-1.5">
              {!readOnly ? (
                <button
                  type="button"
                  className="inline-flex shrink-0 items-center rounded p-0.5 text-red-600 hover:bg-red-50"
                  onClick={() => removeFilter(key)}
                  aria-label={`Remove ${propTitle} filter`}
                >
                  <TrashIcon className="h-3.5 w-3.5" aria-hidden />
                </button>
              ) : null}
              <span className="text-xs font-medium text-gray-700">{propTitle}</span>
            </div>
            {renderProperty(key, propSchema, nestedCtx)}
          </div>
        );
      })}

      {!readOnly && availableKeys.length > 0 ? (
        <select
          className={flowSelectClass}
          value=""
          aria-label={addLabel}
          onChange={(e) => {
            const selected = e.target.value;
            if (selected) addFilter(selected);
          }}
        >
          <option value="">{addLabel}</option>
          {availableKeys.map((key) => (
            <option key={key} value={key}>
              {propertyTitle(nestedProps[key], key)}
            </option>
          ))}
        </select>
      ) : null}
    </div>
  );
};
