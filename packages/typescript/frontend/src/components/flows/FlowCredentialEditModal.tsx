'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircleIcon, EyeIcon, EyeSlashIcon, XMarkIcon } from '@heroicons/react/24/outline';
import type { FlowCredentialHeader, FlowCredentialKindSummary } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import type { DocRouterOrgApi } from '@/utils/api';
import { formatRelativeTime } from '@/utils/date';
import { flowInputClass, flowLabelClass } from './flowUiClasses';
import {
  CREDENTIAL_SECRET_MASK,
  credentialFieldDisplayValue,
  credentialFieldRows,
  credentialFieldValueForSubmit,
  isCredentialSecretMaskValue,
} from './flowCredentialFieldUtils';

const btnSecondary =
  'rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50';
const btnPrimary =
  'rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50';

type EditTab = 'connection' | 'details';

export type FlowCredentialEditModalProps = {
  row: FlowCredentialHeader;
  kind: FlowCredentialKindSummary | null;
  api: DocRouterOrgApi;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
  onError: (message: string) => void;
};

const FlowCredentialEditModal: React.FC<FlowCredentialEditModalProps> = ({
  row,
  kind,
  api,
  onClose,
  onSaved,
  onError,
}) => {
  const [tab, setTab] = useState<EditTab>('connection');
  const [name, setName] = useState(row.name);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [secretMasked, setSecretMasked] = useState<Set<string>>(() => new Set());
  const [showSecret, setShowSecret] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [oauthConnectLoading, setOauthConnectLoading] = useState(false);

  const fieldDefs = useMemo(() => credentialFieldRows(kind), [kind]);
  const secretFieldsSet = useMemo(
    () => new Set(row.secret_fields_set ?? []),
    [row.secret_fields_set],
  );

  const initForm = useCallback(() => {
    setName(row.name);
    setTab('connection');
    const next: Record<string, string> = {};
    const masked = new Set<string>();
    if (kind) {
      for (const f of credentialFieldRows(kind)) {
        if (!f.name) continue;
        if (f.is_secret && secretFieldsSet.has(f.name)) {
          next[f.name] = CREDENTIAL_SECRET_MASK;
          masked.add(f.name);
        } else if (f.is_secret) {
          next[f.name] = '';
        } else {
          next[f.name] = credentialFieldDisplayValue(f, row.public_fields[f.name]);
        }
      }
    }
    setFields(next);
    setSecretMasked(masked);
    setShowSecret({});
  }, [row, kind, secretFieldsSet]);

  useEffect(() => {
    initForm();
  }, [initForm]);

  const grantType = String(row.public_fields?.grantType ?? fields.grantType ?? 'authorizationCode');
  const supportsOAuth =
    kind?.supports_oauth_browser_flow === true &&
    ['authorizationCode', 'pkce'].includes(grantType);
  const oauthConnected =
    supportsOAuth && secretFieldsSet.has('oauthAccessToken');

  const buildFieldsPayload = (): Record<string, unknown> => {
    const out: Record<string, unknown> = {};
    for (const f of fieldDefs) {
      if (!f.name) continue;
      const raw = fields[f.name] ?? '';
      const omitSecret =
        f.is_secret &&
        (secretMasked.has(f.name) || isCredentialSecretMaskValue(raw) || !raw.trim());
      const val = credentialFieldValueForSubmit(f, raw, { omitSecret });
      if (val !== undefined) out[f.name] = val;
    }
    return out;
  };

  const submit = async () => {
    if (!kind) {
      onError('Unknown credential kind');
      return;
    }
    if (!name.trim()) {
      onError('Credential name cannot be empty');
      return;
    }
    try {
      setSaving(true);
      onError('');
      await api.updateFlowCredential(row.credential_id, {
        name: name.trim(),
        fields: buildFieldsPayload(),
      });
      await onSaved();
      onClose();
    } catch (err) {
      onError(getApiErrorMsg(err) || 'Failed to update credential');
    } finally {
      setSaving(false);
    }
  };

  const startOAuthConnect = async () => {
    try {
      setOauthConnectLoading(true);
      onError('');
      await api.updateFlowCredential(row.credential_id, {
        name: name.trim(),
        fields: buildFieldsPayload(),
      });
      const { authorization_url } = await api.initiateFlowOAuthConnect(row.credential_id);
      window.location.href = authorization_url;
    } catch (err) {
      onError(getApiErrorMsg(err) || 'Could not start OAuth');
      setOauthConnectLoading(false);
    }
  };

  const onSecretChange = (fieldName: string, value: string) => {
    setFields((prev) => ({ ...prev, [fieldName]: value }));
    if (!isCredentialSecretMaskValue(value)) {
      setSecretMasked((prev) => {
        if (!prev.has(fieldName)) return prev;
        const next = new Set(prev);
        next.delete(fieldName);
        return next;
      });
    }
  };

  const kindLabel = kind?.display_name || row.kind_key;

  return (
    <CredEditModalShell onClose={onClose}>
      <header className="relative shrink-0 border-b border-gray-200 px-5 py-4">
        <button
          type="button"
          className="absolute right-3 top-3 rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close"
          onClick={onClose}
        >
          <XMarkIcon className="h-5 w-5" />
        </button>
        <div className="flex min-w-0 flex-col gap-1 pr-8">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            aria-label="Credential name"
            className="min-w-0 border-0 bg-transparent p-0 text-lg font-semibold text-gray-900 outline-none ring-0 placeholder:text-gray-400 focus:border-b focus:border-blue-500"
            placeholder="Enter name…"
          />
          <span className="text-sm text-gray-500">{kindLabel}</span>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="flex min-h-[min(420px,55vh)]">
          <nav
            className="flex w-36 shrink-0 flex-col gap-0.5 border-r border-gray-200 bg-gray-50/80 py-3 pr-2"
            aria-label="Credential sections"
          >
            {(
              [
                ['connection', 'Connection'],
                ['details', 'Details'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`rounded-r-md border-l-2 px-3 py-2 text-left text-sm font-medium transition ${
                  tab === id
                    ? 'border-blue-600 bg-white text-blue-700 shadow-sm'
                    : 'border-transparent text-gray-600 hover:bg-white/80 hover:text-gray-900'
                }`}
                onClick={() => setTab(id)}
              >
                {label}
              </button>
            ))}
          </nav>

          <div className="flex-1 px-5 py-4">
            {tab === 'connection' ? (
              <CredEditConnectionTab
                fieldDefs={fieldDefs}
                fields={fields}
                secretMasked={secretMasked}
                showSecret={showSecret}
                supportsOAuth={supportsOAuth}
                oauthConnected={oauthConnected}
                oauthConnectLoading={oauthConnectLoading}
                onSecretChange={onSecretChange}
                setFields={setFields}
                setShowSecret={setShowSecret}
                onOAuthConnect={() => void startOAuthConnect()}
              />
            ) : (
              <CredEditDetailsTab row={row} />
            )}
          </div>
        </div>
      </div>

      <footer className="flex shrink-0 justify-end gap-2 border-t border-gray-200 px-5 py-3">
        <button type="button" className={btnSecondary} onClick={onClose} disabled={saving}>
          Cancel
        </button>
        <button type="button" className={btnPrimary} onClick={() => void submit()} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </footer>
    </CredEditModalShell>
  );
};

function CredEditModalShell({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[280] flex items-center justify-center p-4" role="presentation">
      <button
        type="button"
        className="absolute inset-0 bg-black/50"
        aria-label="Close dialog"
        onClick={onClose}
      />
      <CredEditModalPanel>{children}</CredEditModalPanel>
    </div>
  );
}

function CredEditModalPanel({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="relative z-10 flex max-h-[min(90vh,40rem)] w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-xl"
      role="dialog"
      aria-modal="true"
    >
      {children}
    </div>
  );
}

function CredEditConnectionTab({
  fieldDefs,
  fields,
  secretMasked,
  showSecret,
  supportsOAuth,
  oauthConnected,
  oauthConnectLoading,
  onSecretChange,
  setFields,
  setShowSecret,
  onOAuthConnect,
}: {
  fieldDefs: ReturnType<typeof credentialFieldRows>;
  fields: Record<string, string>;
  secretMasked: Set<string>;
  showSecret: Record<string, boolean>;
  supportsOAuth: boolean;
  oauthConnected: boolean;
  oauthConnectLoading: boolean;
  onSecretChange: (name: string, value: string) => void;
  setFields: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  setShowSecret: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  onOAuthConnect: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      {supportsOAuth ? (
        <OAuthConnectBanner
          connected={oauthConnected}
          loading={oauthConnectLoading}
          onConnect={onOAuthConnect}
        />
      ) : null}
      {fieldDefs.map((f) => (
        <div key={f.name}>
          <label className={flowLabelClass} htmlFor={`cred-edit-${f.name}`}>
            {f.title || f.name}
          </label>
          <CredentialSecretInput
            id={`cred-edit-${f.name}`}
            field={f}
            value={fields[f.name] ?? ''}
            showSecret={showSecret[f.name]}
            isMasked={secretMasked.has(f.name)}
            onChange={(v) =>
              f.is_secret ? onSecretChange(f.name, v) : setFields((p) => ({ ...p, [f.name]: v }))
            }
            onToggleSecret={
              f.is_secret
                ? () => setShowSecret((s) => ({ ...s, [f.name]: !s[f.name] }))
                : undefined
            }
          />
          {f.description ? <p className="mt-1 text-xs text-gray-500">{f.description}</p> : null}
        </div>
      ))}
    </div>
  );
}

function CredEditDetailsTab({ row }: { row: FlowCredentialHeader }) {
  return (
    <dl className="m-0 space-y-4 text-sm text-gray-800">
      <DetailsRow label="Created">{formatRelativeTime(row.created_at)}</DetailsRow>
      <DetailsRow label="Last modified">{formatRelativeTime(row.updated_at)}</DetailsRow>
      <DetailsRow label="ID" mono>
        {row.credential_id}
      </DetailsRow>
    </dl>
  );
}

function CredentialSecretInput({
  id,
  field,
  value,
  showSecret,
  isMasked,
  onChange,
  onToggleSecret,
}: {
  id: string;
  field: { is_secret?: boolean };
  value: string;
  showSecret?: boolean;
  isMasked: boolean;
  onChange: (v: string) => void;
  onToggleSecret?: () => void;
}) {
  const usePassword = field.is_secret && !showSecret && (isMasked || value.length > 0);
  return (
    <div className="relative">
      <input
        id={id}
        className={field.is_secret ? `${flowInputClass} pr-10` : flowInputClass}
        type={usePassword ? 'password' : 'text'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
      />
      {onToggleSecret ? (
        <button
          type="button"
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          aria-label={showSecret ? 'Hide value' : 'Show value'}
          onClick={onToggleSecret}
        >
          {showSecret ? <EyeSlashIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
        </button>
      ) : null}
    </div>
  );
}

function OAuthConnectBanner({
  connected,
  loading,
  onConnect,
}: {
  connected: boolean;
  loading: boolean;
  onConnect: () => void;
}) {
  if (connected) {
    return (
      <div className="flex flex-col gap-3 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
        <div className="flex items-center gap-2 font-medium">
          <CheckCircleIcon className="h-5 w-5 shrink-0 text-emerald-600" aria-hidden />
          Account connected
        </div>
        <button type="button" className={btnSecondary} disabled={loading} onClick={onConnect}>
          {loading ? 'Redirecting…' : 'Reconnect'}
        </button>
      </div>
    );
  }
  return (
    <div className="rounded-md border border-blue-100 bg-blue-50/90 px-4 py-3 text-sm text-blue-950">
      <button type="button" className={btnPrimary} disabled={loading} onClick={onConnect}>
        {loading ? 'Redirecting…' : 'Connect with provider'}
      </button>
      <p className="mt-2 text-xs leading-relaxed text-blue-900">
        Save connection settings first, then sign in with the provider to obtain access and refresh
        tokens.
      </p>
    </div>
  );
}

function DetailsRow({
  label,
  mono,
  children,
}: {
  label: string;
  mono?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</dt>
      <dd className={`mt-0.5 break-all ${mono ? 'font-mono text-xs' : ''}`}>{children}</dd>
    </div>
  );
}

export default FlowCredentialEditModal;
