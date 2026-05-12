'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Menu, MenuButton, MenuItem, MenuItems, MenuSeparator } from '@headlessui/react';
import {
  BeakerIcon,
  EllipsisVerticalIcon,
  EyeIcon,
  EyeSlashIcon,
  MagnifyingGlassIcon,
  PencilSquareIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import type { FlowCredentialHeader, FlowCredentialKindSummary } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import { toast } from 'react-toastify';
import { formatLocalDate } from '@/utils/date';
import { useFlowApi } from './useFlowApi';
import {
  flowWorkspaceDropdownDividerClass,
  flowWorkspaceDropdownItemClass,
  flowWorkspaceDropdownItemDestructiveClass,
  flowWorkspaceMenuPanelClass,
  flowWorkspaceMenuTriggerIconBtnClass,
} from './flowWorkspaceMenu';
import { flowInputClass, flowLabelClass } from './flowUiClasses';
import { loadCredentialNamesTakenLower, nextSequentialDisplayName } from './flowDefaultNames';

type FieldRow = {
  name: string;
  title?: string;
  description?: string;
  type?: string;
  is_secret?: boolean;
};

function fieldRows(kind: FlowCredentialKindSummary | null): FieldRow[] {
  if (!kind?.fields?.length) return [];
  return kind.fields.map((f) => {
    const name = typeof f.name === 'string' ? f.name : '';
    const title = typeof f.title === 'string' ? f.title : undefined;
    const description = typeof f.description === 'string' ? f.description : undefined;
    const type = typeof f.type === 'string' ? f.type : undefined;
    const is_secret = f.is_secret === true;
    return { name, title, description, type, is_secret };
  });
}

const btnSecondary =
  'rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50';
const btnPrimary =
  'rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50';
const btnDanger =
  'rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50';

function FlowModal({
  open,
  title,
  titleAccessory,
  onClose,
  children,
  footer,
  panelMaxWidthClassName = 'max-w-md',
}: {
  open: boolean;
  title: string;
  /** Shown on the same row as the title (e.g. credential kind badge). */
  titleAccessory?: React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
  footer: React.ReactNode;
  /** Tailwind max-width for the dialog panel (picker lists benefit from `max-w-lg`). */
  panelMaxWidthClassName?: string;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[280] flex items-center justify-center p-4" role="presentation">
      <button
        type="button"
        className="absolute inset-0 bg-black/50"
        aria-label="Close dialog"
        onClick={onClose}
      />
      <div
        className={`relative z-10 flex max-h-[min(85vh,36rem)] w-full flex-col rounded-lg border border-gray-200 bg-white shadow-xl ${panelMaxWidthClassName}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="flow-cred-modal-title"
      >
        <div className="shrink-0 border-b border-gray-100 px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="flow-cred-modal-title" className="min-w-0 text-base font-semibold text-gray-900">
              {title}
            </h2>
            {titleAccessory != null ? <div className="shrink-0">{titleAccessory}</div> : null}
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">{children}</div>
        <div className="flex shrink-0 justify-end gap-2 border-t border-gray-100 px-4 py-3">{footer}</div>
      </div>
    </div>
  );
}

const FlowCredentials: React.FC<{
  organizationId: string;
  /** Open the new-credential dialog (header Create credential, or legacy `newCredential` / `bootstrapCredential` in URL). */
  autoBootstrapCredential?: boolean;
  onAutoBootstrapCredentialHandled?: () => void;
}> = ({ organizationId, autoBootstrapCredential, onAutoBootstrapCredentialHandled }) => {
  const api = useFlowApi(organizationId);
  const [kinds, setKinds] = useState<FlowCredentialKindSummary[]>([]);
  const [items, setItems] = useState<FlowCredentialHeader[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [pagination, setPagination] = useState({ page: 0, pageSize: 20 });

  const [createOpen, setCreateOpen] = useState(false);
  /** Step 1: search + pick kind; step 2: name + fields (n8n-style wizard). */
  const [createWizardStep, setCreateWizardStep] = useState<'pick' | 'form'>('pick');
  const [createKindQuery, setCreateKindQuery] = useState('');
  const [createPickKindKey, setCreatePickKindKey] = useState('');
  const [editRow, setEditRow] = useState<FlowCredentialHeader | null>(null);
  const [deleteRow, setDeleteRow] = useState<FlowCredentialHeader | null>(null);

  const [createKindKey, setCreateKindKey] = useState('');
  const [createName, setCreateName] = useState('');
  const [createFields, setCreateFields] = useState<Record<string, string>>({});
  const [showSecret, setShowSecret] = useState<Record<string, boolean>>({});

  const [editName, setEditName] = useState('');
  const [editFields, setEditFields] = useState<Record<string, string>>({});

  const [testChip, setTestChip] = useState<Record<string, { ok: boolean; detail: string }>>({});
  const [testLoadingId, setTestLoadingId] = useState<string | null>(null);
  const [oauthConnectLoading, setOauthConnectLoading] = useState(false);

  const kindByKey = useMemo(() => Object.fromEntries(kinds.map((k) => [k.key, k])), [kinds]);

  const filteredCredentialKinds = useMemo(() => {
    const q = createKindQuery.trim().toLowerCase();
    if (!q) return kinds;
    return kinds.filter((k) => {
      const label = (k.display_name || k.key || '').toLowerCase();
      const key = (k.key || '').toLowerCase();
      return label.includes(q) || key.includes(q);
    });
  }, [kinds, createKindQuery]);

  const resetCreateWizardState = useCallback(() => {
    setCreateWizardStep('pick');
    setCreateKindQuery('');
    setCreatePickKindKey('');
    setCreateKindKey('');
    setCreateName('');
    setCreateFields({});
    setShowSecret({});
  }, []);

  const closeCreateCredential = useCallback(() => {
    setCreateOpen(false);
    resetCreateWizardState();
  }, [resetCreateWizardState]);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setMessage('');
      const [kRes, cRes] = await Promise.all([
        api.listFlowCredentialKinds(),
        api.listFlowCredentials({
          limit: pagination.pageSize,
          offset: pagination.page * pagination.pageSize,
        }),
      ]);
      setKinds(kRes);
      setItems(cRes.items);
      setTotal(cRes.total);
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to load credentials');
    } finally {
      setLoading(false);
    }
  }, [api, pagination.page, pagination.pageSize]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const sp = new URLSearchParams(window.location.search);
    const st = sp.get('flow_oauth');
    if (!st) return;
    if (st === 'success') {
      toast.success('Credential connected successfully');
    } else if (st === 'error') {
      toast.error(sp.get('flow_oauth_detail') || 'OAuth connection failed');
    }
    sp.delete('flow_oauth');
    sp.delete('flow_oauth_detail');
    const qs = sp.toString();
    window.history.replaceState({}, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`);
  }, []);

  const openEdit = useCallback((row: FlowCredentialHeader) => {
    setEditRow(row);
    setEditName(row.name);
    const k = kindByKey[row.kind_key];
    const next: Record<string, string> = {};
    if (k) {
      for (const f of fieldRows(k)) {
        if (!f.name) continue;
        if (f.is_secret) next[f.name] = '';
        else {
          const pub = row.public_fields[f.name];
          next[f.name] = pub === undefined || pub === null ? '' : String(pub);
        }
      }
    }
    setEditFields(next);
    setShowSecret({});
  }, [kindByKey]);

  useEffect(() => {
    if (!autoBootstrapCredential) return;
    if (loading || kinds.length === 0) return;

    let cancelled = false;

    const run = async () => {
      try {
        setMessage('');
        resetCreateWizardState();
        setCreateOpen(true);
        const taken = await loadCredentialNamesTakenLower(api);
        if (cancelled) return;
        setCreateName(nextSequentialDisplayName(taken, 'My credential'));
      } catch (err) {
        if (!cancelled) setMessage(getApiErrorMsg(err) || 'Failed to prepare new credential');
      } finally {
        if (!cancelled) onAutoBootstrapCredentialHandled?.();
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [
    autoBootstrapCredential,
    loading,
    kinds.length,
    api,
    onAutoBootstrapCredentialHandled,
    resetCreateWizardState,
  ]);

  const createKind = createKindKey ? kindByKey[createKindKey] : null;
  const createFieldDefs = useMemo(() => fieldRows(createKind), [createKind]);

  useEffect(() => {
    if (!createOpen || !createKind) return;
    setCreateFields((prev) => {
      const next: Record<string, string> = {};
      for (const f of fieldRows(createKind)) {
        if (f.name) next[f.name] = prev[f.name] ?? '';
      }
      return next;
    });
  }, [createOpen, createKindKey, createKind]);

  const submitCreate = async () => {
    if (!createKindKey.trim() || !createName.trim()) {
      setMessage('Name and kind are required');
      return;
    }
    const kind = kindByKey[createKindKey];
    if (!kind) return;
    const fields: Record<string, unknown> = {};
    for (const f of fieldRows(kind)) {
      if (!f.name) continue;
      fields[f.name] = createFields[f.name] ?? '';
    }
    try {
      setMessage('');
      await api.createFlowCredential({
        kind_key: createKindKey,
        name: createName.trim(),
        fields,
      });
      closeCreateCredential();
      await load();
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to create credential');
    }
  };

  const submitEdit = async () => {
    if (!editRow) return;
    const k = kindByKey[editRow.kind_key];
    if (!k) {
      setMessage('Unknown credential kind');
      return;
    }
    const fields: Record<string, unknown> = {};
    for (const f of fieldRows(k)) {
      if (!f.name) continue;
      const v = editFields[f.name] ?? '';
      if (f.is_secret && !v.trim()) {
        setMessage(`Secret field “${f.title || f.name}” must be re-entered to update.`);
        return;
      }
      fields[f.name] = v;
    }
    try {
      setMessage('');
      await api.updateFlowCredential(editRow.credential_id, {
        name: editName.trim(),
        fields,
      });
      setEditRow(null);
      await load();
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to update credential');
    }
  };

  const confirmDelete = async () => {
    if (!deleteRow) return;
    try {
      setMessage('');
      await api.deleteFlowCredential(deleteRow.credential_id);
      setDeleteRow(null);
      await load();
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to delete credential');
    }
  };

  const startOAuthConnect = async () => {
    if (!editRow) return;
    try {
      setOauthConnectLoading(true);
      setMessage('');
      const { authorization_url } = await api.initiateFlowOAuthConnect(editRow.credential_id);
      window.location.href = authorization_url;
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Could not start OAuth');
      setOauthConnectLoading(false);
    }
  };

  const runTest = async (row: FlowCredentialHeader) => {
    try {
      setTestLoadingId(row.credential_id);
      const res = await api.testFlowCredential(row.credential_id);
      const detail =
        res.ok && res.error
          ? String(res.error)
          : res.ok
            ? res.status_code != null
              ? `HTTP ${res.status_code}`
              : 'OK'
            : res.error || 'Failed';
      setTestChip((prev) => ({
        ...prev,
        [row.credential_id]: { ok: res.ok, detail },
      }));
    } catch (err) {
      setTestChip((prev) => ({
        ...prev,
        [row.credential_id]: { ok: false, detail: getApiErrorMsg(err) || 'Request failed' },
      }));
    } finally {
      setTestLoadingId(null);
    }
  };

  const th = 'border-b border-gray-200 bg-gray-50 px-3 py-2 text-left text-xs font-semibold text-gray-600';
  const td = 'border-b border-gray-100 px-3 py-2 text-sm text-gray-800';

  const editKind = editRow ? kindByKey[editRow.kind_key] : null;
  const editFieldDefs = useMemo(() => fieldRows(editKind), [editKind]);
  const pageCount = Math.max(1, Math.ceil(total / pagination.pageSize));

  const continuePickToForm = () => {
    if (!createPickKindKey.trim()) return;
    setCreateKindKey(createPickKindKey);
    setCreateWizardStep('form');
  };

  const backFormToPick = () => {
    setCreatePickKindKey(createKindKey);
    setCreateKindKey('');
    setCreateWizardStep('pick');
  };

  const renderSecretToggle = (key: string) => (
    <button
      type="button"
      className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
      aria-label={showSecret[key] ? 'Hide value' : 'Show value'}
      onClick={() => setShowSecret((s) => ({ ...s, [key]: !s[key] }))}
    >
      {showSecret[key] ? <EyeSlashIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
    </button>
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      <div className="border-b border-gray-200 px-4 py-3">
        <p className="m-0 text-sm text-gray-600">Store API keys and auth for HTTP Request and other nodes.</p>
      </div>
      {message && <div className="px-4 py-3 text-sm text-red-600">{message}</div>}
      <div className="overflow-x-auto" style={{ minHeight: 360 }}>
        <table className="w-full min-w-[720px] border-collapse">
          <thead>
            <tr>
              <th className={th}>Name</th>
              <th className={th}>Kind</th>
              <th className={th}>Created</th>
              <th className={`${th} w-[140px] text-right`}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-8 text-center text-sm text-gray-500">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && total === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-8 text-center text-sm text-gray-500">
                  No credentials yet. Use Create credential in the page header to add one.
                </td>
              </tr>
            )}
            {items.map((row) => {
              const kindLabel = kindByKey[row.kind_key]?.display_name || row.kind_key;
              const canTest = kindByKey[row.kind_key]?.has_test_request === true;
              const chip = canTest ? testChip[row.credential_id] : undefined;
              return (
                <tr key={row.credential_id}>
                  <td className={td}>
                    <button
                      type="button"
                      onClick={() => openEdit(row)}
                      title="Edit credential"
                      className="m-0 max-w-full cursor-pointer truncate border-0 bg-transparent p-0 text-left font-medium text-blue-700 hover:underline"
                    >
                      {row.name}
                    </button>
                  </td>
                  <td className={td}>{kindLabel}</td>
                  <td className={td}>{formatLocalDate(row.created_at)}</td>
                  <td className={`${td} text-right`}>
                    <div className="inline-flex max-w-full flex-wrap items-center justify-end gap-2">
                      {chip && (
                        <span
                          className={
                            chip.ok
                              ? 'inline-flex max-w-[min(220px,100%)] truncate rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-900'
                              : 'inline-flex max-w-[min(220px,100%)] truncate rounded border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-medium text-red-900'
                          }
                          title={chip.detail}
                        >
                          {chip.detail}
                        </span>
                      )}
                      <div className="inline-flex shrink-0 items-center justify-end gap-0.5">
                        {canTest ? (
                          <button
                            type="button"
                            title="Test connection"
                            aria-label="Test connection"
                            disabled={testLoadingId === row.credential_id}
                            onClick={() => void runTest(row)}
                            className="rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <BeakerIcon className="h-5 w-5" aria-hidden />
                          </button>
                        ) : null}
                        <button
                          type="button"
                          title="Edit"
                          aria-label="Edit"
                          onClick={() => openEdit(row)}
                          className="rounded-md p-1.5 text-gray-600 transition hover:bg-gray-100"
                        >
                          <PencilSquareIcon className="h-5 w-5" aria-hidden />
                        </button>
                        <Menu as="div" className="relative inline-flex">
                          <MenuButton
                            className={flowWorkspaceMenuTriggerIconBtnClass}
                            title="More"
                            aria-label="More"
                          >
                            <EllipsisVerticalIcon className="h-5 w-5" aria-hidden />
                          </MenuButton>
                          <MenuItems anchor="bottom end" portal className={flowWorkspaceMenuPanelClass}>
                            {canTest ? (
                              <MenuItem>
                                {({ focus }) => (
                                  <button
                                    type="button"
                                    disabled={testLoadingId === row.credential_id}
                                    className={`${flowWorkspaceDropdownItemClass} w-full ${focus ? 'bg-gray-100' : ''} disabled:cursor-not-allowed disabled:opacity-50`}
                                    onClick={() => void runTest(row)}
                                  >
                                    <BeakerIcon className="h-4 w-4 shrink-0" aria-hidden /> Test
                                  </button>
                                )}
                              </MenuItem>
                            ) : null}
                            <MenuItem>
                              {({ focus }) => (
                                <button
                                  type="button"
                                  className={`${flowWorkspaceDropdownItemClass} w-full ${focus ? 'bg-gray-100' : ''}`}
                                  onClick={() => openEdit(row)}
                                >
                                  <PencilSquareIcon className="h-4 w-4 shrink-0" aria-hidden /> Edit
                                </button>
                              )}
                            </MenuItem>
                            <MenuSeparator className={flowWorkspaceDropdownDividerClass} />
                            <MenuItem>
                              {({ focus }) => (
                                <button
                                  type="button"
                                  className={`${flowWorkspaceDropdownItemDestructiveClass} w-full ${focus ? 'bg-red-50' : ''}`}
                                  onClick={() => setDeleteRow(row)}
                                >
                                  <TrashIcon className="h-4 w-4 shrink-0" aria-hidden /> Delete
                                </button>
                              )}
                            </MenuItem>
                          </MenuItems>
                        </Menu>
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
          {total} credential{total === 1 ? '' : 's'} total · page {pagination.page + 1} of {pageCount}
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

      <FlowModal
        open={createOpen}
        title={createWizardStep === 'pick' ? 'New credential' : 'Connection details'}
        titleAccessory={
          createWizardStep === 'form' && createKind ? (
            <span
              className="inline-block max-w-[14rem] truncate rounded-md border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-800"
              title={createKind.display_name}
            >
              {createKind.display_name}
            </span>
          ) : undefined
        }
        panelMaxWidthClassName={createWizardStep === 'pick' ? 'max-w-lg' : 'max-w-md'}
        onClose={closeCreateCredential}
        footer={
          createWizardStep === 'pick' ? (
            <>
              <button type="button" className={btnSecondary} onClick={closeCreateCredential}>
                Cancel
              </button>
              <button
                type="button"
                className={btnPrimary}
                disabled={!createPickKindKey}
                onClick={continuePickToForm}
              >
                Continue
              </button>
            </>
          ) : (
            <>
              <button type="button" className={btnSecondary} onClick={backFormToPick}>
                Back
              </button>
              <button type="button" className={btnSecondary} onClick={closeCreateCredential}>
                Cancel
              </button>
              <button type="button" className={btnPrimary} onClick={() => void submitCreate()}>
                Save
              </button>
            </>
          )
        }
      >
        {createWizardStep === 'pick' ? (
          <div className="flex flex-col gap-4">
            <p className="m-0 text-sm leading-relaxed text-gray-700">
              Select an app or service to connect to.
            </p>
            <div>
              <label className={flowLabelClass} htmlFor="cred-create-kind-search">
                Search
              </label>
              <div className="relative">
                <MagnifyingGlassIcon
                  className="pointer-events-none absolute left-2.5 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400"
                  aria-hidden
                />
                <input
                  id="cred-create-kind-search"
                  type="search"
                  role="combobox"
                  aria-expanded={filteredCredentialKinds.length > 0}
                  aria-controls="cred-create-kind-list"
                  aria-autocomplete="list"
                  placeholder="Search for app or service…"
                  autoComplete="off"
                  value={createKindQuery}
                  onChange={(e) => setCreateKindQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      if (createPickKindKey) continuePickToForm();
                    }
                  }}
                  className={`${flowInputClass} pl-10`}
                />
              </div>
            </div>
            <div>
              <div className="mb-1 text-xs font-medium text-gray-600">Credential type</div>
              <div
                id="cred-create-kind-list"
                role="listbox"
                aria-label="Credential types"
                className="max-h-[min(240px,40vh)] overflow-y-auto rounded-md border border-gray-200 bg-gray-50/80"
              >
                {kinds.length === 0 ? (
                  <div className="px-3 py-6 text-center text-sm text-gray-500">
                    No credential types are installed. Add JSON definitions under{' '}
                    <code className="rounded bg-gray-100 px-1 py-0.5 text-xs">schemas/credential-kinds/</code>.
                  </div>
                ) : filteredCredentialKinds.length === 0 ? (
                  <div className="px-3 py-6 text-center text-sm text-gray-500">
                    No services match your search.
                  </div>
                ) : (
                  filteredCredentialKinds.map((k) => {
                    const selected = createPickKindKey === k.key;
                    return (
                      <button
                        key={k.key}
                        type="button"
                        role="option"
                        aria-selected={selected}
                        className={`flex w-full border-0 px-3 py-2.5 text-left text-sm transition ${
                          selected
                            ? 'bg-blue-50 font-medium text-blue-900 ring-1 ring-inset ring-blue-200'
                            : 'bg-white text-gray-800 hover:bg-gray-100'
                        }`}
                        onClick={() => setCreatePickKindKey(k.key)}
                        onDoubleClick={() => {
                          setCreatePickKindKey(k.key);
                          setCreateKindKey(k.key);
                          setCreateWizardStep('form');
                        }}
                      >
                        <span className="min-w-0 flex-1 truncate">{k.display_name}</span>
                        <span className="ml-2 shrink-0 font-mono text-[11px] text-gray-400">{k.key}</span>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div>
              <label className={flowLabelClass} htmlFor="cred-create-name">
                Name
              </label>
              <input
                id="cred-create-name"
                className={flowInputClass}
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                autoComplete="off"
              />
            </div>
            {createFieldDefs.map((f) => (
              <div key={f.name}>
                <label className={flowLabelClass} htmlFor={`cred-create-${f.name}`}>
                  {f.title || f.name}
                </label>
                <div className="relative">
                  <input
                    id={`cred-create-${f.name}`}
                    className={f.is_secret ? `${flowInputClass} pr-10` : flowInputClass}
                    type={f.is_secret && !showSecret[f.name] ? 'password' : 'text'}
                    value={createFields[f.name] ?? ''}
                    onChange={(e) =>
                      setCreateFields((prev) => ({ ...prev, [f.name]: e.target.value }))
                    }
                    autoComplete="off"
                  />
                  {f.is_secret ? renderSecretToggle(f.name) : null}
                </div>
                {f.description ? (
                  <p className="mt-1 text-xs text-gray-500">{f.description}</p>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </FlowModal>

      <FlowModal
        open={editRow != null}
        title="Edit credential"
        titleAccessory={
          <span
            className="inline-block max-w-[14rem] truncate rounded-md border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-800"
            title={editKind?.display_name || editRow?.kind_key}
          >
            {editKind?.display_name || editRow?.kind_key}
          </span>
        }
        onClose={() => setEditRow(null)}
        footer={
          <>
            <button type="button" className={btnSecondary} onClick={() => setEditRow(null)}>
              Cancel
            </button>
            <button type="button" className={btnPrimary} onClick={() => void submitEdit()}>
              Save
            </button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <div>
            <label className={flowLabelClass} htmlFor="cred-edit-name">
              Name
            </label>
            <input
              id="cred-edit-name"
              className={flowInputClass}
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              autoComplete="off"
            />
          </div>
          {editFieldDefs.map((f) => (
            <div key={f.name}>
              <label className={flowLabelClass} htmlFor={`cred-edit-${f.name}`}>
                {f.title || f.name}
              </label>
              <div className="relative">
                <input
                  id={`cred-edit-${f.name}`}
                  className={f.is_secret ? `${flowInputClass} pr-10` : flowInputClass}
                  type={f.is_secret && !showSecret[`edit-${f.name}`] ? 'password' : 'text'}
                  value={editFields[f.name] ?? ''}
                  onChange={(e) =>
                    setEditFields((prev) => ({ ...prev, [f.name]: e.target.value }))
                  }
                  autoComplete="off"
                />
                {f.is_secret ? renderSecretToggle(`edit-${f.name}`) : null}
              </div>
              {f.is_secret ? (
                <p className="mt-1 text-xs text-gray-500">
                  {f.description ? `${f.description} ` : ''}(re-enter to replace; required to save)
                </p>
              ) : f.description ? (
                <p className="mt-1 text-xs text-gray-500">{f.description}</p>
              ) : null}
            </div>
          ))}
          {editKind?.supports_oauth_browser_flow &&
          ['authorizationCode', 'pkce'].includes(
            String(editRow?.public_fields?.grantType ?? 'authorizationCode'),
          ) ? (
            <div className="rounded-md border border-blue-100 bg-blue-50/90 px-3 py-3 text-sm text-blue-950">
              <button
                type="button"
                className={btnPrimary}
                disabled={oauthConnectLoading}
                onClick={() => void startOAuthConnect()}
              >
                {oauthConnectLoading ? 'Redirecting…' : 'Connect with provider'}
              </button>
              <p className="mt-2 text-xs leading-relaxed text-blue-900">
                Save Client ID, Secret, and URLs first. This opens the provider login page to obtain access and refresh
                tokens.
              </p>
            </div>
          ) : null}
        </div>
      </FlowModal>

      <FlowModal
        open={deleteRow != null}
        title="Delete credential?"
        onClose={() => setDeleteRow(null)}
        footer={
          <>
            <button type="button" className={btnSecondary} onClick={() => setDeleteRow(null)}>
              Cancel
            </button>
            <button type="button" className={btnDanger} onClick={() => void confirmDelete()}>
              Delete
            </button>
          </>
        }
      >
        <p className="m-0 text-sm leading-relaxed text-gray-700">
          Delete “{deleteRow?.name}”? Flow nodes that reference it may fail until you choose another
          credential.
        </p>
      </FlowModal>
    </div>
  );
};

export default FlowCredentials;
