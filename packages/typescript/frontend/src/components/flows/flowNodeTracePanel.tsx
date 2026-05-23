'use client';

import React, { useMemo, useState } from 'react';
import { NodeRunErrorDetails } from './flowNodeRunErrorDetails';

export type FlowTraceEvent = {
  ts?: string;
  level?: string;
  kind?: string;
  message?: string;
  detail?: Record<string, unknown>;
};

export type TraceEventFilter = 'all' | 'errors' | 'http';

function asTraceEvents(raw: unknown): FlowTraceEvent[] {
  if (!Array.isArray(raw)) return [];
  const out: FlowTraceEvent[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const rec = item as Record<string, unknown>;
    out.push({
      ts: typeof rec.ts === 'string' ? rec.ts : undefined,
      level: typeof rec.level === 'string' ? rec.level : undefined,
      kind: typeof rec.kind === 'string' ? rec.kind : undefined,
      message: typeof rec.message === 'string' ? rec.message : undefined,
      detail: rec.detail && typeof rec.detail === 'object' ? (rec.detail as Record<string, unknown>) : undefined,
    });
  }
  return out;
}

function matchesTraceFilter(ev: FlowTraceEvent, filter: TraceEventFilter): boolean {
  if (filter === 'all') return true;
  if (filter === 'http') return ev.kind === 'http';
  const level = (ev.level ?? '').toLowerCase();
  if (filter === 'errors') {
    return level === 'error' || level === 'warn' || ev.kind === 'http';
  }
  return true;
}

/** Node-level trace tab: error envelope, code logs, and structured ``trace[]`` events. */
export const FlowNodeTracePanel: React.FC<{
  nodeError: unknown;
  executionError?: Record<string, unknown> | null;
  codeLogs?: string[];
  traceEvents?: unknown;
}> = ({ nodeError, executionError, codeLogs, traceEvents }) => {
  const [eventFilter, setEventFilter] = useState<TraceEventFilter>('all');
  const events = asTraceEvents(traceEvents);
  const filteredEvents = useMemo(
    () => events.filter((ev) => matchesTraceFilter(ev, eventFilter)),
    [events, eventFilter],
  );
  const logs = codeLogs ?? [];
  const showExecutionError =
    executionError &&
    typeof executionError.message === 'string' &&
    executionError.message.trim() !== '' &&
    (!nodeError ||
      typeof nodeError !== 'object' ||
      (nodeError as Record<string, unknown>).message !== executionError.message);

  if (!nodeError && !showExecutionError && logs.length === 0 && events.length === 0) {
    return <div className="text-sm text-gray-600">No trace data for this node yet.</div>;
  }

  return (
    <div className="space-y-3">
      {showExecutionError ? (
        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">
            Execution error
          </div>
          <NodeRunErrorDetails error={executionError} />
        </div>
      ) : null}
      <NodeRunErrorDetails error={nodeError} />
      {logs.length > 0 ? (
        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">Console</div>
          <pre className="max-h-48 overflow-auto rounded-md border border-[#eceff2] bg-[#fafbfc] p-2 font-mono text-[11px] leading-snug text-gray-900">
            {logs.join('\n')}
          </pre>
        </div>
      ) : null}
      {events.length > 0 ? (
        <div>
          <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">Events</div>
            <div className="flex gap-1">
              {(['all', 'errors', 'http'] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setEventFilter(f)}
                  className={`rounded px-1.5 py-0.5 text-[10px] font-medium capitalize ${
                    eventFilter === f
                      ? 'bg-gray-200 text-gray-900'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
          {filteredEvents.length === 0 ? (
            <div className="text-xs text-gray-500">No events match this filter.</div>
          ) : (
            <ul className="divide-y divide-[#eceff2] rounded-md border border-[#e8eaed] bg-white text-xs">
              {filteredEvents.map((ev, i) => (
                <li key={`${ev.ts ?? 't'}-${i}`} className="px-2 py-2">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    {ev.ts ? <span className="font-mono text-[10px] text-gray-500">{ev.ts}</span> : null}
                    {ev.level ? (
                      <span className="rounded bg-gray-100 px-1 py-0.5 text-[10px] font-semibold uppercase text-gray-700">
                        {ev.level}
                      </span>
                    ) : null}
                    {ev.kind ? <span className="text-[10px] text-gray-500">{ev.kind}</span> : null}
                  </div>
                  {ev.message ? <div className="mt-0.5 break-words text-gray-900">{ev.message}</div> : null}
                  {ev.detail ? (
                    <pre className="mt-1 max-h-32 overflow-auto rounded bg-[#fafbfc] p-1.5 font-mono text-[10px] text-gray-800">
                      {JSON.stringify(ev.detail, null, 2)}
                    </pre>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
};
