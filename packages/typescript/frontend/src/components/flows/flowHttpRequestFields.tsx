'use client';

import React, { useMemo } from 'react';
import { Switch } from '@headlessui/react';
import type { FlowNode } from '@docrouter/sdk';
import { flowInputClass, flowLabelClass, flowSelectClass } from './flowUiClasses';
import { FLOW_VALUE_MIME, type FlowValueDragPayload } from './IoViewer';

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] as const;
const BODY_MODES = ['none', 'json', 'json_keypair', 'form_urlencoded', 'raw'] as const;

const HTTP_DEFAULTS: Record<string, unknown> = {
  method: 'GET',
  url: '',
  query_params: [],
  headers: [],
  body_mode: 'none',
  body_json: '',
  body_params: [],
  body_raw: '',
  body_content_type: 'text/plain',
  full_response: false,
  never_error: false,
  follow_redirects: true,
  timeout_seconds: 30,
};

const switchTrackClass =
  'group relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent bg-gray-200 transition-colors data-[checked]:bg-violet-600 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-1';
const switchThumbClass =
  'inline-block h-3.5 w-3.5 translate-x-0.5 rounded-full bg-white shadow transition group-data-[checked]:translate-x-4';

type Pair = { name: string; value: string };

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

function payloadToExpression(p: FlowValueDragPayload): string {
  let expr = `_node["${p.nodeId}"]["json"]`;
  for (const seg of p.path) {
    expr += typeof seg === 'number' ? `[${seg}]` : `["${String(seg)}"]`;
  }
  return `=${expr}`;
}

function coercePairs(raw: unknown): Pair[] {
  if (!Array.isArray(raw)) return [];
  const out: Pair[] = [];
  for (const row of raw) {
    if (row && typeof row === 'object' && 'name' in row) {
      const o = row as { name?: unknown; value?: unknown };
      out.push({ name: typeof o.name === 'string' ? o.name : '', value: typeof o.value === 'string' ? o.value : '' });
    }
  }
  return out;
}

const PairEditor: React.FC<{
  label: string;
  pairs: Pair[];
  readOnly: boolean;
  onChange: (next: Pair[]) => void;
}> = ({ label, pairs, readOnly, onChange }) => (
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
              n[i] = { ...n[i], name: e.target.value || n[i].name, value: payloadToExpression(p) };
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

/**
 * Structured editor for `flows.http_request` parameters (matches backend JSON Schema).
 */
export const FlowHttpRequestParameterFields: React.FC<{
  node: FlowNode;
  onChange: (patch: Partial<FlowNode>) => void;
  readOnly?: boolean;
}> = ({ node, onChange, readOnly = false }) => {
  const params = useMemo(() => {
    const p = node.parameters || {};
    return { ...HTTP_DEFAULTS, ...p } as Record<string, unknown>;
  }, [node.parameters]);

  const setParams = (patch: Record<string, unknown>) => {
    onChange({ parameters: { ...params, ...patch } });
  };

  const method = typeof params.method === 'string' ? params.method : 'GET';
  const url = typeof params.url === 'string' ? params.url : '';
  const bodyMode =
    typeof params.body_mode === 'string' && (BODY_MODES as readonly string[]).includes(params.body_mode)
      ? params.body_mode
      : 'none';
  const bodyJson = typeof params.body_json === 'string' ? params.body_json : '';
  const bodyRaw = typeof params.body_raw === 'string' ? params.body_raw : '';
  const bodyCt = typeof params.body_content_type === 'string' ? params.body_content_type : 'text/plain';
  const queryParams = coercePairs(params.query_params);
  const headers = coercePairs(params.headers);
  const bodyParams = coercePairs(params.body_params);
  const timeout = typeof params.timeout_seconds === 'number' ? params.timeout_seconds : 30;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <div>
        <label className={flowLabelClass} htmlFor="http-method">
          method
        </label>
        <select
          id="http-method"
          className={flowSelectClass}
          disabled={readOnly}
          value={method}
          onChange={(e) => setParams({ method: e.target.value })}
        >
          {HTTP_METHODS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className={flowLabelClass} htmlFor="http-url">
          url
        </label>
        <input
          id="http-url"
          className={flowInputClass}
          readOnly={readOnly}
          value={url}
          placeholder="https://… or =expression"
          onChange={(e) => setParams({ url: e.target.value })}
          onDragOver={(e) => {
            if (readOnly) return;
            if (e.dataTransfer.types.includes(FLOW_VALUE_MIME)) e.preventDefault();
          }}
          onDrop={(e) => {
            if (readOnly) return;
            const p = parseDropPayload(e);
            if (!p) return;
            e.preventDefault();
            setParams({ url: payloadToExpression(p) });
          }}
        />
      </div>

      <PairEditor
        label="query_params"
        pairs={queryParams}
        readOnly={readOnly}
        onChange={(next) => setParams({ query_params: next })}
      />
      <PairEditor label="headers" pairs={headers} readOnly={readOnly} onChange={(next) => setParams({ headers: next })} />

      <div>
        <label className={flowLabelClass} htmlFor="http-body-mode">
          body_mode
        </label>
        <select
          id="http-body-mode"
          className={flowSelectClass}
          disabled={readOnly}
          value={bodyMode}
          onChange={(e) => setParams({ body_mode: e.target.value })}
        >
          {BODY_MODES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>

      {bodyMode === 'json' && (
        <div>
          <label className={flowLabelClass} htmlFor="http-body-json">
            body_json
          </label>
          <textarea
            id="http-body-json"
            className={flowInputClass + ' min-h-[120px] font-mono text-[11px]'}
            readOnly={readOnly}
            value={bodyJson}
            placeholder={'JSON string or =expression'}
            onChange={(e) => setParams({ body_json: e.target.value })}
          />
        </div>
      )}

      {(bodyMode === 'json_keypair' || bodyMode === 'form_urlencoded') && (
        <PairEditor
          label="body_params"
          pairs={bodyParams}
          readOnly={readOnly}
          onChange={(next) => setParams({ body_params: next })}
        />
      )}

      {bodyMode === 'raw' && (
        <>
          <div>
            <label className={flowLabelClass} htmlFor="http-body-raw">
              body_raw
            </label>
            <textarea
              id="http-body-raw"
              className={flowInputClass + ' min-h-[100px] font-mono text-[11px]'}
              readOnly={readOnly}
              value={bodyRaw}
              onChange={(e) => setParams({ body_raw: e.target.value })}
            />
          </div>
          <div>
            <label className={flowLabelClass} htmlFor="http-body-ct">
              body_content_type
            </label>
            <input
              id="http-body-ct"
              className={flowInputClass}
              readOnly={readOnly}
              value={bodyCt}
              onChange={(e) => setParams({ body_content_type: e.target.value })}
            />
          </div>
        </>
      )}

      <div className="flex items-center justify-between gap-3 rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2">
        <span className="text-sm text-gray-800">full_response</span>
        <Switch
          checked={Boolean(params.full_response)}
          onChange={(v) => setParams({ full_response: v })}
          disabled={readOnly}
          className={switchTrackClass}
        >
          <span className={switchThumbClass} aria-hidden />
        </Switch>
      </div>
      <div className="flex items-center justify-between gap-3 rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2">
        <span className="text-sm text-gray-800">never_error</span>
        <Switch
          checked={Boolean(params.never_error)}
          onChange={(v) => setParams({ never_error: v })}
          disabled={readOnly}
          className={switchTrackClass}
        >
          <span className={switchThumbClass} aria-hidden />
        </Switch>
      </div>
      <div className="flex items-center justify-between gap-3 rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2">
        <span className="text-sm text-gray-800">follow_redirects</span>
        <Switch
          checked={Boolean(params.follow_redirects)}
          onChange={(v) => setParams({ follow_redirects: v })}
          disabled={readOnly}
          className={switchTrackClass}
        >
          <span className={switchThumbClass} aria-hidden />
        </Switch>
      </div>
      <div>
        <label className={flowLabelClass} htmlFor="http-timeout">
          timeout_seconds
        </label>
        <input
          id="http-timeout"
          type="number"
          min={1}
          className={flowInputClass}
          readOnly={readOnly}
          value={timeout}
          onChange={(e) => setParams({ timeout_seconds: Number(e.target.value) })}
        />
      </div>
    </div>
  );
};
