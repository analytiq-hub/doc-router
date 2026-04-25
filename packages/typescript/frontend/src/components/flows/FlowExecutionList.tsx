'use client';

import React, { useCallback, useEffect, useState } from 'react';
import type { FlowExecution } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';

function statusRunning(e: FlowExecution) {
  return e.status === 'queued' || e.status === 'running';
}

function formatDuration(e: FlowExecution) {
  const end = e.finished_at ? new Date(e.finished_at).getTime() : Date.now();
  const start = new Date(e.started_at).getTime();
  if (!Number.isFinite(end) || !Number.isFinite(start)) return '—';
  const s = Math.max(0, Math.round((end - start) / 1000));
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

const thClass = 'border-b border-gray-200 bg-gray-50 px-3 py-2 text-left text-xs font-semibold text-gray-600';
const tdClass = 'border-b border-gray-100 px-3 py-2 text-sm text-gray-800';

const FlowExecutionList: React.FC<{
  orgApi: DocRouterOrgApi;
  flowId: string;
}> = ({ orgApi, flowId }) => {
  const [items, setItems] = useState<FlowExecution[]>([]);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState<string>('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setErr('');
      const res = await orgApi.listExecutions(flowId, { limit: 50, offset: 0 });
      setItems(res.items);
      setTotal(res.total);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to load executions');
    } finally {
      setLoading(false);
    }
  }, [orgApi, flowId]);

  useEffect(() => {
    void load();
  }, [load]);

  const anyActive = items.some(statusRunning);
  useEffect(() => {
    if (!anyActive) return;
    const id = setInterval(() => {
      void load();
    }, 3000);
    return () => clearInterval(id);
  }, [anyActive, load]);

  const onStop = async (executionId: string) => {
    try {
      await orgApi.stopExecution(flowId, executionId);
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Stop failed');
    }
  };

  if (loading && items.length === 0) {
    return <div className="text-sm text-gray-500">Loading executions…</div>;
  }

  return (
    <div className="space-y-2">
      {err && <div className="text-sm text-red-600">{err}</div>}
      <div className="text-xs text-gray-500">
        Showing {items.length} of {total} executions
      </div>
      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="w-full min-w-[520px] border-collapse">
          <thead>
            <tr>
              <th className={thClass}>Started</th>
              <th className={thClass}>Mode</th>
              <th className={thClass}>Status</th>
              <th className={thClass}>Duration</th>
              <th className={`${thClass} text-right`}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((e) => {
              const open = expanded === e.execution_id;
              return (
                <React.Fragment key={e.execution_id}>
                  <tr
                    onClick={() => setExpanded((x) => (x === e.execution_id ? null : e.execution_id))}
                    className={`cursor-pointer transition hover:bg-gray-50 ${open ? 'bg-slate-50' : ''}`}
                  >
                    <td className={tdClass}>{formatLocalDate(e.started_at)}</td>
                    <td className={tdClass}>{e.mode}</td>
                    <td className={tdClass}>{e.status}</td>
                    <td className={tdClass}>{formatDuration(e)}</td>
                    <td className={`${tdClass} text-right`} onClick={(ev) => ev.stopPropagation()}>
                      {statusRunning(e) && (
                        <button
                          type="button"
                          onClick={() => void onStop(e.execution_id)}
                          className="rounded border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-medium text-red-800 hover:bg-red-100"
                        >
                          Stop
                        </button>
                      )}
                    </td>
                  </tr>
                  {open && (
                    <tr onClick={(ev) => ev.stopPropagation()}>
                      <td colSpan={5} className="border-b border-gray-100 bg-gray-50 px-0">
                        <pre className="max-h-80 overflow-auto rounded-b-lg border-t border-gray-200 p-2 text-[11px] text-gray-800">
                          {JSON.stringify(
                            { run_data: e.run_data, error: e.error, trigger: e.trigger, last_node: e.last_node_executed },
                            null,
                            2,
                          )}
                        </pre>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {items.length === 0 && !loading && (
        <div className="text-sm text-gray-600">No executions yet. Run the flow from the editor tab.</div>
      )}
    </div>
  );
};

export default FlowExecutionList;
