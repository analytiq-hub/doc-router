'use client';

import React from 'react';
import { flowInputClass, flowLabelClass } from './flowUiClasses';
import { FLOW_VALUE_MIME, type FlowValueDragPayload } from './IoViewer';

export type NameValuePair = { name: string; value: string };

function parseDropPayload(e: React.DragEvent): FlowValueDragPayload | null {
  const raw = e.dataTransfer.getData(FLOW_VALUE_MIME);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as FlowValueDragPayload;
    if (!parsed || parsed.kind !== 'jsonPath' || typeof parsed.nodeId !== 'string' || !Array.isArray(parsed.path))
      return null;
    return parsed;
  } catch {
    return null;
  }
}

export function payloadToExpression(p: FlowValueDragPayload): string {
  let expr = `_node["${p.nodeId}"]["json"]`;
  for (const seg of p.path) {
    expr += typeof seg === 'number' ? `[${seg}]` : `["${String(seg)}"]`;
  }
  return `=${expr}`;
}

export function coerceNameValuePairs(raw: unknown): NameValuePair[] {
  if (!Array.isArray(raw)) return [];
  const out: NameValuePair[] = [];
  for (const row of raw) {
    if (row && typeof row === 'object' && 'name' in row) {
      const o = row as { name?: unknown; value?: unknown };
      out.push({ name: typeof o.name === 'string' ? o.name : '', value: typeof o.value === 'string' ? o.value : '' });
    }
  }
  return out;
}

/** Array-of-{name,value} editor; drag-from-IO applies only to the value cell (drops on name are ignored). */
export const FlowNameValueListField: React.FC<{
  label: string;
  value: unknown;
  readOnly: boolean;
  onChange: (next: NameValuePair[]) => void;
}> = ({ label, value, readOnly, onChange }) => {
  const pairs = coerceNameValuePairs(value);

  return (
    <div className="space-y-2">
      <div className={flowLabelClass}>{label}</div>
      <div className="space-y-1.5">
        {pairs.map((row, i) => (
          <div key={i} className="flex gap-2">
            <input
              className={flowInputClass + ' min-w-0 flex-1'}
              placeholder="name"
              value={row.name}
              readOnly={readOnly}
              onChange={(e) => {
                const n = [...pairs];
                n[i] = { ...n[i], name: e.target.value };
                onChange(n);
              }}
            />
            <input
              className={flowInputClass + ' min-w-0 flex-1'}
              placeholder="value or =expression"
              value={row.value}
              readOnly={readOnly}
              onChange={(e) => {
                const n = [...pairs];
                n[i] = { ...n[i], value: e.target.value };
                onChange(n);
              }}
              onDragOver={(e) => {
                if (readOnly) return;
                if (e.dataTransfer.types.includes(FLOW_VALUE_MIME)) e.preventDefault();
              }}
              onDrop={(e) => {
                if (readOnly) return;
                const p = parseDropPayload(e);
                if (!p) return;
                e.preventDefault();
                const n = [...pairs];
                n[i] = { ...n[i], value: payloadToExpression(p) };
                onChange(n);
              }}
            />
            {!readOnly && (
              <button
                type="button"
                className="shrink-0 rounded border border-gray-200 px-2 text-[11px] text-gray-600 hover:bg-gray-50"
                onClick={() => onChange(pairs.filter((_, j) => j !== i))}
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
      {!readOnly && (
        <button
          type="button"
          className="text-[11px] font-semibold text-sky-700 hover:text-sky-900"
          onClick={() => onChange([...pairs, { name: '', value: '' }])}
        >
          + Add row
        </button>
      )}
    </div>
  );
};
