'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { FlowExecution, FlowListItem } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';
import { useFlowApi } from './useFlowApi';

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

function statusLabel(e: FlowExecution) {
  switch (e.status) {
    case 'success':
      return 'Succeeded';
    case 'error':
      return 'Error';
    case 'running':
      return 'Running';
    case 'queued':
      return 'Queued';
    case 'stopped':
      return 'Stopped';
    default:
      return e.status;
  }
}

const FlowExecutionsAll: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const api = useFlowApi(organizationId);
  const [list, setList] = useState<FlowExecution[]>([]);
  const [flowNames, setFlowNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [stopLoadingId, setStopLoadingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setMessage('');
      const pageSize = 200;
      const [execRes, firstFlows] = await Promise.all([
        api.listExecutions({ limit: 100, offset: 0 }),
        api.listFlows({ limit: pageSize, offset: 0 }),
      ]);
      setList(execRes.items);
      const m: Record<string, string> = {};
      for (const row of firstFlows.items as FlowListItem[]) {
        m[row.flow.flow_id] = row.flow.name;
      }
      let offset = firstFlows.items.length;
      const totalFlows = firstFlows.total;
      while (offset < totalFlows) {
        const next = await api.listFlows({ limit: pageSize, offset });
        if (next.items.length === 0) break;
        for (const row of next.items as FlowListItem[]) {
          m[row.flow.flow_id] = row.flow.name;
        }
        offset += next.items.length;
      }
      setFlowNames(m);
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to load executions');
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  const stopExecution = useCallback(
    async (flowId: string, executionId: string) => {
      try {
        setStopLoadingId(executionId);
        await api.stopExecution(flowId, executionId);
        await load();
      } catch (err) {
        setMessage(getApiErrorMsg(err) || 'Failed to stop execution');
      } finally {
        setStopLoadingId(null);
      }
    },
    [api, load],
  );

  const th = 'border-b border-gray-200 bg-gray-50 px-3 py-2 text-left text-xs font-semibold text-gray-600';
  const td = 'border-b border-gray-100 px-3 py-2 text-sm text-gray-800';

  const empty = useMemo(() => !loading && list.length === 0, [loading, list.length]);

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      {message && <div className="px-4 py-3 text-sm text-red-600">{message}</div>}
      <div className="overflow-x-auto" style={{ minHeight: 360 }}>
        <table className="w-full min-w-[880px] border-collapse">
          <thead>
            <tr>
              <th className={th}>Flow</th>
              <th className={th}>Status</th>
              <th className={th}>Started</th>
              <th className={th}>Duration</th>
              <th className={`${th} w-[120px] text-right`} aria-label="actions" />
            </tr>
          </thead>
          <tbody>
            {loading && list.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-8 text-center text-sm text-gray-500">
                  Loading…
                </td>
              </tr>
            )}
            {empty && (
              <tr>
                <td colSpan={5} className="px-3 py-8 text-center text-sm text-gray-500">
                  No executions yet.
                </td>
              </tr>
            )}
            {list.map((e) => {
              const fname = flowNames[e.flow_id] || e.flow_id;
              const running = statusRunning(e);
              const stopping = stopLoadingId === e.execution_id;
              return (
                <tr
                  key={e.execution_id}
                  className="cursor-pointer hover:bg-gray-50"
                  onClick={() =>
                    router.push(`/orgs/${organizationId}/flows/${e.flow_id}?tab=executions`)
                  }
                >
                  <td className={td}>
                    <Link
                      href={`/orgs/${organizationId}/flows/${e.flow_id}?tab=executions`}
                      className="font-medium text-blue-700 hover:underline"
                      onClick={(ev) => ev.stopPropagation()}
                    >
                      {fname}
                    </Link>
                  </td>
                  <td className={td}>
                    <span title={e.status}>
                      {statusLabel(e)} <span className="text-gray-500">· {formatDuration(e)}</span>
                    </span>
                  </td>
                  <td className={td}>{formatLocalDate(e.started_at)}</td>
                  <td className={td}>{formatDuration(e)}</td>
                  <td className={`${td} text-right`} onClick={(ev) => ev.stopPropagation()}>
                    {running && (
                      <button
                        type="button"
                        disabled={stopping}
                        onClick={() => void stopExecution(e.flow_id, e.execution_id)}
                        className={[
                          'rounded border px-2.5 py-1 text-xs font-semibold shadow-sm transition',
                          stopping
                            ? 'cursor-not-allowed border-gray-200 bg-gray-100 text-gray-400'
                            : 'border-red-200 bg-white text-red-700 hover:bg-red-50',
                        ].join(' ')}
                      >
                        {stopping ? 'Stopping…' : 'Stop'}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default FlowExecutionsAll;
