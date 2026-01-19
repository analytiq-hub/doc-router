'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { apiClient, getApiErrorMsg } from '@/utils/api';
import { toast } from 'react-toastify';
import { useAppSession } from '@/contexts/AppSessionContext';
import { isOrgAdmin, isSysAdmin } from '@/utils/roles';
import {
  Send as SendIcon,
  Refresh as RefreshIcon,
  Replay as RetryIcon,
  Close as CloseIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';
import { useOrganizationData } from '@/hooks/useOrganizationData';
import type { Organization as UiOrganization } from '@/types/organizations';
import { copyToClipboard } from '@/utils/clipboard';

type WebhookEventType =
  | 'document.uploaded'
  | 'document.error'
  | 'llm.completed'
  | 'llm.error'
  | 'webhook.test';

interface WebhookConfigResponse {
  enabled: boolean;
  url: string | null;
  events: Array<WebhookEventType> | null;
  secret_set: boolean;
  secret_preview?: string | null;
  generated_secret?: string | null;
  auth_type?: 'hmac' | 'header' | null;
  auth_header_name?: string | null;
  auth_header_set?: boolean | null;
  auth_header_preview?: string | null;
}

interface WebhookDeliveryItem {
  id: string;
  event_id: string;
  event_type: string;
  status: string;
  attempts: number;
  max_attempts: number;
  document_id?: string | null;
  prompt_revid?: string | null;
  last_http_status?: number | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
  next_attempt_at?: string | null;
}

interface DeliveriesResponse {
  deliveries: WebhookDeliveryItem[];
  total_count: number;
  skip: number;
}

interface WebhookConfigSnapshot {
  enabled: boolean;
  url: string;
  events: WebhookEventType[];
  authType: 'hmac' | 'header';
  authHeaderName: string;
}

const CONFIG_EVENTS: Array<Exclude<WebhookEventType, 'webhook.test'>> = [
  'document.uploaded',
  'document.error',
  'llm.completed',
  'llm.error',
];

const normalizeWebhookEvents = (
  incoming?: Array<WebhookEventType> | null
): WebhookEventType[] => {
  if (!incoming || incoming.length === 0) {
    return CONFIG_EVENTS;
  }
  const normalized = new Set<WebhookEventType>();
  for (const ev of incoming) {
    if (ev === 'webhook.test') continue;
    normalized.add(ev);
  }
  return normalized.size > 0 ? Array.from(normalized) : CONFIG_EVENTS;
};

const normalizeEventList = (incoming: WebhookEventType[]) =>
  [...incoming].filter((ev) => ev !== 'webhook.test').sort();

type DeliveryDetails = Record<string, unknown>;

export default function OrganizationWebhooks({ organizationId }: { organizationId: string }) {
  const { session } = useAppSession();
  const { organization, loading: orgLoading } = useOrganizationData(organizationId);
  const canEdit = useMemo(
    () => isSysAdmin(session) || (organization ? isOrgAdmin(organization as unknown as UiOrganization, session) : false),
    [organization, session]
  );

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const [enabled, setEnabled] = useState(false);
  const [url, setUrl] = useState('');
  const [secret, setSecret] = useState('');
  const [secretSet, setSecretSet] = useState(false);
  const [secretPreview, setSecretPreview] = useState<string | null>(null);
  const [events, setEvents] = useState<WebhookEventType[]>(CONFIG_EVENTS);
  const [generatedSecret, setGeneratedSecret] = useState<string | null>(null);
  const [authType, setAuthType] = useState<'hmac' | 'header'>('hmac');
  const [authHeaderName, setAuthHeaderName] = useState('Authorization');
  const [authHeaderValue, setAuthHeaderValue] = useState('');
  const [authHeaderPreview, setAuthHeaderPreview] = useState<string | null>(null);
  const [initialConfig, setInitialConfig] = useState<WebhookConfigSnapshot | null>(null);

  const [deliveries, setDeliveries] = useState<WebhookDeliveryItem[]>([]);
  const [deliveriesLoading, setDeliveriesLoading] = useState(false);
  const [deliveriesTotal, setDeliveriesTotal] = useState(0);
  const [page, setPage] = useState(0); // 0-based
  const [pageSize, setPageSize] = useState(25);

  const [selectedDeliveryId, setSelectedDeliveryId] = useState<string | null>(null);
  const [deliveryDetails, setDeliveryDetails] = useState<DeliveryDetails | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  const loadConfig = useCallback(async () => {
    const res = await apiClient.get<WebhookConfigResponse>(`/v0/orgs/${organizationId}/webhook`);
    const normalizedEvents = normalizeWebhookEvents(res.data.events);
    const resolvedAuthType = (res.data.auth_type as 'hmac' | 'header' | null) ?? 'hmac';
    const resolvedAuthHeaderName = res.data.auth_header_name ?? 'Authorization';
    setEnabled(res.data.enabled);
    setUrl(res.data.url ?? '');
    setSecretSet(res.data.secret_set);
    setSecretPreview(res.data.secret_preview ?? null);
    setEvents(normalizedEvents);
    setAuthType(resolvedAuthType);
    setAuthHeaderName(resolvedAuthHeaderName);
    setAuthHeaderPreview(res.data.auth_header_preview ?? null);
    setInitialConfig({
      enabled: res.data.enabled,
      url: res.data.url ?? '',
      events: normalizedEvents,
      authType: resolvedAuthType,
      authHeaderName: resolvedAuthHeaderName,
    });
  }, [organizationId]);

  const loadDeliveries = useCallback(async () => {
    setDeliveriesLoading(true);
    try {
      const skip = page * pageSize;
      const res = await apiClient.get<DeliveriesResponse>(`/v0/orgs/${organizationId}/webhook/deliveries`, {
        params: { skip, limit: pageSize },
      });
      setDeliveries(res.data.deliveries);
      setDeliveriesTotal(res.data.total_count);
    } finally {
      setDeliveriesLoading(false);
    }
  }, [organizationId, page, pageSize]);

  const loadDeliveryDetails = useCallback(
    async (deliveryId: string) => {
      setDetailsLoading(true);
      try {
        const res = await apiClient.get(`/v0/orgs/${organizationId}/webhook/deliveries/${deliveryId}`);
        setDeliveryDetails(res.data);
      } finally {
        setDetailsLoading(false);
      }
    },
    [organizationId]
  );

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        await loadConfig();
        await loadDeliveries();
      } catch (e) {
        toast.error(getApiErrorMsg(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [loadConfig, loadDeliveries]);

  const toggleEvent = (ev: WebhookEventType) => {
    setEvents((prev) => (prev.includes(ev) ? prev.filter((x) => x !== ev) : [...prev, ev]));
  };

  const isDirty = useMemo(() => {
    if (!initialConfig) return false;
    const trimmedUrl = url.trim();
    const initialUrl = initialConfig.url.trim();
    const eventsMatch =
      normalizeEventList(events).join(',') === normalizeEventList(initialConfig.events).join(',');
    const hasSecretChange = authType === 'hmac' && secret.trim().length > 0;
    const hasHeaderValueChange = authType === 'header' && authHeaderValue.trim().length > 0;

    return (
      enabled !== initialConfig.enabled ||
      trimmedUrl !== initialUrl ||
      !eventsMatch ||
      authType !== initialConfig.authType ||
      authHeaderName.trim() !== initialConfig.authHeaderName.trim() ||
      hasSecretChange ||
      hasHeaderValueChange
    );
  }, [authHeaderName, authHeaderValue, authType, enabled, events, initialConfig, secret, url]);

  const save = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/v0/orgs/${organizationId}/webhook`, {
        enabled,
        url: url.trim() || null,
        events,
        auth_type: authType,
        auth_header_name: authHeaderName.trim() || null,
        ...(authHeaderValue.trim().length > 0 ? { auth_header_value: authHeaderValue } : {}),
        // If secret is blank, do not update it.
        ...(secret.trim().length > 0 ? { secret: secret.trim() } : {}),
      });
      setSecret('');
      setAuthHeaderValue('');
      toast.success('Webhook settings saved');
      await loadConfig();
    } catch (e) {
      toast.error(getApiErrorMsg(e));
    } finally {
      setSaving(false);
    }
  };

  const regenerateSecret = async () => {
    setSaving(true);
    try {
      const res = await apiClient.put<WebhookConfigResponse>(`/v0/orgs/${organizationId}/webhook`, {
        secret: '',
      });
      await loadConfig();
      const newSecret = res.data.generated_secret ?? null;
      if (newSecret) {
        setGeneratedSecret(newSecret);
      } else {
        toast.success('Secret regenerated');
      }
    } catch (e) {
      toast.error(getApiErrorMsg(e));
    } finally {
      setSaving(false);
    }
  };

  const testWebhook = async () => {
    setTesting(true);
    try {
      const res = await apiClient.post<{ status: string; delivery_id: string }>(
        `/v0/orgs/${organizationId}/webhook/test`
      );
      toast.success(`Test enqueued (delivery ${res.data.delivery_id})`);
      await loadDeliveries();
    } catch (e) {
      toast.error(getApiErrorMsg(e));
    } finally {
      setTesting(false);
    }
  };

  const openDetails = async (deliveryId: string) => {
    setSelectedDeliveryId(deliveryId);
    setDeliveryDetails(null);
    try {
      await loadDeliveryDetails(deliveryId);
    } catch (e) {
      toast.error(getApiErrorMsg(e));
    }
  };

  const closeDetails = () => {
    setSelectedDeliveryId(null);
    setDeliveryDetails(null);
  };

  const retryDelivery = async (deliveryId: string) => {
    try {
      await apiClient.post(`/v0/orgs/${organizationId}/webhook/deliveries/${deliveryId}/retry`);
      toast.success('Retry enqueued');
      await loadDeliveries();
      if (selectedDeliveryId === deliveryId) {
        await loadDeliveryDetails(deliveryId);
      }
    } catch (e) {
      toast.error(getApiErrorMsg(e));
    }
  };

  if (loading || orgLoading) {
    return (
      <div className="flex items-center justify-center p-4">
        <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
        Loading...
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto min-h-[calc(100vh-80px)]">
      {/* Gray header panel: title left, actions right */}
      <div className="mb-4 bg-gray-50 rounded-lg px-0 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold text-gray-900">Organization Webhook</h2>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={save}
              disabled={!canEdit || saving || !isDirty}
              className="inline-flex items-center justify-center px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              onClick={testWebhook}
              disabled={!canEdit || testing}
              className="inline-flex items-center justify-center px-4 py-2 rounded-md border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-50"
            >
              <SendIcon fontSize="small" className="mr-2" />
              Test webhook
            </button>
          </div>
        </div>
      </div>

      {/* Main card */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="mb-8">
        <div className="flex flex-col md:flex-row md:items-center gap-3">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Webhook URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={!canEdit}
              placeholder="https://example.com/webhook"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white disabled:bg-gray-100"
            />
          </div>

          <div className="md:w-32 md:flex md:justify-center">
            <label className="inline-flex items-center gap-2 text-sm md:mt-6">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                disabled={!canEdit}
                className="h-4 w-4"
              />
              Enabled
            </label>
          </div>
        </div>

        <div className="mt-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Authentication Method</label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 items-center">
              <div className="md:col-span-1">
                <select
                  value={authType}
                  onChange={(e) => setAuthType(e.target.value as 'hmac' | 'header')}
                  disabled={!canEdit}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white disabled:bg-gray-100"
                >
                  <option value="hmac">HMAC signature</option>
                  <option value="header">Header Auth</option>
                </select>
              </div>
              <div className="md:col-span-2 text-xs text-gray-600">
                {authType === 'hmac' ? (
                  <div>
                    DocRouter sends body signature in <span className="font-mono">X-DocRouter-Signature</span>.
                  </div>
                ) : (
                  <div>DocRouter sends a static auth header (works with n8n Webhook “Header Auth”).</div>
                )}
              </div>
            </div>
          </div>

          {authType === 'header' ? (
            <div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 items-end">
                <div className="md:col-span-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Header name</label>
                  <input
                    type="text"
                    value={authHeaderName}
                    onChange={(e) => setAuthHeaderName(e.target.value)}
                    disabled={!canEdit}
                    placeholder="Authorization"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white disabled:bg-gray-100"
                  />
                </div>
                <div className="md:col-span-2">
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-sm font-medium text-gray-700">Header value</label>
                    <div className="text-xs text-gray-500">
                      {authHeaderPreview ? <span className="font-mono">Header Value begins with: {authHeaderPreview}</span> : 'Not set'}
                    </div>
                  </div>
                  <input
                    type="password"
                    value={authHeaderValue}
                    onChange={(e) => setAuthHeaderValue(e.target.value)}
                    disabled={!canEdit}
                    placeholder="Enter header value (leave blank to keep)"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white disabled:bg-gray-100"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between gap-3 mb-1">
                <label className="block text-sm font-medium text-gray-700">Webhook secret</label>
                <div className="text-xs text-gray-500">
                  {secretPreview ? (
                    <span className="font-mono">Secret begins with: {secretPreview}</span>
                  ) : secretSet ? (
                    'Secret is set'
                  ) : (
                    'Not set'
                  )}
                </div>
              </div>
              <div className="flex flex-col md:flex-row gap-2">
                <input
                  type="password"
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  disabled={!canEdit}
                  placeholder="Enter new secret (leave blank to keep)"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white disabled:bg-gray-100"
                />
                <button
                  type="button"
                  onClick={regenerateSecret}
                  disabled={!canEdit || saving}
                  className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                >
                  Regenerate
                </button>
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Events</label>
            <div className="flex flex-col gap-2">
              {CONFIG_EVENTS.map((ev) => (
                <label key={ev} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={events.includes(ev)}
                    onChange={() => toggleEvent(ev)}
                    disabled={!canEdit}
                    className="h-4 w-4"
                  />
                  <span className="font-mono text-xs">{ev}</span>
                </label>
              ))}
            </div>
            <div className="text-xs text-gray-500 mt-2">
              Note: the “Test webhook” button sends a <span className="font-mono">webhook.test</span> event and does not
              require enabling it in the event list.
            </div>
          </div>

          {!canEdit && (
            <div className="text-sm text-gray-600">
              Only organization admins (or system admins) can change webhook settings.
            </div>
          )}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-medium text-gray-900">Recent deliveries</h3>
          <div className="flex items-center gap-3">
            <div className="text-sm text-gray-600">
              {deliveriesLoading ? 'Loading…' : `${deliveries.length} shown (total ${deliveriesTotal})`}
            </div>
            <button
              type="button"
              onClick={() => loadDeliveries()}
              className="inline-flex items-center px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
              disabled={deliveriesLoading}
              title="Refresh deliveries"
            >
              <RefreshIcon fontSize="small" className="mr-2" />
              Refresh
            </button>
          </div>
        </div>

        <div className="overflow-x-auto border border-gray-200 rounded-md">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-gray-700">
              <tr>
                <th className="text-left px-3 py-2">Status</th>
                <th className="text-left px-3 py-2">Event</th>
                <th className="text-left px-3 py-2">Doc</th>
                <th className="text-left px-3 py-2">Prompt</th>
                <th className="text-left px-3 py-2">Attempts</th>
                <th className="text-left px-3 py-2">HTTP</th>
                <th className="text-left px-3 py-2">Updated</th>
                <th className="text-right px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {deliveries.map((d) => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2 font-medium">{d.status}</td>
                  <td className="px-3 py-2 font-mono text-xs">{d.event_type}</td>
                  <td className="px-3 py-2 font-mono text-xs">{d.document_id || '-'}</td>
                  <td className="px-3 py-2 font-mono text-xs">{d.prompt_revid || '-'}</td>
                  <td className="px-3 py-2">
                    {d.attempts}/{d.max_attempts}
                  </td>
                  <td className="px-3 py-2">{d.last_http_status ?? '-'}</td>
                  <td className="px-3 py-2">{new Date(d.updated_at).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => openDetails(d.id)}
                      className="text-sm text-blue-700 hover:text-blue-900"
                    >
                      Details
                    </button>
                    {canEdit && d.status === 'failed' && (
                      <button
                        type="button"
                        onClick={() => retryDelivery(d.id)}
                        className="ml-3 inline-flex items-center text-sm text-gray-700 hover:text-gray-900"
                        title="Retry"
                      >
                        <RetryIcon fontSize="small" className="mr-1" />
                        Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {deliveries.length === 0 && !deliveriesLoading && (
                <tr>
                  <td className="px-3 py-6 text-center text-gray-500" colSpan={8}>
                    No deliveries yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mt-3">
          <div className="text-sm text-gray-600">
            Page {page + 1} of {Math.max(1, Math.ceil(deliveriesTotal / pageSize))}
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-700">
              Page size
              <select
                className="ml-2 border border-gray-300 rounded-md px-2 py-1 bg-white"
                value={pageSize}
                onChange={(e) => {
                  setPageSize(parseInt(e.target.value, 10));
                  setPage(0);
                }}
              >
                {[10, 25, 50, 100].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="px-3 py-1 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || deliveriesLoading}
            >
              Prev
            </button>
            <button
              type="button"
              className="px-3 py-1 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * pageSize >= deliveriesTotal || deliveriesLoading}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Details drawer */}
      {selectedDeliveryId && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/30" onClick={closeDetails} />
          <div className="absolute right-0 top-0 h-full w-full max-w-2xl bg-white shadow-xl flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <div>
                <div className="text-sm text-gray-600">Delivery</div>
                <div className="font-mono text-xs">{selectedDeliveryId}</div>
              </div>
              <button
                type="button"
                onClick={closeDetails}
                className="p-2 rounded-md hover:bg-gray-100"
                aria-label="Close"
              >
                <CloseIcon fontSize="small" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {detailsLoading && <div className="text-sm text-gray-600">Loading…</div>}
              {!detailsLoading && deliveryDetails && (
                <pre className="text-xs bg-gray-50 border border-gray-200 rounded-md p-3 overflow-x-auto">
                  {JSON.stringify(deliveryDetails, null, 2)}
                </pre>
              )}
            </div>

            <div className="px-4 py-3 border-t flex justify-between items-center">
              <div className="text-xs text-gray-500">Tip: use event_id to de-dupe on your side.</div>
              {canEdit && (
                <button
                  type="button"
                  onClick={() => retryDelivery(selectedDeliveryId)}
                  className="inline-flex items-center px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  <RetryIcon fontSize="small" className="mr-2" />
                  Retry
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Generated secret modal (Tailwind only) */}
      {generatedSecret && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/30" onClick={() => setGeneratedSecret(null)} />
          <div className="relative w-full max-w-md bg-white rounded-lg shadow-xl">
            <button
              type="button"
              onClick={() => setGeneratedSecret(null)}
              className="absolute right-3 top-3 p-2 rounded-md hover:bg-gray-100 text-gray-600"
              aria-label="Close"
            >
              <CloseIcon fontSize="small" />
            </button>

            <div className="p-6">
              <div className="text-xl font-semibold">New webhook secret</div>
              <div className="text-sm text-gray-600 mt-2">Copy this secret now. It is shown only once.</div>

              <div className="mt-4 flex items-center justify-between gap-2 p-2 bg-gray-100 rounded">
                <span className="font-mono text-xs break-all">{generatedSecret}</span>
                <button
                  type="button"
                  onClick={async () => {
                    await copyToClipboard(generatedSecret);
                    toast.success('Copied');
                  }}
                  className="inline-flex items-center p-2 rounded-full bg-gray-200 shadow-md hover:bg-gray-300 hover:shadow-lg text-gray-700"
                  title="Copy"
                >
                  <CopyIcon fontSize="small" />
                </button>
              </div>

              <button
                type="button"
                onClick={() => setGeneratedSecret(null)}
                className="mt-6 w-full sm:w-auto sm:ml-auto block px-4 py-2 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

