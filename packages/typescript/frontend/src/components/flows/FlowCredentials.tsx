'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControl from '@mui/material/FormControl';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import type { FlowCredentialHeader, FlowCredentialKindSummary } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import { formatLocalDate } from '@/utils/date';
import { useFlowApi } from './useFlowApi';
import { flowInputClass, flowLabelClass } from './flowUiClasses';

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

const FlowCredentials: React.FC<{
  organizationId: string;
  autoOpenCreate?: boolean;
  onAutoOpenCreateHandled?: () => void;
}> = ({ organizationId, autoOpenCreate, onAutoOpenCreateHandled }) => {
  const api = useFlowApi(organizationId);
  const [kinds, setKinds] = useState<FlowCredentialKindSummary[]>([]);
  const [items, setItems] = useState<FlowCredentialHeader[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');

  const [createOpen, setCreateOpen] = useState(false);
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

  const kindByKey = useMemo(() => Object.fromEntries(kinds.map((k) => [k.key, k])), [kinds]);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setMessage('');
      const [kRes, cRes] = await Promise.all([
        api.listFlowCredentialKinds(),
        api.listFlowCredentials(),
      ]);
      setKinds(kRes);
      setItems(cRes.items);
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to load credentials');
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!autoOpenCreate) return;
    setCreateOpen(true);
    onAutoOpenCreateHandled?.();
  }, [autoOpenCreate, onAutoOpenCreateHandled]);

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

  useEffect(() => {
    if (createOpen && !createKindKey && kinds.length > 0) {
      setCreateKindKey(kinds[0].key);
    }
  }, [createOpen, createKindKey, kinds]);

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
      setCreateOpen(false);
      await load();
    } catch (err) {
      setMessage(getApiErrorMsg(err) || 'Failed to create credential');
    }
  };

  const openEdit = (row: FlowCredentialHeader) => {
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

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      {message && <div className="px-4 py-3 text-sm text-red-600">{message}</div>}
      <div className="overflow-x-auto" style={{ minHeight: 360 }}>
        <table className="w-full min-w-[720px] border-collapse">
          <thead>
            <tr>
              <th className={th}>Name</th>
              <th className={th}>Kind</th>
              <th className={th}>Created</th>
              <th className={`${th} w-[280px]`}>Actions</th>
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
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-8 text-center text-sm text-gray-500">
                  No credentials yet. Add one to use in flow nodes.
                </td>
              </tr>
            )}
            {items.map((row) => {
              const kindLabel = kindByKey[row.kind_key]?.display_name || row.kind_key;
              const chip = testChip[row.credential_id];
              return (
                <tr key={row.credential_id}>
                  <td className={`${td} font-medium`}>{row.name}</td>
                  <td className={td}>{kindLabel}</td>
                  <td className={td}>{formatLocalDate(row.created_at)}</td>
                  <td className={td}>
                    <div className="flex flex-wrap items-center gap-2">
                      {chip && (
                        <Chip
                          size="small"
                          label={chip.detail}
                          color={chip.ok ? 'success' : 'error'}
                          variant="outlined"
                        />
                      )}
                      <Button
                        size="small"
                        variant="outlined"
                        disabled={testLoadingId === row.credential_id}
                        onClick={() => void runTest(row)}
                      >
                        {testLoadingId === row.credential_id ? 'Test…' : 'Test'}
                      </Button>
                      <Button size="small" variant="outlined" onClick={() => openEdit(row)}>
                        Edit
                      </Button>
                      <Button size="small" color="error" variant="outlined" onClick={() => setDeleteRow(row)}>
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New credential</DialogTitle>
        <DialogContent className="flex flex-col gap-3 pt-1">
          <FormControl fullWidth size="small" sx={{ mt: 1 }}>
            <InputLabel id="cred-kind-label">Kind</InputLabel>
            <Select
              labelId="cred-kind-label"
              label="Kind"
              value={createKindKey}
              onChange={(e) => setCreateKindKey(e.target.value)}
            >
              {kinds.map((k) => (
                <MenuItem key={k.key} value={k.key}>
                  {k.display_name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
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
            <TextField
              key={f.name}
              fullWidth
              size="small"
              label={f.title || f.name}
              helperText={f.description}
              type={f.is_secret && !showSecret[f.name] ? 'password' : 'text'}
              value={createFields[f.name] ?? ''}
              onChange={(e) => setCreateFields((prev) => ({ ...prev, [f.name]: e.target.value }))}
              InputProps={
                f.is_secret
                  ? {
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton
                            aria-label="toggle visibility"
                            onClick={() =>
                              setShowSecret((s) => ({ ...s, [f.name]: !s[f.name] }))
                            }
                            edge="end"
                          >
                            {showSecret[f.name] ? <VisibilityOff /> : <Visibility />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }
                  : undefined
              }
            />
          ))}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => void submitCreate()}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={editRow != null} onClose={() => setEditRow(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Edit credential</DialogTitle>
        <DialogContent className="flex flex-col gap-3 pt-1">
          <div className="text-xs text-gray-500">
            Kind: <strong>{editKind?.display_name || editRow?.kind_key}</strong> (cannot change)
          </div>
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
            <TextField
              key={f.name}
              fullWidth
              size="small"
              label={f.title || f.name}
              helperText={
                f.is_secret
                  ? `${f.description ? `${f.description} ` : ''}(re-enter to replace; required to save)`
                  : f.description
              }
              type={f.is_secret && !showSecret[`edit-${f.name}`] ? 'password' : 'text'}
              value={editFields[f.name] ?? ''}
              onChange={(e) => setEditFields((prev) => ({ ...prev, [f.name]: e.target.value }))}
              InputProps={
                f.is_secret
                  ? {
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton
                            aria-label="toggle visibility"
                            onClick={() =>
                              setShowSecret((s) => ({
                                ...s,
                                [`edit-${f.name}`]: !s[`edit-${f.name}`],
                              }))
                            }
                            edge="end"
                          >
                            {showSecret[`edit-${f.name}`] ? <VisibilityOff /> : <Visibility />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }
                  : undefined
              }
            />
          ))}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditRow(null)}>Cancel</Button>
          <Button variant="contained" onClick={() => void submitEdit()}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={deleteRow != null} onClose={() => setDeleteRow(null)}>
        <DialogTitle>Delete credential?</DialogTitle>
        <DialogContent>
          <p className="m-0 text-sm text-gray-700">
            Delete “{deleteRow?.name}”? Flow nodes that reference it may fail until you choose another
            credential.
          </p>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteRow(null)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={() => void confirmDelete()}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default FlowCredentials;
