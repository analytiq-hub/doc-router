'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { BeakerIcon, CheckCircleIcon, EyeIcon, EyeSlashIcon, XMarkIcon } from '@heroicons/react/24/outline';
import type { FlowCredentialHeader, FlowCredentialKindSummary } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import type { DocRouterOrgApi } from '@/utils/api';
import { formatRelativeTime } from '@/utils/date';
import {
  flowInlineNameInputClass,
  flowInlineNameMeasureClass,
  flowInlineNameReadClass,
  flowInputClass,
  flowLabelClass,
} from './flowUiClasses';
import { useInlineNameWidthPx } from './useInlineNameWidthPx';
import {
  CREDENTIAL_SECRET_MASK,
  credentialFieldDisplayValue,
  credentialFieldRows,
  credentialFieldValueForSubmit,
  credentialKindShowsTestButton,
  formatCredentialTestDetail,
  isCredentialSecretMaskValue,
} from './flowCredentialFieldUtils';

const btnSecondary =
  'rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50';
const btnPrimary =
  'rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50';

type EditTab = 'connection' | 'details';

type FlowCredentialEditModalBaseProps = {
  kind: FlowCredentialKindSummary | null;
  api: DocRouterOrgApi;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
  onError: (message: string) => void;
};

export type FlowCredentialEditModalProps = FlowCredentialEditModalBaseProps &
  (
    | { mode: 'edit'; row: FlowCredentialHeader }
    | { mode: 'create'; kindKey: string; initialName: string }
  );

const FlowCredentialEditModal: React.FC<FlowCredentialEditModalProps> = (props) => {
  const { kind, api, onClose, onSaved, onError, mode } = props;
  const [savedRow, setSavedRow] = useState<FlowCredentialHeader | null>(
    mode === 'edit' ? props.row : null,
  );
  const row = mode === 'edit' ? props.row : savedRow;
  const kindKey = mode === 'edit' ? props.row.kind_key : props.kindKey;

  const [tab, setTab] = useState<EditTab>('connection');
  const [name, setName] = useState(mode === 'edit' ? props.row.name : props.initialName);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [secretMasked, setSecretMasked] = useState<Set<string>>(() => new Set());
  const [showSecret, setShowSecret] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [oauthConnectLoading, setOauthConnectLoading] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [testDetail, setTestDetail] = useState<string | null>(null);

  const fieldDefs = useMemo(() => credentialFieldRows(kind), [kind]);
  const secretFieldsSet = useMemo(
    () => new Set(row?.secret_fields_set ?? []),
    [row?.secret_fields_set],
  );

  const initForm = useCallback(() => {
    if (mode === 'edit') {
      setName(props.row.name);
    }
    setTab('connection');
    const next: Record<string, string> = {};
    const masked = new Set<string>();
    if (kind) {
      for (const f of credentialFieldRows(kind)) {
        if (!f.name) continue;
        if (f.is_secret && row && secretFieldsSet.has(f.name)) {
          next[f.name] = CREDENTIAL_SECRET_MASK;
          masked.add(f.name);
        } else if (f.is_secret) {
          next[f.name] = '';
        } else if (row) {
          next[f.name] = credentialFieldDisplayValue(f, row.public_fields[f.name]);
        } else {
          next[f.name] = '';
        }
      }
    }
    setFields(next);
    setSecretMasked(masked);
    setShowSecret({});
    setTestDetail(null);
  }, [mode, props, kind, row, secretFieldsSet]);

  useEffect(() => {
    initForm();
  }, [initForm]);

  useEffect(() => {
    if (mode === 'create') {
      setName(props.initialName);
    }
  }, [mode, props]);

  const supportsOAuth = kind?.supports_oauth_browser_flow === true;
  const oauthConnected = supportsOAuth && secretFieldsSet.has('oauthAccessToken');
  const credentialId = row?.credential_id;

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

  const persist = async (): Promise<FlowCredentialHeader | null> => {
    if (!kind) {
      onError('Unknown credential kind');
      return null;
    }
    if (!name.trim()) {
      onError('Credential name cannot be empty');
      return null;
    }
    const payload = { name: name.trim(), fields: buildFieldsPayload() };
    if (credentialId) {
      return api.updateFlowCredential(credentialId, payload);
    }
    return api.createFlowCredential({ kind_key: kindKey, ...payload });
  };

  const submit = async () => {
    try {
      setSaving(true);
      onError('');
      const result = await persist();
      if (!result) return;
      if (mode === 'create' && !savedRow) {
        setSavedRow(result);
      }
      await onSaved();
      if (mode === 'edit') {
        onClose();
      }
    } catch (err) {
      onError(getApiErrorMsg(err) || 'Failed to save credential');
    } finally {
      setSaving(false);
    }
  };

  const startOAuthConnect = async () => {
    try {
      setOauthConnectLoading(true);
      onError('');
      let id = credentialId;
      if (!id) {
        const created = await persist();
        if (!created) {
          setOauthConnectLoading(false);
          return;
        }
        setSavedRow(created);
        id = created.credential_id;
        await onSaved();
      } else {
        await persist();
      }
      const { authorization_url } = await api.initiateFlowOAuthConnect(id);
      window.location.href = authorization_url;
    } catch (err) {
      onError(getApiErrorMsg(err) || 'Could not start OAuth');
      setOauthConnectLoading(false);
    }
  };

  const runTest = async () => {
    if (!credentialId) {
      onError('Save the credential before testing the connection');
      return;
    }
    try {
      setTestLoading(true);
      setTestDetail(null);
      onError('');
      await persist();
      const res = await api.testFlowCredential(credentialId);
      setTestDetail(formatCredentialTestDetail(res));
    } catch (err) {
      setTestDetail(getApiErrorMsg(err) || 'Request failed');
    } finally {
      setTestLoading(false);
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

  const kindLabel = kind?.display_name || kindKey;
  const testOk =
    testDetail != null &&
    (testDetail === 'OK' || /^HTTP 2\d\d/.test(testDetail));

  return (
    <CredEditModalShell onClose={onClose}>
      <header className="relative shrink-0 border-b border-gray-200 px-5 py-4">
        <button
          type="button"
          className="absolute right-4 top-4 rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close"
          onClick={onClose}
        >
          <XMarkIcon className="h-5 w-5" />
        </button>
        <CredEditModalHeader name={name} onNameChange={setName} kindLabel={kindLabel} />
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
                connectNeedsSave={!credentialId}
                onSecretChange={onSecretChange}
                setFields={setFields}
                setShowSecret={setShowSecret}
                onOAuthConnect={() => void startOAuthConnect()}
              />
            ) : row ? (
              <CredEditDetailsTab row={row} />
            ) : (
              <p className="m-0 text-sm text-gray-600">
                Save the credential to see created date, last modified, and ID.
              </p>
            )}
          </div>
        </div>
      </div>

      <footer className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-gray-200 px-5 py-3">
        <div className="min-w-0 flex-1">
          {testDetail ? (
            <span
              className={`inline-block max-w-[min(280px,50vw)] truncate text-xs font-medium ${
                testOk ? 'text-emerald-700' : 'text-red-700'
              }`}
              title={testDetail}
            >
              {testDetail}
            </span>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          {credentialKindShowsTestButton(kind) && credentialId ? (
            <button
              type="button"
              className={btnSecondary}
              disabled={testLoading || saving}
              onClick={() => void runTest()}
              title="Test connection"
            >
              <BeakerIcon className="mr-1.5 inline h-4 w-4" aria-hidden />
              {testLoading ? 'Testing…' : 'Test'}
            </button>
          ) : null}
          <button type="button" className={btnSecondary} onClick={onClose} disabled={saving}>
            {mode === 'create' && savedRow ? 'Done' : 'Cancel'}
          </button>
          <button type="button" className={btnPrimary} onClick={() => void submit()} disabled={saving || !kind}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
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
      <div
        className="relative z-10 flex max-h-[min(90vh,40rem)] w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-xl"
        role="dialog"
        aria-modal="true"
      >
        {children}
      </div>
    </div>
  );
}

function CredEditModalHeader({
  name,
  onNameChange,
  kindLabel,
}: {
  name: string;
  onNameChange: (value: string) => void;
  kindLabel: string;
}) {
  const [nameHover, setNameHover] = useState(false);
  const [nameFocus, setNameFocus] = useState(false);
  const showNameField = nameHover || nameFocus;
  const measure = useInlineNameWidthPx(name, 'Credential name');

  return (
    <div className="min-w-0 pr-10">
      <div
        className="max-w-full shrink-0"
        onMouseEnter={() => setNameHover(true)}
        onMouseLeave={() => setNameHover(false)}
      >
        <span
          ref={measure.spanRef}
          className={flowInlineNameMeasureClass}
          style={{
            position: 'absolute',
            visibility: 'hidden',
            pointerEvents: 'none',
            whiteSpace: 'pre',
          }}
          aria-hidden
        >
          {measure.basis}
        </span>
        {showNameField ? (
          <input
            type="text"
            className={flowInlineNameInputClass}
            style={measure.widthPx ? { width: `${measure.widthPx}px` } : undefined}
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            maxLength={100}
            placeholder="Credential name"
            aria-label="Credential name"
            onFocus={() => setNameFocus(true)}
            onBlur={() => setNameFocus(false)}
          />
        ) : (
          <span
            className={flowInlineNameReadClass}
            title={name.trim() ? name : 'Credential name'}
          >
            {name.trim() ? name : 'Unnamed credential'}
          </span>
        )}
      </div>
      <p className="m-0 mt-0.5 text-sm leading-snug text-gray-500">{kindLabel}</p>
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
  connectNeedsSave,
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
  connectNeedsSave: boolean;
  onSecretChange: (fieldName: string, value: string) => void;
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
          connectNeedsSave={connectNeedsSave}
          onConnect={onOAuthConnect}
        />
      ) : null}
      {fieldDefs.map((f) => (
        <div key={f.name}>
          <label className={flowLabelClass} htmlFor={`cred-edit-${f.name}`}>
            {f.title || f.name}
          </label>
          <CredEditFieldInput
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

function CredEditFieldInput({
  id,
  field,
  value,
  showSecret,
  isMasked,
  onChange,
  onToggleSecret,
}: {
  id: string;
  field: { is_secret?: boolean; name: string };
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
  connectNeedsSave,
  onConnect,
}: {
  connected: boolean;
  loading: boolean;
  connectNeedsSave: boolean;
  onConnect: () => void;
}) {
  if (connected) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
        <div className="flex min-w-0 items-center gap-2 font-medium">
          <CheckCircleIcon className="h-5 w-5 shrink-0 text-emerald-600" aria-hidden />
          Account connected
        </div>
        <button
          type="button"
          className={`${btnSecondary} shrink-0`}
          disabled={loading}
          onClick={onConnect}
        >
          {loading ? 'Redirecting…' : 'Reconnect'}
        </button>
      </div>
    );
  }
  return (
    <div className="rounded-md border border-blue-100 bg-blue-50/90 px-4 py-3 text-sm text-blue-950">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="m-0 min-w-0 flex-1 text-sm leading-snug text-blue-950">
          {connectNeedsSave
            ? 'Save connection settings, then sign in with the provider.'
            : 'Sign in with the provider to obtain access and refresh tokens.'}
        </p>
        <button
          type="button"
          className={`${btnPrimary} shrink-0`}
          disabled={loading}
          onClick={onConnect}
        >
          {loading ? 'Redirecting…' : connectNeedsSave ? 'Save and connect' : 'Connect with provider'}
        </button>
      </div>
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
