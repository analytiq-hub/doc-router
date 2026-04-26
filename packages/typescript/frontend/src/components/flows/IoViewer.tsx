import React, { useMemo, useState } from 'react';
import Editor from '@monaco-editor/react';

type JsonPath = Array<string | number>;

export type FlowValueDragPayload = {
  kind: 'jsonPath';
  source: 'nodeOutput' | 'nodeInput';
  nodeId: string;
  path: JsonPath;
  exampleValue: unknown;
};

export const FLOW_VALUE_MIME = 'application/docrouter-flow-value';

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return Boolean(v) && typeof v === 'object' && !Array.isArray(v);
}

function getAtPath(root: unknown, path: JsonPath): unknown {
  let cur: unknown = root;
  for (const seg of path) {
    if (typeof seg === 'number') {
      if (!Array.isArray(cur)) return undefined;
      cur = cur[seg];
      continue;
    }
    if (!isPlainObject(cur)) return undefined;
    cur = cur[seg];
  }
  return cur;
}

type TableData = { columns: string[]; rows: Record<string, unknown>[] };

function convertToTable(value: unknown, caps: { maxCols: number; maxRows: number }): TableData | null {
  if (!Array.isArray(value)) return null;
  const objs = value.filter(isPlainObject) as Record<string, unknown>[];
  if (objs.length === 0) return null;
  const rows = objs.slice(0, caps.maxRows);
  const colsSet = new Set<string>();
  for (const r of rows) for (const k of Object.keys(r)) colsSet.add(k);
  const columns = Array.from(colsSet).slice(0, caps.maxCols);
  return { columns, rows };
}

function pathToExpression(nodeId: string, path: JsonPath): string {
  let expr = `_node["${nodeId}"]["json"]`;
  for (const seg of path) {
    expr += typeof seg === 'number' ? `[${seg}]` : `["${seg}"]`;
  }
  return `=${expr}`;
}

function stringifyJson(v: unknown): string {
  try {
    return JSON.stringify(v ?? null, null, 2);
  } catch {
    return String(v);
  }
}

function isExpandable(v: unknown): boolean {
  return (Array.isArray(v) && v.length > 0) || (Boolean(v) && typeof v === 'object' && !Array.isArray(v) && Object.keys(v as object).length > 0);
}

function shortValuePreview(v: unknown): string {
  if (v === null) return 'null';
  if (typeof v === 'string') return v.length > 80 ? `${v.slice(0, 77)}…` : v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (Array.isArray(v)) return `Array(${v.length})`;
  if (typeof v === 'object') return 'Object';
  if (typeof v === 'undefined') return 'undefined';
  return String(v);
}

const SchemaAccordion: React.FC<{
  label: string;
  value: unknown;
  path: JsonPath;
  onDragStartPath: (e: React.DragEvent, path: JsonPath) => void;
  depth?: number;
  maxDepth?: number;
}> = ({ label, value, path, onDragStartPath, depth = 0, maxDepth = 6 }) => {
  const expandable = isExpandable(value) && depth < maxDepth;
  const [open, setOpen] = useState(depth < 1);

  const entries: Array<[string, unknown]> = useMemo(() => {
    if (!expandable) return [];
    if (Array.isArray(value)) return (value as unknown[]).map((v, i) => [String(i), v]);
    return Object.entries(value as Record<string, unknown>);
  }, [expandable, value]);

  return (
    <div className="border-b border-gray-100 last:border-b-0">
      <div className="flex items-start gap-2 px-2 py-1.5">
        <button
          type="button"
          className={[
            'shrink-0 rounded px-1 text-[11px] font-semibold text-gray-500',
            expandable ? 'hover:bg-gray-50' : 'cursor-default',
          ].join(' ')}
          onClick={() => expandable && setOpen((o) => !o)}
          aria-label={expandable ? (open ? 'Collapse' : 'Expand') : 'Value'}
        >
          {expandable ? (open ? '▼' : '▶') : '•'}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-start justify-between gap-2">
            <div
              className="min-w-0 truncate font-mono text-[11px] font-semibold text-gray-900"
              draggable
              onDragStart={(e) => onDragStartPath(e, path)}
              title="Drag to insert expression"
            >
              {label}
            </div>
            <div className="min-w-0 truncate font-mono text-[11px] text-gray-600">{shortValuePreview(value)}</div>
          </div>
        </div>
      </div>
      {expandable && open && (
        <div className="pl-5">
          {entries.slice(0, 200).map(([k, v]) => (
            <SchemaAccordion
              key={`${label}.${k}`}
              label={k}
              value={v}
              path={[...path, Array.isArray(value) ? Number(k) : k]}
              onDragStartPath={onDragStartPath}
              depth={depth + 1}
              maxDepth={maxDepth}
            />
          ))}
          {entries.length > 200 && (
            <div className="px-2 py-1 text-[11px] text-gray-500">… truncated ({entries.length - 200} more)</div>
          )}
        </div>
      )}
    </div>
  );
};

export const IoViewer: React.FC<{
  title?: string;
  value: unknown;
  dragSource: { nodeId: string; source: FlowValueDragPayload['source'] };
  defaultMode?: 'schema' | 'table' | 'json';
}> = ({ title, value, dragSource, defaultMode = 'json' }) => {
  const [mode, setMode] = useState<'schema' | 'table' | 'json'>(defaultMode);

  const sample = useMemo(() => {
    if (Array.isArray(value)) return value[0];
    return value;
  }, [value]);

  const table = useMemo(() => convertToTable(value, { maxCols: 25, maxRows: 50 }), [value]);

  const startDrag = (e: React.DragEvent, path: JsonPath) => {
    const payload: FlowValueDragPayload = {
      kind: 'jsonPath',
      source: dragSource.source,
      nodeId: dragSource.nodeId,
      path,
      exampleValue: getAtPath(sample, path),
    };
    e.dataTransfer.setData(FLOW_VALUE_MIME, JSON.stringify(payload));
    e.dataTransfer.effectAllowed = 'copy';
  };

  return (
    <div className="min-w-0">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="min-w-0">
          {title && <div className="truncate text-[11px] font-semibold text-gray-700">{title}</div>}
        </div>
        <div className="inline-flex rounded-md border border-gray-200 bg-white p-0.5 text-[11px]">
          {(['schema', 'table', 'json'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={[
                'rounded px-2 py-1 font-semibold',
                mode === m ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-50',
              ].join(' ')}
            >
              {m.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {mode === 'schema' && (
        <div className="rounded border border-[#eceff2] bg-white">
          <div className="max-h-[360px] overflow-auto">
            <SchemaAccordion
              label="$json"
              value={sample}
              path={[]}
              onDragStartPath={startDrag}
              depth={0}
              maxDepth={6}
            />
          </div>
        </div>
      )}

      {mode === 'table' && (
        <div className="rounded border border-[#eceff2] bg-white">
          {table == null ? (
            <div className="p-3 text-sm text-gray-500">Not a table: expected an array of objects.</div>
          ) : (
            <div className="max-h-[360px] overflow-auto">
              <table className="w-full border-collapse text-[11px]">
                <thead className="sticky top-0 bg-[#fafbfc]">
                  <tr>
                    {table.columns.map((c) => (
                      <th
                        key={c}
                        className="border-b border-gray-200 px-2 py-1.5 text-left font-semibold text-gray-700"
                        draggable
                        onDragStart={(e) => startDrag(e, [c])}
                        title={`Drag to insert expression: ${pathToExpression(dragSource.nodeId, [c])}`}
                      >
                        <span className="cursor-grab active:cursor-grabbing">{c}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((row, idx) => (
                    <tr key={idx} className="odd:bg-white even:bg-gray-50/40">
                      {table.columns.map((c) => (
                        <td key={c} className="border-b border-gray-100 px-2 py-1 align-top text-gray-900">
                          <span className="line-clamp-2 font-mono">{stringifyJson(row[c])}</span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {mode === 'json' && (
        <div className="rounded border border-[#eceff2] bg-white">
          <Editor
            height="360px"
            language="json"
            value={stringifyJson(sample)}
            options={{
              minimap: { enabled: false },
              fontSize: 11,
              scrollBeyondLastLine: false,
              readOnly: true,
              wordWrap: 'on',
              folding: true,
              showFoldingControls: 'always',
              foldingHighlight: true,
              renderLineHighlight: 'none',
            }}
          />
        </div>
      )}
    </div>
  );
};

