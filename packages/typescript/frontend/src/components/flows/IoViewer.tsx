import React, { useEffect, useMemo, useState } from 'react';
import Editor from '@monaco-editor/react';
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline';

export type JsonPath = Array<string | number>;

export type FlowValueDragPayload =
  | {
      kind: 'jsonPath';
      source: 'nodeOutput' | 'nodeInput';
      nodeId: string;
      /** Canvas display name when non-empty; matches Python ``node_name`` (else expressions use ``nodeId``). */
      nodeDisplayName?: string;
      path: JsonPath;
      exampleValue: unknown;
    }
  | {
      kind: 'contextVar';
      /** Root identifier for drag-insert, e.g. `_json` — must match ``expressions.eval_expression`` env names */
      varName: string;
      path: JsonPath;
      exampleValue: unknown;
    };

export const FLOW_VALUE_MIME = 'application/docrouter-flow-value';

/** Parse MIME payload from `FLOW_VALUE_MIME`; rejects malformed or unknown shapes. */
export function parseFlowValueDragPayload(raw: string): FlowValueDragPayload | null {
  try {
    const parsed = JSON.parse(raw) as FlowValueDragPayload | null;
    if (!parsed || typeof parsed !== 'object') return null;
    if (parsed.kind === 'contextVar') {
      if (typeof (parsed as { varName?: unknown }).varName !== 'string') return null;
      if (!Array.isArray((parsed as { path?: unknown }).path)) return null;
      return parsed;
    }
    if (parsed.kind === 'jsonPath') {
      const j = parsed as { nodeId?: unknown; path?: unknown };
      if (typeof j.nodeId !== 'string' || !Array.isArray(j.path)) return null;
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

/** Append JSON path segments to a base identifier (valid in flow expressions, e.g. ``_json``, ``_node[...]``). */
function appendPathToExpr(base: string, path: JsonPath): string {
  let expr = base;
  for (const seg of path) {
    expr += typeof seg === 'number' ? `[${seg}]` : `["${String(seg)}"]`;
  }
  return expr;
}

/**
 * Build the `=` expression inserted when dragging a field from INPUT/OUTPUT previews.
 *
 * Upstream output fields use name-keyed ``_node`` (Python): ``_node[<display>].json`` for slot 0 or
 * ``_node[<display>].output[slot].json``, matching ``materialize_node_outputs_by_name`` at execute time.
 *
 * When configuring node `configuringNodeId`:
 * - **`source === 'nodeInput'`** and **`nodeId === configuringNodeId`** → **`_json`** (this node's inbound item row).
 * - **`source === 'nodeOutput'`** (any node, including upstream) → **`_node[display].json`** so the expression names the
 *   node whose preview you dragged from — not `_json`, which would lose which upstream produced the field when multiple exist.
 *
 * `@param outputSlotIndex` defaults to first output handle (matches current single-slot wiring in the modal).
 */
export function payloadToExpression(
  p: FlowValueDragPayload,
  configuringNodeId?: string,
  outputSlotIndex = 0,
): string {
  if (p.kind === 'contextVar') {
    return `=${appendPathToExpr(p.varName, p.path)}`;
  }

  const useInboundJson =
    configuringNodeId != null &&
    p.source === 'nodeInput' &&
    p.nodeId === configuringNodeId;

  if (useInboundJson) {
    return `=${appendPathToExpr('_json', p.path)}`;
  }

  const display =
    typeof p.nodeDisplayName === 'string' && p.nodeDisplayName.trim() !== '' ? p.nodeDisplayName.trim() : p.nodeId;
  const keyLit = JSON.stringify(display);
  const base =
    outputSlotIndex === 0 ? `_node[${keyLit}].json` : `_node[${keyLit}].output[${outputSlotIndex}].json`;
  return `=${appendPathToExpr(base, p.path)}`;
}

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

type TableData = {
  columns: string[];
  rows: Record<string, unknown>[];
  /** Plain-object items beyond this were omitted from the table (browser safety cap). */
  omittedTailItemCount?: number;
};

/** Aligned with n8n editor `RunDataTable.vue` `convertToTable` (one row per item, columns grow in first-seen key order). */
const TABLE_MAX_KEYS_PER_ROW = 40;
/** Upper bound on items passed into table conversion — pagination displays within this window. */
const TABLE_MATERIALIZATION_CAP = 25_000;

const TABLE_PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const;

function coerceExecutionItems(raw: unknown): unknown[] {
  if (raw == null) return [];
  return Array.isArray(raw) ? raw : [raw];
}

/**
 * n8n-style: walk items in order; columns are appended when new keys appear; missing keys are `undefined`
 * and earlier rows are padded with trailing `undefined`s for columns added later.
 * Skips non-plain-object items (like n8n skipping entries without `json`).
 */
function convertToTableLikeN8n(items: unknown[], maxItems: number): TableData | null {
  const omittedTailItemCount =
    items.length > maxItems ? items.filter(isPlainObject).length - items.slice(0, maxItems).filter(isPlainObject).length : 0;

  const slice = items.slice(0, maxItems);
  const tableColumns: string[] = [];
  const rowArrays: unknown[][] = [];
  const rowSources: Record<string, unknown>[] = [];

  for (const raw of slice) {
    if (!isPlainObject(raw)) continue;
    const entry = raw;
    rowSources.push(entry);
    let entryColumns = Object.keys(entry);
    if (entryColumns.length > TABLE_MAX_KEYS_PER_ROW) {
      entryColumns = entryColumns.slice(0, TABLE_MAX_KEYS_PER_ROW);
    }

    let leftEntryColumns = [...entryColumns];
    const entryRows: unknown[] = [];

    for (const key of tableColumns) {
      if (Object.prototype.hasOwnProperty.call(entry, key)) {
        entryRows.push(entry[key]);
        const ix = leftEntryColumns.indexOf(key);
        if (ix !== -1) leftEntryColumns.splice(ix, 1);
      } else {
        entryRows.push(undefined);
      }
    }

    for (const key of leftEntryColumns) {
      tableColumns.push(key);
      entryRows.push(entry[key]);
    }

    rowArrays.push(entryRows);
  }

  if (rowArrays.length === 0) return null;

  for (const row of rowArrays) {
    while (row.length < tableColumns.length) {
      row.push(undefined);
    }
  }

  if (tableColumns.length === 0) {
    return {
      columns: ['_'],
      rows: rowSources.map((o) => ({ _: stringifyJsonCompact(o) })),
      omittedTailItemCount: omittedTailItemCount > 0 ? omittedTailItemCount : undefined,
    };
  }

  const rows: Record<string, unknown>[] = rowArrays.map((arr) => {
    const rec: Record<string, unknown> = {};
    tableColumns.forEach((col, i) => {
      rec[col] = arr[i];
    });
    return rec;
  });

  return {
    columns: tableColumns,
    rows,
    omittedTailItemCount: omittedTailItemCount > 0 ? omittedTailItemCount : undefined,
  };
}

function stringifyJson(v: unknown): string {
  try {
    return JSON.stringify(v ?? null, null, 2);
  } catch {
    return String(v);
  }
}

function stringifyJsonCompact(v: unknown): string {
  try {
    return JSON.stringify(v ?? null);
  } catch {
    return String(v);
  }
}

function isExpandable(v: unknown): boolean {
  return (
    (Array.isArray(v) && v.length > 0) ||
    (Boolean(v) && typeof v === 'object' && !Array.isArray(v) && Object.keys(v as object).length > 0)
  );
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

/** Shared Schema / Table / JSON toggle (n8n-style input/output toolbar). */
export function IoDataModeTabs({
  mode,
  onChange,
}: {
  mode: 'schema' | 'table' | 'json';
  onChange: (next: 'schema' | 'table' | 'json') => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-gray-200 bg-white p-0.5 text-[11px]">
      {(['schema', 'table', 'json'] as const).map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          title={m === 'schema' ? 'Schema' : m === 'table' ? 'Table' : 'JSON'}
          aria-label={m === 'schema' ? 'Schema' : m === 'table' ? 'Table' : 'JSON'}
          className={[
            'rounded px-2 py-1 text-[10px] font-semibold leading-none',
            mode === m ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-50',
          ].join(' ')}
        >
          {m === 'schema' ? 'Schema' : m === 'table' ? 'Table' : 'JSON'}
        </button>
      ))}
    </div>
  );
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
      <div className="flex items-center gap-2 px-2 py-1.5">
        {expandable ? (
          <button
            type="button"
            className="flex h-4 w-4 shrink-0 items-center justify-center rounded text-gray-500 hover:bg-gray-50"
            onClick={() => setOpen((o) => !o)}
            aria-label={open ? 'Collapse' : 'Expand'}
          >
            <ChevronRightIcon
              className={['h-3 w-3 transition-transform duration-150 ease-out', open ? 'rotate-90' : 'rotate-0'].join(' ')}
              strokeWidth={1.5}
            />
          </button>
        ) : (
          <span className="h-4 w-4 shrink-0" aria-hidden />
        )}
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

/** n8n-style schema: item count lives in header; body shows fields of the first item only — no `_json` root row. */
function SchemaFirstItemFields({
  schemaRoot,
  startDrag,
}: {
  schemaRoot: unknown;
  startDrag: (e: React.DragEvent, path: JsonPath) => void;
}) {
  if (schemaRoot === null || typeof schemaRoot === 'undefined') {
    return <div className="px-2 py-2 text-[11px] text-gray-500">No structured fields.</div>;
  }
  if (isPlainObject(schemaRoot)) {
    const entries = Object.entries(schemaRoot);
    if (entries.length === 0) {
      return <div className="px-2 py-2 text-[11px] text-gray-500">Empty object.</div>;
    }
    return (
      <>
        {entries.map(([k, v]) => (
          <SchemaAccordion
            key={k}
            label={k}
            value={v}
            path={[k]}
            onDragStartPath={startDrag}
            depth={0}
            maxDepth={6}
          />
        ))}
      </>
    );
  }
  if (Array.isArray(schemaRoot)) {
    if (schemaRoot.length === 0) {
      return <div className="px-2 py-2 text-[11px] text-gray-500">Empty array.</div>;
    }
    const capped = schemaRoot.slice(0, 200);
    return (
      <>
        {capped.map((v, i) => (
          <SchemaAccordion
            key={i}
            label={String(i)}
            value={v}
            path={[i]}
            onDragStartPath={startDrag}
            depth={0}
            maxDepth={6}
          />
        ))}
        {schemaRoot.length > 200 && (
          <div className="px-2 py-1 text-[11px] text-gray-500">
            … truncated ({schemaRoot.length - 200} more index entries)
          </div>
        )}
      </>
    );
  }

  return (
    <SchemaAccordion label="#" value={schemaRoot} path={[]} onDragStartPath={startDrag} depth={0} maxDepth={6} />
  );
}

export const IoViewer: React.FC<{
  title?: string;
  value: unknown;
  dragSource: { nodeId: string; source: 'nodeOutput' | 'nodeInput'; nodeDisplayName?: string };
  defaultMode?: 'schema' | 'table' | 'json';
  mode?: 'schema' | 'table' | 'json';
  onModeChange?: (next: 'schema' | 'table' | 'json') => void;
  /**
   * `executionItems`: value is treated as `FlowItem[].json` only (often an array). Schema uses the first item;
   * table one row per item; JSON renders a top-level `[...]` (or `[]`).
   */
  valueKind?: 'executionItems' | 'json';
  /** When true, only the schema/table/json body is rendered (parent supplies chrome). */
  hideHeader?: boolean;
  /** When set, drag hints and payloads use inbound `_json` vs `_node[…].json` consistently with the modal node. */
  expressionConfigNodeId?: string;
}> = ({
  title,
  value,
  dragSource,
  defaultMode = 'json',
  mode: controlledMode,
  onModeChange,
  valueKind = 'json',
  hideHeader = false,
  expressionConfigNodeId,
}) => {
  const [uncontrolledMode, setUncontrolledMode] = useState<'schema' | 'table' | 'json'>(defaultMode);
  const mode = controlledMode ?? uncontrolledMode;
  const setMode = (next: 'schema' | 'table' | 'json') => {
    onModeChange?.(next);
    if (controlledMode == null) setUncontrolledMode(next);
  };

  const executionItems = useMemo(
    () => (valueKind === 'executionItems' ? coerceExecutionItems(value) : []),
    [value, valueKind],
  );

  const schemaRoot = useMemo(() => {
    if (valueKind === 'executionItems') {
      return executionItems.length === 0 ? undefined : executionItems[0];
    }
    if (Array.isArray(value) && value.length > 0) return value[0];
    return value;
  }, [value, valueKind, executionItems]);

  const table = useMemo(() => {
    if (valueKind === 'executionItems') {
      return convertToTableLikeN8n(executionItems, TABLE_MATERIALIZATION_CAP);
    }
    if (Array.isArray(value)) {
      return convertToTableLikeN8n(value, TABLE_MATERIALIZATION_CAP);
    }
    return null;
  }, [value, valueKind, executionItems]);

  const [tablePageIndex, setTablePageIndex] = useState(0);
  const [tablePageSize, setTablePageSize] = useState<(typeof TABLE_PAGE_SIZE_OPTIONS)[number]>(25);

  useEffect(() => {
    setTablePageIndex(0);
  }, [table, tablePageSize]);

  const jsonText = useMemo(() => {
    if (valueKind === 'executionItems') return stringifyJson(executionItems);
    return stringifyJson(value);
  }, [value, valueKind, executionItems]);

  const itemsCountLabel = useMemo(() => {
    if (valueKind === 'executionItems') {
      const n = executionItems.length;
      return `${n} ${n === 1 ? 'Item' : 'Items'}`;
    }
    if (Array.isArray(value)) {
      const n = value.length;
      return `${n} ${n === 1 ? 'Item' : 'Items'}`;
    }
    return null;
  }, [executionItems, value, valueKind]);

  const startDrag = (e: React.DragEvent, path: JsonPath) => {
    const dn = dragSource.nodeDisplayName?.trim();
    const payload: FlowValueDragPayload = {
      kind: 'jsonPath',
      source: dragSource.source,
      nodeId: dragSource.nodeId,
      ...(dn ? { nodeDisplayName: dn } : {}),
      path,
      exampleValue: getAtPath(schemaRoot ?? null, path),
    };
    e.dataTransfer.setData(FLOW_VALUE_MIME, JSON.stringify(payload));
    e.dataTransfer.effectAllowed = 'copy';
  };

  const isExecution = valueKind === 'executionItems';

  const tablePagination = useMemo(() => {
    if (!table || table.rows.length === 0) return null;
    const totalRows = table.rows.length;
    const pageCount = Math.max(1, Math.ceil(totalRows / tablePageSize));
    const safePage = Math.min(Math.max(tablePageIndex, 0), pageCount - 1);
    const start = safePage * tablePageSize;
    const end = Math.min(start + tablePageSize, totalRows);
    const slice = table.rows.slice(start, start + tablePageSize);
    return { totalRows, pageCount, safePage, start, end, slice };
  }, [table, tablePageIndex, tablePageSize]);

  return (
    <div className="min-w-0">
      {!hideHeader && (
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="min-w-0">
            {title && <div className="truncate text-[11px] font-semibold text-gray-700">{title}</div>}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <IoDataModeTabs mode={mode} onChange={setMode} />
            {itemsCountLabel != null ? (
              <span className="whitespace-nowrap text-[11px] font-medium tabular-nums text-gray-500">{itemsCountLabel}</span>
            ) : null}
          </div>
        </div>
      )}

      {mode === 'schema' && (
        <div className="rounded border border-[#eceff2] bg-white">
          <div className="max-h-[360px] overflow-auto">
            {isExecution && executionItems.length === 0 ? (
              <div className="p-3 text-sm text-gray-500">No items.</div>
            ) : (
              <SchemaFirstItemFields schemaRoot={schemaRoot ?? null} startDrag={startDrag} />
            )}
          </div>
        </div>
      )}

      {mode === 'table' && (
        <div className="rounded border border-[#eceff2] bg-white">
          {isExecution && executionItems.length === 0 ? (
            <div className="p-3 text-sm text-gray-500">No items.</div>
          ) : table == null ? (
            <div className="p-3 text-sm text-gray-500">
              {isExecution ? 'No tabular preview for these items.' : 'Not a table: expected an array of objects.'}
            </div>
          ) : (
            <>
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
                          title={`Drag to insert expression: ${payloadToExpression(
                              {
                                kind: 'jsonPath',
                                source: dragSource.source,
                                nodeId: dragSource.nodeId,
                                ...(dragSource.nodeDisplayName?.trim()
                                  ? { nodeDisplayName: dragSource.nodeDisplayName.trim() }
                                  : {}),
                                path: [c],
                                exampleValue: null,
                              },
                              expressionConfigNodeId,
                            )}`}
                        >
                          <span className="cursor-grab active:cursor-grabbing">{c}</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(tablePagination?.slice ?? []).map((row, idx) => (
                      <tr key={tablePagination!.start + idx} className="odd:bg-white even:bg-gray-50/40">
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
              {tablePagination && (
                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[#eceff2] px-2 py-2 text-[11px] text-gray-600">
                  <div className="min-w-0 space-y-0.5">
                    <div className="text-gray-700">
                      Rows {tablePagination.start + 1}–{tablePagination.end} of {tablePagination.totalRows}
                      <span className="text-gray-500">
                        {' '}
                        (page {tablePagination.safePage + 1}/{tablePagination.pageCount})
                      </span>
                    </div>
                    {table.omittedTailItemCount != null && table.omittedTailItemCount > 0 && (
                      <div className="max-w-xl text-[10px] text-amber-800">
                        Another {table.omittedTailItemCount} item(s) exceed the UI table cap ({TABLE_MATERIALIZATION_CAP}). Use Download to view the full result.
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <label className="flex items-center gap-1 whitespace-nowrap text-gray-600">
                      Per page
                      <select
                        className="max-w-[5.5rem] rounded-md border border-gray-200 bg-white px-1.5 py-1 text-[11px] text-gray-900 shadow-sm"
                        aria-label="Rows per page"
                        value={tablePageSize}
                        onChange={(e) => setTablePageSize(Number(e.target.value) as (typeof TABLE_PAGE_SIZE_OPTIONS)[number])}
                      >
                        {TABLE_PAGE_SIZE_OPTIONS.map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="inline-flex items-center gap-0.5">
                      <button
                        type="button"
                        className="rounded-md border border-gray-200 bg-white p-1 text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                        aria-label="Previous page"
                        disabled={tablePagination.safePage <= 0}
                        onClick={() => setTablePageIndex(Math.max(tablePagination.safePage - 1, 0))}
                      >
                        <ChevronLeftIcon className="h-4 w-4" aria-hidden />
                      </button>
                      <button
                        type="button"
                        className="rounded-md border border-gray-200 bg-white p-1 text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                        aria-label="Next page"
                        disabled={tablePagination.safePage >= tablePagination.pageCount - 1}
                        onClick={() =>
                          setTablePageIndex(Math.min(tablePagination.safePage + 1, tablePagination.pageCount - 1))
                        }
                      >
                        <ChevronRightIcon className="h-4 w-4" aria-hidden />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {mode === 'json' && (
        <div className="rounded border border-[#eceff2] bg-white">
          <Editor
            height="360px"
            language="json"
            value={jsonText}
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
