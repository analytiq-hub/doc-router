'use client';

import React from 'react';
import type { JsonValue } from '@docrouter/sdk';

type Props = {
  value: Record<string, JsonValue>;
};

function renderValue(value: JsonValue, parentKey: string, level: number): React.ReactNode {
  if (
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean' ||
    value === null
  ) {
    const stringValue = value?.toString() ?? '';
    const isEmpty = stringValue === '' || stringValue === 'null' || value === null;
    return (
      <div className={`flex-1 ${isEmpty ? 'text-gray-400 italic' : 'text-gray-900'}`}>
        {isEmpty ? 'null' : stringValue}
      </div>
    );
  }

  if (typeof value === 'object' && !Array.isArray(value)) {
    if (Object.keys(value).length === 0) {
      return <div className="text-sm text-gray-500 italic">Empty object</div>;
    }
    return (
      <div className={`space-y-2 ${level > 0 ? 'ml-4 pl-2 border-l border-gray-200' : ''}`}>
        {Object.entries(value).map(([key, val]) => {
          const fullKey = parentKey ? `${parentKey}.${key}` : key;
          return (
            <div key={fullKey} className="text-sm">
              <div className="text-xs text-gray-500 mb-1">{key}</div>
              {renderValue(val, fullKey, level + 1)}
            </div>
          );
        })}
      </div>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <div className="text-sm text-gray-500 italic">Empty array</div>;
    }
    const isPrimitiveArray = value.every(
      (item) =>
        typeof item === 'string' ||
        typeof item === 'number' ||
        typeof item === 'boolean' ||
        item === null
    );
    if (isPrimitiveArray) {
      return (
        <div className="space-y-2">
          {value.map((item, index) => (
            <div key={index} className="flex items-center gap-2 pl-2 border-l-2 border-gray-200">
              <span className="text-gray-500 text-xs w-6">[{index}]</span>
              <span className="flex-1 font-medium text-gray-900">{item?.toString() ?? ''}</span>
            </div>
          ))}
        </div>
      );
    }
    return (
      <div className="space-y-3">
        {value.map((item, index) => (
          <div key={index} className="border rounded p-2 bg-gray-50 min-w-0">
            <div className="font-medium text-sm text-gray-700 mb-2 truncate">Item {index}</div>
            {typeof item === 'object' && item !== null ? (
              <div className="pl-3 border-l-2 border-gray-300">
                {renderValue(item as JsonValue, `${parentKey}[${index}]`, level + 1)}
              </div>
            ) : (
              <div className="text-sm font-medium text-gray-900">{item?.toString() ?? ''}</div>
            )}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="text-sm whitespace-pre-wrap break-words text-gray-700 bg-gray-50 rounded p-2">
      {JSON.stringify(value, null, 2)}
    </div>
  );
}

export default function LlmResultTree({ value }: Props) {
  return <div className="p-4 space-y-3">{renderValue(value, '', 0)}</div>;
}
