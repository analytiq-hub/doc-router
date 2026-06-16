import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Editor from '@monaco-editor/react';
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline';
import type { FlowExecutionBlobContext } from './flowExecutionBlob';
import { fetchFlowExecutionBlob, isFetchableExecutionBlobStorageId } from './flowExecutionBlob';

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
 * - **`source === 'nodeOutput'`** → **`_node[display].json`** when multiple inbound parents exist or the drag is not from the sole parent.
 *   When **exactly one edge** feeds this node and you drag from **that parent's** output, use **`_json`** — same row as execute-time inbound data.
 *
 * `@param outputSlotIndex` defaults to first output handle (matches current single-slot wiring in the modal).
 */
export function payloadToExpression(
  p: FlowValueDragPayload,
  configuringNodeId?: string,
  outputSlotIndex = 0,
  opts?: { soleInboundParentNodeId?: string | null },
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

  const sole = opts?.soleInboundParentNodeId;
  const useSoleParentInboundJson =
    sole != null &&
    configuringNodeId != null &&
    p.source === 'nodeOutput' &&
    p.nodeId === sole &&
    p.nodeId !== configuringNodeId;

  if (useSoleParentInboundJson) {
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

/** One row per item; columns grow in first-seen key order (`convertToTable`-style widening). */
const TABLE_MAX_KEYS_PER_ROW = 40;
/** Upper bound on items passed into table conversion — pagination displays within this window. */
const TABLE_MATERIALIZATION_CAP = 25_000;

const TABLE_PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const;

function coerceExecutionItems(raw: unknown): unknown[] {
  if (raw == null) return [];
  return Array.isArray(raw) ? raw : [raw];
}

/**
 * Walk items in order; columns are appended when new keys appear; missing keys are `undefined`
 * and earlier rows are padded with trailing `undefined`s for columns added later.
 * Skips non-plain-object items.
 */
function convertItemsToGrowingColumnTable(items: unknown[], maxItems: number): TableData | null {
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

    const leftEntryColumns = [...entryColumns];
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

export type IoDataMode = 'schema' | 'table' | 'json' | 'binary';

/** Shared Schema / Table / JSON / Binary toggle (Binary appears only when `showBinary`). */
export function IoDataModeTabs({
  mode,
  onChange,
  showBinary = false,
}: {
  mode: IoDataMode;
  onChange: (next: IoDataMode) => void;
  showBinary?: boolean;
}) {
  const modes: IoDataMode[] = showBinary ? ['schema', 'table', 'json', 'binary'] : ['schema', 'table', 'json'];
  const label = (m: IoDataMode) =>
    m === 'schema' ? 'Schema' : m === 'table' ? 'Table' : m === 'json' ? 'JSON' : 'Binary';
  return (
    <div className="inline-flex rounded-md border border-gray-200 bg-white p-0.5 text-[11px]">
      {modes.map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          title={label(m)}
          aria-label={label(m)}
          className={[
            'rounded px-2 py-1 text-[10px] font-semibold leading-none',
            mode === m ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-50',
          ].join(' ')}
        >
          {label(m)}
        </button>
      ))}
    </div>
  );
}

function formatFileSizeBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10_240 ? 2 : 1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(n < 10_485_760 ? 2 : 1)} MB`;
}

function fileExtensionFromName(name: string | undefined): string {
  if (!name || typeof name !== 'string') return '—';
  const i = name.lastIndexOf('.');
  if (i <= 0 || i === name.length - 1) return '—';
  return name.slice(i + 1).toLowerCase();
}

/** When ``file_name`` is absent (e.g. Postman raw CSV), infer a conventional extension from MIME. */
function fileExtensionHintFromMime(mime: string | undefined): string | null {
  if (!mime || typeof mime !== 'string') return null;
  const base = mime.split(';')[0].trim().toLowerCase();
  const map: Record<string, string> = {
    'text/csv': 'csv',
    'application/csv': 'csv',
    'text/tab-separated-values': 'tsv',
    'text/tsv': 'tsv',
    'application/pdf': 'pdf',
    'application/json': 'json',
    'application/xml': 'xml',
    'text/xml': 'xml',
    'application/zip': 'zip',
    'application/gzip': 'gz',
    'application/x-gzip': 'gz',
    'application/octet-stream': 'bin',
  };
  if (map[base]) return map[base];
  if (base.startsWith('text/')) return base.slice('text/'.length).replace(/[^a-z0-9+.@-]/gi, '') || null;
  return null;
}

function displayFileExtension(fileName: string | undefined, mimeType: string | undefined): string {
  const fromName = fileExtensionFromName(fileName);
  if (fromName !== '—') return fromName;
  const fromMime = fileExtensionHintFromMime(mimeType);
  return fromMime ?? '—';
}

type BinaryRefLike = {
  mime_type?: string;
  file_name?: string;
  storage_id?: string;
  file_size?: number;
};

function coerceBinaryRefLike(v: unknown): BinaryRefLike | null {
  if (v == null || typeof v !== 'object' || Array.isArray(v)) return null;
  const o = v as Record<string, unknown>;
  const storage_id = o.storage_id;
  if (typeof storage_id !== 'string' || !storage_id.trim()) return null;
  const mime_type = typeof o.mime_type === 'string' ? o.mime_type : undefined;
  const file_name = typeof o.file_name === 'string' ? o.file_name : undefined;
  const fs = o.file_size;
  const file_size = typeof fs === 'number' && Number.isFinite(fs) ? fs : undefined;
  return { mime_type, file_name, storage_id: storage_id.trim(), file_size };
}

function binaryAttachmentRows(itemsBinaries: Array<Record<string, unknown>>): Array<{
  itemIndex: number;
  propertyName: string;
  ref: BinaryRefLike;
}> {
  const rows: Array<{ itemIndex: number; propertyName: string; ref: BinaryRefLike }> = [];
  itemsBinaries.forEach((bin, itemIndex) => {
    if (!bin || typeof bin !== 'object') return;
    for (const [propertyName, raw] of Object.entries(bin)) {
      const ref = coerceBinaryRefLike(raw);
      if (ref) rows.push({ itemIndex, propertyName, ref });
    }
  });
  return rows;
}

/** Same categories as the reference workflow editor: only these open the in-panel viewer. */
type BinaryViewKind = 'image' | 'video' | 'audio' | 'pdf' | 'json' | 'html' | 'text';

function inferBinaryViewKind(mime: string | undefined, fileName: string | undefined): BinaryViewKind | null {
  const m = (mime || '').split(';')[0].trim().toLowerCase();
  const ext = fileExtensionFromName(fileName);
  const extHint = fileExtensionHintFromMime(mime);
  const e = ext !== '—' ? ext : extHint;

  if (m.startsWith('image/')) return 'image';
  if (m.startsWith('video/')) return 'video';
  if (m.startsWith('audio/')) return 'audio';
  if (m === 'application/pdf' || e === 'pdf') return 'pdf';
  if (m === 'application/json' || m.endsWith('+json') || e === 'json') return 'json';
  if (m === 'text/html' || e === 'html' || e === 'htm') return 'html';
  if (m.startsWith('text/')) return 'text';
  if (m === 'application/xml' || m === 'text/xml' || e === 'xml') return 'text';
  return null;
}

type IoBinaryPreview =
  | { variant: 'image'; blobUrl: string; title: string }
  | { variant: 'video'; blobUrl: string; mime: string; title: string }
  | { variant: 'audio'; blobUrl: string; mime: string; title: string }
  | { variant: 'embed'; blobUrl: string; mime: string; title: string }
  | { variant: 'json'; body: string; title: string }
  | { variant: 'html'; body: string; title: string }
  | { variant: 'text'; body: string; title: string };

function IoBinaryPreviewOverlay({
  preview,
  onClose,
}: {
  preview: IoBinaryPreview;
  onClose: () => void;
}) {
  return (
    <div className="absolute inset-0 z-20 flex min-h-[220px] flex-col overflow-hidden rounded-md border border-[#eceff2] bg-white shadow-md">
      <div className="flex shrink-0 items-center gap-2 border-b border-[#eceff2] bg-[#fafbfc] px-2 py-1.5">
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center gap-1 rounded border border-gray-200 bg-white px-2 py-1 text-[11px] font-semibold text-gray-800 shadow-sm hover:bg-gray-50"
        >
          <ChevronLeftIcon className="h-3.5 w-3.5" strokeWidth={2} />
          Back
        </button>
        <span className="min-w-0 truncate text-[11px] font-semibold text-gray-900" title={preview.title}>
          {preview.title}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-2">
        {preview.variant === 'image' ? (
          <div className="flex justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview.blobUrl} alt="" className="max-h-[min(70vh,520px)] max-w-full object-contain" />
          </div>
        ) : null}
        {preview.variant === 'video' ? (
          <video controls className="max-h-[min(70vh,520px)] w-full max-w-full" preload="metadata">
            <source src={preview.blobUrl} type={preview.mime} />
          </video>
        ) : null}
        {preview.variant === 'audio' ? (
          <audio controls className="w-full" preload="metadata">
            <source src={preview.blobUrl} type={preview.mime} />
          </audio>
        ) : null}
        {preview.variant === 'embed' ? (
          <embed
            src={preview.blobUrl}
            type={preview.mime}
            title={preview.title}
            className="h-[min(70vh,520px)] w-full border-0"
          />
        ) : null}
        {preview.variant === 'json' ? (
          <pre className="whitespace-pre-wrap break-words rounded border border-gray-100 bg-gray-50 p-2 font-mono text-[11px] leading-relaxed text-gray-900">
            {preview.body}
          </pre>
        ) : null}
        {preview.variant === 'text' ? (
          <pre className="whitespace-pre-wrap break-words rounded border border-gray-100 bg-gray-50 p-2 font-mono text-[11px] leading-relaxed text-gray-900">
            {preview.body}
          </pre>
        ) : null}
        {preview.variant === 'html' ? (
          <iframe
            title={preview.title}
            sandbox=""
            srcDoc={preview.body}
            className="h-[min(70vh,520px)] w-full rounded border border-gray-200 bg-white"
          />
        ) : null}
      </div>
    </div>
  );
}

const IoBinaryPanel: React.FC<{
  itemsBinaries: Array<Record<string, unknown>>;
  itemCount: number;
  flowBlobDownloadContext: FlowExecutionBlobContext | null;
}> = ({ itemsBinaries, itemCount, flowBlobDownloadContext }) => {
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<IoBinaryPreview | null>(null);
  const previewBlobUrlRef = useRef<string | null>(null);

  const rows = useMemo(() => binaryAttachmentRows(itemsBinaries), [itemsBinaries]);

  const closePreview = useCallback(() => {
    if (previewBlobUrlRef.current) {
      URL.revokeObjectURL(previewBlobUrlRef.current);
      previewBlobUrlRef.current = null;
    }
    setPreview(null);
  }, []);

  useEffect(
    () => () => {
      if (previewBlobUrlRef.current) {
        URL.revokeObjectURL(previewBlobUrlRef.current);
        previewBlobUrlRef.current = null;
      }
    },
    [],
  );

  const openPreview = useCallback(
    async (cardKey: string, ref: BinaryRefLike, title: string) => {
      const viewKind = inferBinaryViewKind(ref.mime_type, ref.file_name);
      if (!viewKind || !flowBlobDownloadContext) return;

      setError(null);
      setBusyKey(cardKey);
      try {
        if (previewBlobUrlRef.current) {
          URL.revokeObjectURL(previewBlobUrlRef.current);
          previewBlobUrlRef.current = null;
        }

        const { blob } = await fetchFlowExecutionBlob(flowBlobDownloadContext, ref.storage_id!, { action: 'view' });
        const effectiveMime =
          blob.type && blob.type.trim() ? blob.type.split(';')[0].trim() : ref.mime_type || 'application/octet-stream';

        if (viewKind === 'json') {
          const raw = await blob.text();
          let body: string;
          try {
            body = JSON.stringify(JSON.parse(raw), null, 2);
          } catch {
            body = raw;
          }
          setPreview({ variant: 'json', body, title });
          return;
        }
        if (viewKind === 'html') {
          setPreview({ variant: 'html', body: await blob.text(), title });
          return;
        }
        if (viewKind === 'text') {
          setPreview({ variant: 'text', body: await blob.text(), title });
          return;
        }

        const blobUrl = URL.createObjectURL(blob);
        previewBlobUrlRef.current = blobUrl;

        if (viewKind === 'image') {
          setPreview({ variant: 'image', blobUrl, title });
        } else if (viewKind === 'video') {
          setPreview({ variant: 'video', blobUrl, mime: effectiveMime, title });
        } else if (viewKind === 'audio') {
          setPreview({ variant: 'audio', blobUrl, mime: effectiveMime, title });
        } else {
          setPreview({ variant: 'embed', blobUrl, mime: effectiveMime, title });
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Failed to load binary');
      } finally {
        setBusyKey(null);
      }
    },
    [flowBlobDownloadContext],
  );

  const downloadBlob = useCallback(
    async (key: string, storageId: string, fallbackName: string | undefined) => {
      if (!flowBlobDownloadContext) {
        setError('Run the workflow and select an execution to download binaries.');
        return;
      }
      setError(null);
      setBusyKey(key);
      try {
        const { blob, downloadName } = await fetchFlowExecutionBlob(flowBlobDownloadContext, storageId, {
          action: 'download',
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = (downloadName && downloadName.trim()) || fallbackName || 'attachment';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Failed to load binary');
      } finally {
        setBusyKey(null);
      }
    },
    [flowBlobDownloadContext],
  );

  if (rows.length === 0) {
    return <div className="p-3 text-sm text-gray-500">No binary attachments on these items.</div>;
  }

  const showItemLabels = itemCount > 1;

  return (
    <div className="relative min-h-[120px]">
      {preview ? <IoBinaryPreviewOverlay preview={preview} onClose={closePreview} /> : null}
      <div className="max-h-[360px] space-y-3 overflow-auto">
        {error ? <div className="rounded border border-red-200 bg-red-50 px-2 py-1.5 text-[11px] text-red-900">{error}</div> : null}
        {!flowBlobDownloadContext ? (
          <div className="text-[11px] text-gray-500">
            View and Download need a saved execution context (run the flow from the editor or open an execution).
          </div>
        ) : null}
        {rows.map((r) => {
          const sid = typeof r.ref.storage_id === 'string' ? r.ref.storage_id : '';
          const cardKey = `${r.itemIndex}:${r.propertyName}:${sid}`;
          const ext = displayFileExtension(r.ref.file_name, r.ref.mime_type);
          const mime = r.ref.mime_type && r.ref.mime_type.trim() ? r.ref.mime_type : '—';
          const sizeLabel = r.ref.file_size != null ? formatFileSizeBytes(r.ref.file_size) : '—';
          const displayName = r.ref.file_name?.trim() || r.propertyName;
          const canFetch = Boolean(flowBlobDownloadContext && isFetchableExecutionBlobStorageId(sid));
          const busy = busyKey === cardKey;
          const viewKind = inferBinaryViewKind(r.ref.mime_type, r.ref.file_name);
          const canView = Boolean(canFetch && viewKind);
          return (
            <div key={cardKey} className="rounded-md border border-[#eceff2] bg-white p-3 shadow-sm">
              {showItemLabels ? (
                <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-gray-400">
                  Item {r.itemIndex + 1}
                  <span className="font-mono normal-case text-gray-600"> · {r.propertyName}</span>
                </div>
              ) : (
                <div className="mb-2 text-[11px] font-semibold text-gray-800">{r.propertyName}</div>
              )}
              <div className="grid grid-cols-[max-content_minmax(0,1fr)] items-baseline gap-x-2 gap-y-1.5 text-[11px]">
                <span className="whitespace-nowrap font-medium text-gray-500">File Name</span>
                <span className="min-w-0 truncate font-mono text-gray-900" title={displayName}>
                  {displayName}
                </span>
                <span className="whitespace-nowrap font-medium text-gray-500">File Extension</span>
                <span className="min-w-0 truncate font-mono text-gray-900">{ext}</span>
                <span className="whitespace-nowrap font-medium text-gray-500">Mime Type</span>
                <span className="min-w-0 truncate font-mono text-gray-900" title={mime}>
                  {mime}
                </span>
                <span className="whitespace-nowrap font-medium text-gray-500">File Size</span>
                <span className="min-w-0 truncate font-mono text-gray-900">{sizeLabel}</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {canView ? (
                  <button
                    type="button"
                    disabled={!canFetch || busy}
                    onClick={() => void openPreview(cardKey, r.ref, displayName)}
                    className="rounded-md bg-rose-500 px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm transition hover:bg-rose-600 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {busy ? '…' : 'View'}
                  </button>
                ) : null}
                <button
                  type="button"
                  disabled={!canFetch || busy}
                  onClick={() => void downloadBlob(cardKey, r.ref.storage_id!, r.ref.file_name)}
                  className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-gray-800 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy ? '…' : 'Download'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

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

/** Schema mode: item count in header; body shows fields of the first item only — no `_json` root row. */
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
  defaultMode?: IoDataMode;
  mode?: IoDataMode;
  onModeChange?: (next: IoDataMode) => void;
  /**
   * `executionItems`: value is treated as `FlowItem[].json` only (often an array). Schema uses the first item;
   * table one row per item; JSON renders a top-level `[...]` (or `[]`).
   */
  valueKind?: 'executionItems' | 'json';
  /**
   * When `valueKind` is `executionItems`, parallel `FlowItem.binary` maps (same length as rows; omit or pad with `{}`).
   */
  executionItemsBinaries?: Array<Record<string, unknown>> | null;
  /** Enables View/Download using `fetchFlowExecutionBlob` for execution-scoped binary refs. */
  flowBlobDownloadContext?: FlowExecutionBlobContext | null;
  /** When true, only the schema/table/json body is rendered (parent supplies chrome). */
  hideHeader?: boolean;
  /** When set, drag hints and payloads use inbound `_json` vs `_node[…].json` consistently with the modal node. */
  expressionConfigNodeId?: string;
  /**
   * Node id of the only inbound edge source for `expressionConfigNodeId`. When set, drags from **that** node's output
   * use `_json` (same as runtime inbound row); other upstream sections still use `_node[…]`.
   */
  soleInboundParentNodeId?: string | null;
  /** Schema/table hint, e.g. ``from Manual trigger · item 0``. */
  lineageCaption?: string | null;
}> = ({
  title,
  value,
  dragSource,
  defaultMode = 'json',
  mode: controlledMode,
  onModeChange,
  valueKind = 'json',
  executionItemsBinaries = null,
  flowBlobDownloadContext = null,
  hideHeader = false,
  expressionConfigNodeId,
  soleInboundParentNodeId = null,
  lineageCaption = null,
}) => {
  const [uncontrolledMode, setUncontrolledMode] = useState<IoDataMode>(defaultMode);
  const mode = controlledMode ?? uncontrolledMode;
  const setMode = (next: IoDataMode) => {
    onModeChange?.(next);
    if (controlledMode == null) setUncontrolledMode(next);
  };

  const executionItems = useMemo(
    () => (valueKind === 'executionItems' ? coerceExecutionItems(value) : []),
    [value, valueKind],
  );

  const paddedItemBinaries = useMemo(() => {
    if (valueKind !== 'executionItems') return [];
    const n = executionItems.length;
    const src = executionItemsBinaries ?? [];
    const out: Record<string, unknown>[] = [];
    for (let i = 0; i < n; i++) {
      const b = src[i];
      out.push(b != null && typeof b === 'object' && !Array.isArray(b) ? (b as Record<string, unknown>) : {});
    }
    return out;
  }, [valueKind, executionItems.length, executionItemsBinaries]);

  const showBinaryTab = useMemo(() => {
    if (valueKind !== 'executionItems') return false;
    return paddedItemBinaries.some((b) => Object.keys(b).length > 0);
  }, [valueKind, paddedItemBinaries]);

  useEffect(() => {
    if (mode !== 'binary' || showBinaryTab) return;
    let cancelled = false;
    const id = requestAnimationFrame(() => {
      if (cancelled) return;
      onModeChange?.('json');
      if (controlledMode == null) setUncontrolledMode('json');
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(id);
    };
  }, [mode, showBinaryTab, controlledMode, onModeChange]);

  const schemaRoot = useMemo(() => {
    if (valueKind === 'executionItems') {
      return executionItems.length === 0 ? undefined : executionItems[0];
    }
    if (Array.isArray(value) && value.length > 0) return value[0];
    return value;
  }, [value, valueKind, executionItems]);

  const table = useMemo(() => {
    if (valueKind === 'executionItems') {
      return convertItemsToGrowingColumnTable(executionItems, TABLE_MATERIALIZATION_CAP);
    }
    if (Array.isArray(value)) {
      return convertItemsToGrowingColumnTable(value, TABLE_MATERIALIZATION_CAP);
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
            <IoDataModeTabs mode={mode} onChange={setMode} showBinary={showBinaryTab} />
            {itemsCountLabel != null ? (
              <span className="whitespace-nowrap text-[11px] font-medium tabular-nums text-gray-500">{itemsCountLabel}</span>
            ) : null}
          </div>
        </div>
      )}

      {mode === 'schema' && (
        <div className="rounded border border-[#eceff2] bg-white">
          {lineageCaption ? (
            <div className="border-b border-[#eceff2] px-2 py-1.5 text-[11px] text-gray-600">{lineageCaption}</div>
          ) : null}
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
                              0,
                              { soleInboundParentNodeId },
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

      {mode === 'binary' && showBinaryTab && (
        <div className="rounded border border-[#eceff2] bg-[#fafbfc]/60 p-2">
          <IoBinaryPanel
            itemsBinaries={paddedItemBinaries}
            itemCount={executionItems.length}
            flowBlobDownloadContext={flowBlobDownloadContext ?? null}
          />
        </div>
      )}
    </div>
  );
};
