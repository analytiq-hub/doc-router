import React, { useCallback, useEffect, useState } from 'react';
import { Menu, MenuButton, MenuItem, MenuItems, MenuSeparator } from '@headlessui/react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  BoltIcon,
  BoltSlashIcon,
  EllipsisVerticalIcon,
  PencilSquareIcon,
  PlayIcon,
  Square2StackIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { getApiErrorMsg } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';
import FlowStatusBadge from './FlowStatusBadge';
import {
  flowWorkspaceDropdownDividerClass,
  flowWorkspaceDropdownItemClass,
  flowWorkspaceDropdownItemDestructiveClass,
  flowWorkspaceMenuPanelClass,
  flowWorkspaceMenuTriggerIconBtnClass,
} from './flowWorkspaceMenu';
import { useFlowApi } from './useFlowApi';
import type { FlowListItem } from '@docrouter/sdk';

const FlowList: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const router = useRouter();
  const api = useFlowApi(organizationId);

  const [rows, setRows] = useState<FlowListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [cloningFlowId, setCloningFlowId] = useState<string | null>(null);
  const [pagination, setPagination] = useState({ page: 0, pageSize: 20 });

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

  const handleEdit = (item: FlowListItem) => {
    router.push(`/orgs/${organizationId}/flows/${item.flow.flow_id}`);
  };

  const handleRun = async (item: FlowListItem) => {
    try {
      await api.runFlow(item.flow.flow_id, {});
      await load();
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to run flow');
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
    }
  };

  const handleClone = async (item: FlowListItem) => {
    const flowRevid = item.latest_revision?.flow_revid?.trim();
    if (!flowRevid) {
      setMessage('Cannot clone: this flow has no saved revision');
      return;
    }
    try {
      setCloningFlowId(item.flow.flow_id);
      setMessage('');
      const revision = await api.getRevision(item.flow.flow_id, flowRevid);
      const res = await api.createFlow({
        name: `Copy of ${item.flow.name}`,
        nodes: revision.nodes,
        connections: revision.connections,
        settings: revision.settings,
        pin_data: revision.pin_data,
      });
      await load();
      router.push(`/orgs/${organizationId}/flows/${res.flow.flow_id}`);
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to clone flow');
    } finally {
      setCloningFlowId(null);
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
              <th className={`${th} w-[140px] text-right`}>Actions</th>
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
                    <Link
                      href={`/orgs/${organizationId}/flows/${item.flow.flow_id}`}
                      className="font-medium text-blue-700 hover:underline"
                    >
                      {item.flow.name}
                    </Link>
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
                      <Menu as="div" className="relative inline-flex">
                        <MenuButton className={flowWorkspaceMenuTriggerIconBtnClass} title="More" aria-label="More">
                          <EllipsisVerticalIcon className="h-5 w-5" aria-hidden />
                        </MenuButton>
                        <MenuItems anchor="bottom end" portal className={flowWorkspaceMenuPanelClass}>
                          <MenuItem>
                            {({ focus }) => (
                              <button
                                type="button"
                                className={`${flowWorkspaceDropdownItemClass} w-full ${focus ? 'bg-gray-100' : ''}`}
                                onClick={() => handleEdit(item)}
                              >
                                <PencilSquareIcon className="h-4 w-4 shrink-0" aria-hidden /> Edit
                              </button>
                            )}
                          </MenuItem>
                          <MenuItem>
                            {({ focus }) => (
                              <button
                                type="button"
                                className={`${flowWorkspaceDropdownItemClass} w-full ${focus ? 'bg-gray-100' : ''}`}
                                onClick={() => void handleRun(item)}
                              >
                                <PlayIcon className="h-4 w-4 shrink-0" aria-hidden /> Run
                              </button>
                            )}
                          </MenuItem>
                          <MenuItem>
                            {({ focus }) => (
                              <button
                                type="button"
                                className={`${flowWorkspaceDropdownItemClass} w-full ${focus ? 'bg-gray-100' : ''}`}
                                onClick={() => void handleToggleActive(item)}
                              >
                                {item.flow.active ? (
                                  <>
                                    <BoltSlashIcon className="h-4 w-4 shrink-0" aria-hidden /> Deactivate
                                  </>
                                ) : (
                                  <>
                                    <BoltIcon className="h-4 w-4 shrink-0" aria-hidden /> Activate
                                  </>
                                )}
                              </button>
                            )}
                          </MenuItem>
                          <MenuItem disabled={cloningFlowId === item.flow.flow_id}>
                            {({ focus, disabled }) => (
                              <button
                                type="button"
                                disabled={disabled}
                                className={`${flowWorkspaceDropdownItemClass} w-full ${disabled ? 'cursor-not-allowed opacity-45' : ''} ${focus && !disabled ? 'bg-gray-100' : ''}`}
                                onClick={() => void handleClone(item)}
                              >
                                <Square2StackIcon className="h-4 w-4 shrink-0" aria-hidden /> Clone
                              </button>
                            )}
                          </MenuItem>
                          <MenuSeparator className={flowWorkspaceDropdownDividerClass} />
                          <MenuItem>
                            {({ focus }) => (
                              <button
                                type="button"
                                className={`${flowWorkspaceDropdownItemDestructiveClass} w-full ${focus ? 'bg-red-50' : ''}`}
                                onClick={() => void handleDelete(item)}
                              >
                                <TrashIcon className="h-4 w-4 shrink-0" aria-hidden /> Delete
                              </button>
                            )}
                          </MenuItem>
                        </MenuItems>
                      </Menu>
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
