'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Switch } from '@headlessui/react';
import {
  BeakerIcon,
  CheckCircleIcon,
  EyeIcon,
  EyeSlashIcon,
  QuestionMarkCircleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import type { FlowCredentialHeader, FlowCredentialKindSummary } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import type { DocRouterOrgApi } from '@/utils/api';
import { formatRelativeTime } from '@/utils/date';
import { copyToClipboard } from '@/utils/clipboard';
import { toast } from 'react-toastify';
import {
  flowInlineNameInputClass,
  flowInlineNameMeasureClass,
  flowInlineNameReadClass,
  flowInputClass,
  flowLabelClass,
  flowSelectClass,
  flowSwitchThumbClass,
  flowSwitchTrackClass,
} from './flowUiClasses';
import { useInlineNameWidthPx } from './useInlineNameWidthPx';
import {
  buildCredentialFieldsPayload,
  CREDENTIAL_SECRET_MASK,
  credentialFieldDisplayValue,
  credentialFieldInitialValue,
  credentialFieldRowVisible,
  credentialFieldRows,
  credentialFormSnapshotsEqual,
  parseCredentialBooleanField,
  type CredentialFieldRow,
  credentialKindShowsTestButton,
  credentialOAuthHintAppName,
  type CredentialFormSnapshot,
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
  onSaved: (row?: FlowCredentialHeader) => void | Promise<void>;
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
  const editRow = mode === 'edit' ? props.row : null;
  const createInitialName = mode === 'create' ? props.initialName : '';
  const formResetKey =
    mode === 'edit'
      ? `${props.row.credential_id}:${props.row.updated_at ?? ''}:${props.row.secret_fields_set?.join(',') ?? ''}`
      : `create:${props.kindKey}`;

  const [tab, setTab] = useState<EditTab>('connection');
  const [name, setName] = useState(mode === 'edit' ? props.row.name : props.initialName);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [secretMasked, setSecretMasked] = useState<Set<string>>(() => new Set());
  const [showSecret, setShowSecret] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [oauthConnectLoading, setOauthConnectLoading] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [testDetail, setTestDetail] = useState<string | null>(null);
  const [savedSnapshot, setSavedSnapshot] = useState<CredentialFormSnapshot | null>(null);
  const [formEpoch, setFormEpoch] = useState(0);

  const fieldDefs = useMemo(() => credentialFieldRows(kind), [kind]);
  const secretFieldsSet = useMemo(
    () => new Set(row?.secret_fields_set ?? []),
    [row?.secret_fields_set],
  );

  const initForm = useCallback(() => {
    if (mode === 'edit' && editRow) {
      setName(editRow.name);
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
          next[f.name] = credentialFieldInitialValue(f, row.public_fields[f.name]);
        } else {
          next[f.name] = credentialFieldInitialValue(f, undefined);
        }
      }
    }
    setFields(next);
    setSecretMasked(masked);
    setShowSecret({});
    setTestDetail(null);
    setFormEpoch((n) => n + 1);
  }, [mode, editRow, kind, row, secretFieldsSet]);

  useEffect(() => {
    initForm();
  }, [formResetKey, initForm]);

  useEffect(() => {
    if (!kind || formEpoch === 0) return;
    setSavedSnapshot({
      name: name.trim(),
      fields: buildCredentialFieldsPayload(fieldDefs, fields, secretMasked),
    });
    // Baseline is captured once per form reset (initForm), not on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- formEpoch only
  }, [formEpoch, kind]);

  useEffect(() => {
    if (mode === 'create') {
      setName(createInitialName);
    }
  }, [mode, createInitialName]);

  const supportsOAuth = kind?.supports_oauth_browser_flow === true;
  const oauthConnected = supportsOAuth && secretFieldsSet.has('oauthAccessToken');
  const credentialId = row?.credential_id;

  const currentSnapshot = useMemo(
    (): CredentialFormSnapshot => ({
      name: name.trim(),
      fields: buildCredentialFieldsPayload(fieldDefs, fields, secretMasked),
    }),
    [name, fields, secretMasked, fieldDefs],
  );

  const hasUnsavedChanges = useMemo(() => {
    if (!savedSnapshot) return false;
    return !credentialFormSnapshotsEqual(currentSnapshot, savedSnapshot);
  }, [currentSnapshot, savedSnapshot]);

  const persist = async (): Promise<FlowCredentialHeader | null> => {
    if (!kind) {
      onError('Unknown credential kind');
      return null;
    }
    if (!name.trim()) {
      onError('Credential name cannot be empty');
      return null;
    }
    const payload = { name: currentSnapshot.name, fields: currentSnapshot.fields };
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
      await onSaved(result);
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
                oauthRedirectUri={kind?.oauth_redirect_uri ?? undefined}
                oauthHintAppName={
                  kind ? credentialOAuthHintAppName(kind.display_name) : undefined
                }
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
          <button
            type="button"
            className={btnPrimary}
            onClick={() => void submit()}
            disabled={saving || !kind || !hasUnsavedChanges}
          >
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
  oauthRedirectUri,
  oauthHintAppName,
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
  oauthRedirectUri?: string;
  oauthHintAppName?: string;
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
      {supportsOAuth && oauthRedirectUri ? (
        <OAuthRedirectUrlField redirectUri={oauthRedirectUri} appName={oauthHintAppName} />
      ) : null}
      {fieldDefs
        .filter((f) => credentialFieldRowVisible(f, fields, fieldDefs))
        .map((f) => (
          <CredEditFieldBlock
            key={f.name}
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
        ))}
    </div>
  );
}

function OAuthRedirectUrlField({
  redirectUri,
  appName,
}: {
  redirectUri: string;
  appName?: string;
}) {
  const hint = appName
    ? `In ${appName}, use the URL above when prompted to enter an OAuth callback or redirect URL`
    : 'Use the URL above when prompted to enter an OAuth callback or redirect URL';

  const onCopy = async () => {
    await copyToClipboard(redirectUri);
  };

  return (
    <div>
      <label className={flowLabelClass}>OAuth Redirect URL</label>
      <button
        type="button"
        data-testid="oauth-redirect-url"
        className="group mt-1 flex w-full cursor-pointer items-start justify-between gap-3 rounded-md border border-gray-200 bg-gray-50 px-3 py-2.5 text-left transition hover:border-gray-300 hover:bg-gray-100"
        onClick={() => void onCopy()}
        title="Click to copy"
      >
        <span className="min-w-0 break-all font-mono text-xs leading-relaxed text-gray-800">
          {redirectUri}
        </span>
        <span className="hidden shrink-0 pt-0.5 text-xs font-medium text-gray-500 group-hover:inline group-hover:text-gray-700">
          Click to copy
        </span>
      </button>
      <p className="mt-2 text-xs leading-snug text-gray-500">{hint}</p>
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

function CredEditFieldLabel({
  htmlFor,
  label,
  description,
}: {
  htmlFor?: string;
  label: string;
  description?: string;
}) {
  return (
    <div className="mb-1 flex min-w-0 items-center gap-1">
      {htmlFor ? (
        <label className="mb-0 block text-xs font-medium text-gray-600" htmlFor={htmlFor}>
          {label}
        </label>
      ) : (
        <span className="text-sm text-gray-800">{label}</span>
      )}
      {description ? (
        <span className="group/info relative inline-flex shrink-0 cursor-help opacity-0 transition-opacity duration-150 group-hover/field:opacity-100 group-focus-within/field:opacity-100">
          <QuestionMarkCircleIcon className="h-4 w-4 text-gray-400" aria-hidden />
          <span
            role="tooltip"
            className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-max max-w-[16rem] -translate-x-1/2 rounded-md bg-gray-900 px-2.5 py-1.5 text-xs font-normal leading-snug text-white opacity-0 shadow-lg transition-opacity duration-150 delay-300 group-hover/info:opacity-100 group-focus-within/info:opacity-100"
          >
            {description}
            <span
              className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-gray-900"
              aria-hidden
            />
          </span>
          <span className="sr-only">{description}</span>
        </span>
      ) : null}
    </div>
  );
}

function CredEditFieldBlock({
  field,
  value,
  showSecret,
  isMasked,
  onChange,
  onToggleSecret,
}: {
  field: CredentialFieldRow;
  value: string;
  showSecret?: boolean;
  isMasked: boolean;
  onChange: (v: string) => void;
  onToggleSecret?: () => void;
}) {
  const id = `cred-edit-${field.name}`;
  const label = field.title || field.name;

  if (field.type === 'boolean') {
    const checked = parseCredentialBooleanField(value, field.default === true);
    return (
      <div className="group/field">
        <div className="flex items-center justify-between gap-3 rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2">
          <CredEditFieldLabel label={label} description={field.description} />
          <Switch
            checked={checked}
            onChange={(next) => onChange(next ? 'true' : 'false')}
            className={flowSwitchTrackClass}
          >
            <span className={flowSwitchThumbClass} aria-hidden />
          </Switch>
        </div>
      </div>
    );
  }

  if (field.enum?.length) {
    return (
      <div className="group/field">
        <CredEditFieldLabel htmlFor={id} label={label} description={field.description} />
        <select
          id={id}
          className={flowSelectClass}
          value={value || field.enum[0] || ''}
          onChange={(e) => onChange(e.target.value)}
        >
          {field.enum.map((opt, idx) => (
            <option key={opt} value={opt}>
              {field.enumNames?.[idx] ?? opt}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div className="group/field">
      <CredEditFieldLabel htmlFor={id} label={label} description={field.description} />
      <CredEditFieldInput
        id={id}
        field={field}
        value={value}
        showSecret={showSecret}
        isMasked={isMasked}
        onChange={onChange}
        onToggleSecret={onToggleSecret}
      />
    </div>
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
  field: { is_secret?: boolean; name: string; placeholder?: string };
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
        placeholder={field.placeholder}
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
