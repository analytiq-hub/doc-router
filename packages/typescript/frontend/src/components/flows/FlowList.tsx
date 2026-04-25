import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  EllipsisVerticalIcon,
  PencilSquareIcon,
  PlayIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { getApiErrorMsg } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';
import FlowStatusBadge from './FlowStatusBadge';
import { useFlowApi } from './useFlowApi';
import type { FlowListItem } from '@docrouter/sdk';

const FlowList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const api = useFlowApi(organizationId);

  const [rows, setRows] = useState<FlowListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [pagination, setPagination] = useState({ page: 0, pageSize: 20 });

  const [rowMenu, setRowMenu] = useState<FlowListItem | null>(null);
  const rowMenuRef = useRef<HTMLDivElement | null>(null);

  const load = useCallback(async () => {
    try {
      setIsLoading(true);
      setMessage('');
      const res = await api.listFlows({
        limit: pagination.pageSize,
        offset: pagination.page * pagination.pageSize,
      });
      setRows(res.items);
      setTotal(res.total);
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Error loading flows');
    } finally {
      setIsLoading(false);
    }
  }, [api, pagination.page, pagination.pageSize]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!rowMenu) return;
    const onDoc = (e: MouseEvent) => {
      if (rowMenuRef.current && !rowMenuRef.current.contains(e.target as Node)) {
        setRowMenu(null);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [rowMenu]);

  const handleEdit = (item: FlowListItem) => {
    router.push(`/orgs/${organizationId}/flows/${item.flow.flow_id}`);
    setRowMenu(null);
  };

  const handleRun = async (item: FlowListItem) => {
    try {
      await api.runFlow(item.flow.flow_id, {});
      await load();
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to run flow');
    } finally {
      setRowMenu(null);
    }
  };

  const handleToggleActive = async (item: FlowListItem) => {
    try {
      if (item.flow.active) {
        await api.deactivateFlow(item.flow.flow_id);
      } else {
        await api.activateFlow(item.flow.flow_id);
      }
      await load();
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to update flow activation');
    } finally {
      setRowMenu(null);
    }
  };

  const handleDelete = async (item: FlowListItem) => {
    const ok = window.confirm(`Delete flow “${item.flow.name}”?`);
    if (!ok) return;
    try {
      await api.deleteFlow(item.flow.flow_id);
      await load();
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to delete flow');
    } finally {
      setRowMenu(null);
    }
  };

  const pageCount = Math.max(1, Math.ceil(total / pagination.pageSize));
  const th = 'border-b border-gray-200 bg-gray-50 px-3 py-2 text-left text-xs font-semibold text-gray-600';
  const td = 'border-b border-gray-100 px-3 py-2 text-sm text-gray-800';

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      {message && <div className="px-4 py-3 text-sm text-red-600">{message}</div>}
      <div className="overflow-x-auto" style={{ minHeight: 400 }}>
        <table className="w-full min-w-[720px] border-collapse">
          <thead>
            <tr>
              <th className={th}>Name</th>
              <th className={th}>Status</th>
              <th className={th}>Version</th>
              <th className={th}>Updated</th>
              <th className={`${th} w-[140px] text-right`} aria-label="actions" />
            </tr>
          </thead>
          <tbody>
            {isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-8 text-center text-sm text-gray-500">
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-8 text-center text-sm text-gray-500">
                  No flows yet
                </td>
              </tr>
            )}
            {rows.map((item) => {
              const v = item.flow.updated_at;
              const updated = v ? formatLocalDate(v) : '—';
              return (
                <tr key={item.flow.flow_id} className="hover:bg-gray-50/80">
                  <td className={td}>
                    <span className="font-medium text-gray-900">{item.flow.name}</span>
                  </td>
                  <td className={td}>
                    <FlowStatusBadge active={item.flow.active} />
                  </td>
                  <td className={td}>{item.flow.flow_version}</td>
                  <td className={`${td} text-gray-600`} title={updated}>
                    {updated}
                  </td>
                  <td className={`${td} text-right`}>
                    <div className="inline-flex items-center justify-end gap-0.5">
                      <button
                        type="button"
                        title="Edit"
                        aria-label="Edit"
                        onClick={() => handleEdit(item)}
                        className="rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100"
                      >
                        <PencilSquareIcon className="h-5 w-5" />
                      </button>
                      <button
                        type="button"
                        title="Run"
                        aria-label="Run"
                        onClick={() => void handleRun(item)}
                        className="rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100"
                      >
                        <PlayIcon className="h-5 w-5" />
                      </button>
                      <div className="relative" ref={rowMenu?.flow.flow_id === item.flow.flow_id ? rowMenuRef : null}>
                        <button
                          type="button"
                          title="More"
                          aria-label="More"
                          aria-expanded={rowMenu?.flow.flow_id === item.flow.flow_id}
                          onClick={() => setRowMenu((m) => (m?.flow.flow_id === item.flow.flow_id ? null : item))}
                          className="rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100"
                        >
                          <EllipsisVerticalIcon className="h-5 w-5" />
                        </button>
                        {rowMenu?.flow.flow_id === item.flow.flow_id && (
                          <div
                            className="absolute right-0 z-20 mt-1 w-44 rounded-md border border-gray-200 bg-white py-1 text-left text-sm shadow-lg"
                            role="menu"
                          >
                            <button
                              type="button"
                              className="flex w-full items-center gap-2 px-3 py-2 text-gray-800 hover:bg-gray-100"
                              onClick={() => handleEdit(item)}
                              role="menuitem"
                            >
                              <PencilSquareIcon className="h-4 w-4" /> Edit
                            </button>
                            <button
                              type="button"
                              className="flex w-full items-center gap-2 px-3 py-2 text-gray-800 hover:bg-gray-100"
                              onClick={() => void handleRun(item)}
                              role="menuitem"
                            >
                              <PlayIcon className="h-4 w-4" /> Run
                            </button>
                            <button
                              type="button"
                              className="flex w-full items-center gap-2 px-3 py-2 text-gray-800 hover:bg-gray-100"
                              onClick={() => void handleToggleActive(item)}
                              role="menuitem"
                            >
                              {item.flow.active ? 'Deactivate' : 'Activate'}
                            </button>
                            <button
                              type="button"
                              className="flex w-full items-center gap-2 px-3 py-2 text-red-700 hover:bg-red-50"
                              onClick={() => void handleDelete(item)}
                              role="menuitem"
                            >
                              <TrashIcon className="h-4 w-4" /> Delete
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-200 px-3 py-2 text-sm text-gray-600">
        <div>
          {total} flow{total === 1 ? '' : 's'} total · page {pagination.page + 1} of {pageCount}
        </div>
        <div className="flex items-center gap-2">
          <label className="inline-flex items-center gap-1">
            <span className="text-xs">Rows</span>
            <select
              className="rounded border border-gray-300 bg-white px-2 py-1 text-sm"
              value={pagination.pageSize}
              onChange={(e) => {
                const pageSize = Number(e.target.value);
                setPagination({ page: 0, pageSize });
              }}
            >
              {[10, 20, 50].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="rounded border border-gray-300 bg-white px-2 py-1 text-sm disabled:opacity-40"
            disabled={pagination.page <= 0}
            onClick={() => setPagination((p) => ({ ...p, page: Math.max(0, p.page - 1) }))}
          >
            Previous
          </button>
          <button
            type="button"
            className="rounded border border-gray-300 bg-white px-2 py-1 text-sm disabled:opacity-40"
            disabled={pagination.page >= pageCount - 1}
            onClick={() => setPagination((p) => ({ ...p, page: Math.min(pageCount - 1, p.page + 1) }))}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default FlowList;
