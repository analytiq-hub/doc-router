'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterAccountApi } from '@/utils/api';
import { getApiErrorMsg } from '@/utils/api';
import type { AzureServicePrincipalConfig } from '@docrouter/sdk';

const AzureConfigManager: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [config, setConfig] = useState<AzureServicePrincipalConfig | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [tenantId, setTenantId] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [apiBase, setApiBase] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const c = await docRouterAccountApi.getAzureConfig();
        if (!cancelled) setConfig(c);
      } catch {
        if (!cancelled) setConfig(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [docRouterAccountApi]);

  const handleOpenEdit = () => {
    setTenantId(config?.tenant_id?.trim() ?? '');
    setClientId(config?.client_id?.trim() ?? '');
    setClientSecret('');
    setApiBase(config?.api_base?.trim() ?? '');
    setError(null);
    setEditOpen(true);
  };

  const handleSave = async () => {
    setError(null);
    const t = tenantId.trim();
    const c = clientId.trim();
    const s = clientSecret.trim();
    const b = apiBase.trim().replace(/\/+$/, '');
    if (!t || !c || !s || !b) {
      setError('Tenant ID, Client ID, Client secret, and API base URL are required.');
      return;
    }
    if (!/^https:\/\//i.test(b)) {
      setError('API base URL must start with https://');
      return;
    }
    try {
      await docRouterAccountApi.createAzureConfig({
        tenant_id: t,
        client_id: c,
        client_secret: s,
        api_base: b,
      });
      setEditOpen(false);
      try {
        setConfig(await docRouterAccountApi.getAzureConfig());
      } catch {
        setConfig(null);
      }
    } catch (e: unknown) {
      setError(getApiErrorMsg(e) || 'Failed to save Azure configuration.');
    }
  };

  const handleDelete = async () => {
    setError(null);
    try {
      await docRouterAccountApi.deleteAzureConfig();
      setConfig(null);
    } catch (e: unknown) {
      setError(getApiErrorMsg(e) || 'Failed to delete Azure configuration.');
    }
  };

  const configured = Boolean(config?.tenant_id);

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-medium text-gray-900">Microsoft Entra (service principal)</h2>
          <button
            type="button"
            onClick={handleOpenEdit}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {configured ? 'Edit credentials' : 'Add credentials'}
          </button>
        </div>
        <p className="text-sm text-gray-600 mb-3">
          Application (client) credentials for Azure AI Foundry and LiteLLM (tenant ID, client ID, client secret from
          your app registration). Set the Foundry API base (HTTPS endpoint used as the LiteLLM api_base). Service
          principal fields are encrypted server-side except API base (plaintext). Only the client secret is masked when
          viewing saved configuration.
        </p>
        <p className="text-sm">
          <b>Status:</b>{' '}
          {configured ? (
            <span className="text-green-600">Configured</span>
          ) : (
            <span className="text-yellow-600">Not configured</span>
          )}
        </p>
        {configured && config && (
          <div className="mt-4 text-sm space-y-1 font-mono text-gray-800">
            <div>
              <span className="text-gray-500">Tenant ID:</span> {config.tenant_id}
            </div>
            <div>
              <span className="text-gray-500">Client ID:</span> {config.client_id}
            </div>
            <div>
              <span className="text-gray-500">Client secret:</span> {config.client_secret}
            </div>
            <div className="break-all">
              <span className="text-gray-500">API base:</span> {config.api_base}
            </div>
          </div>
        )}
        {configured && (
          <button
            type="button"
            onClick={handleDelete}
            className="mt-3 px-3 py-1.5 text-sm text-red-700 border border-red-300 rounded hover:bg-red-50"
          >
            Remove Azure credentials
          </button>
        )}
        {error && !editOpen && <p className="text-red-600 text-sm mt-2">{error}</p>}
      </div>

      <div className="bg-blue-50 rounded-lg shadow p-4">
        <span className="list-decimal list-inside space-y-2 text-blue-900">
          Change Azure Configuration for on-prem installs only. Contact Support for additional instructions.
        </span>
      </div>

      {editOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-4">
              <h2 className="text-xl font-semibold">Azure service principal</h2>
              <button
                type="button"
                onClick={() => setEditOpen(false)}
                className="text-gray-500 hover:text-gray-700"
                aria-label="Close"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Directory (tenant) ID</label>
            <input
              type="text"
              className="w-full mb-3 px-3 py-2 border border-gray-300 rounded text-sm font-mono"
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              value={tenantId}
              onChange={(e) => {
                setTenantId(e.target.value);
                setError(null);
              }}
            />
            <label className="block text-sm font-medium text-gray-700 mb-1">Application (client) ID</label>
            <input
              type="text"
              className="w-full mb-3 px-3 py-2 border border-gray-300 rounded text-sm font-mono"
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              value={clientId}
              onChange={(e) => {
                setClientId(e.target.value);
                setError(null);
              }}
            />
            <label className="block text-sm font-medium text-gray-700 mb-1">Client secret</label>
            <input
              type="password"
              className="w-full mb-3 px-3 py-2 border border-gray-300 rounded text-sm font-mono"
              placeholder="From Certificates & secrets"
              value={clientSecret}
              onChange={(e) => {
                setClientSecret(e.target.value);
                setError(null);
              }}
            />
            <label className="block text-sm font-medium text-gray-700 mb-1">
              API base URL (Foundry endpoint)
            </label>
            <input
              type="url"
              className="w-full mb-3 px-3 py-2 border border-gray-300 rounded text-sm font-mono"
              placeholder="https://your-resource.services.ai.azure.com"
              value={apiBase}
              onChange={(e) => {
                setApiBase(e.target.value);
                setError(null);
              }}
            />
            {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={() => setEditOpen(false)}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={
                  !tenantId.trim() ||
                  !clientId.trim() ||
                  !clientSecret.trim() ||
                  !apiBase.trim()
                }
                className="px-4 py-2 text-sm text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AzureConfigManager;
