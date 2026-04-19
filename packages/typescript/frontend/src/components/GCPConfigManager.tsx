import React, { useState, useEffect, useMemo, useCallback } from 'react';
import type { GCPConfig } from '@docrouter/sdk';
import { DocRouterAccountApi } from '@/utils/api';
import { getApiErrorMsg } from '@/utils/api';

const GCPConfigManager: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [gcpConfig, setGcpConfig] = useState<GCPConfig | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [jsonText, setJsonText] = useState('');
  const [fileName, setFileName] = useState('');
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const cfg = await docRouterAccountApi.getGCPConfig();
      setGcpConfig(cfg);
      setConfigured(true);
    } catch {
      setGcpConfig(null);
      setConfigured(false);
    }
  }, [docRouterAccountApi]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const cfg = await docRouterAccountApi.getGCPConfig();
        if (!cancelled) {
          setGcpConfig(cfg);
          setConfigured(true);
        }
      } catch {
        if (!cancelled) {
          setGcpConfig(null);
          setConfigured(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [docRouterAccountApi]);

  const handleSave = async () => {
    setError(null);
    const raw = jsonText.trim();
    if (!raw) {
      setError('Paste or upload a service account JSON file.');
      return;
    }
    try {
      JSON.parse(raw);
    } catch {
      setError('Invalid JSON.');
      return;
    }
    try {
      await docRouterAccountApi.createGCPConfig({ service_account_json: raw });
      setEditOpen(false);
      setJsonText('');
      setFileName('');
      await refresh();
    } catch (e: unknown) {
      setError(getApiErrorMsg(e) || 'Failed to save GCP configuration.');
    }
  };

  const handleDelete = async () => {
    setError(null);
    try {
      await docRouterAccountApi.deleteGCPConfig();
      await refresh();
    } catch (e: unknown) {
      setError(getApiErrorMsg(e) || 'Failed to delete GCP configuration.');
    }
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-medium text-gray-900">GCP (Vertex AI)</h2>
          <button
            type="button"
            onClick={() => {
              setEditOpen(true);
              setJsonText('');
              setFileName('');
              setError(null);
            }}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {configured ? 'Edit JSON key' : 'Add JSON key'}
          </button>
        </div>
        <p className="text-sm text-gray-600 mb-3">
          Service account JSON used for Vertex AI models. The service account must be granted the{' '}
          <b>Vertex AI User</b> role (<code>roles/aiplatform.user</code>) on the project, and the Vertex AI API
          must be enabled.
        </p>
        <p className="text-sm">
          <b>Status:</b>{' '}
          {configured === null ? (
            <span className="text-gray-500">Loading…</span>
          ) : configured ? (
            <span className="text-green-600">Configured</span>
          ) : (
            <span className="text-yellow-600">Not configured</span>
          )}
        </p>
        {configured && gcpConfig && (
          <div className="mt-4 text-sm space-y-1 font-mono text-gray-800">
            <div className="break-all">
              <span className="text-gray-500">Project ID:</span> {gcpConfig.project_id || '—'}
            </div>
            <div className="break-all">
              <span className="text-gray-500">Private key ID:</span> {gcpConfig.private_key_id || '—'}
            </div>
            <div className="break-all">
              <span className="text-gray-500">Service account:</span> {gcpConfig.client_email || '—'}
            </div>
            <div className="break-all">
              <span className="text-gray-500">Client ID:</span> {gcpConfig.client_id || '—'}
            </div>
          </div>
        )}
        {configured && (
          <button
            type="button"
            onClick={handleDelete}
            className="mt-3 px-3 py-1.5 text-sm text-red-700 border border-red-300 rounded hover:bg-red-50"
          >
            Remove GCP key
          </button>
        )}
      </div>

      <div className="bg-blue-50 rounded-lg shadow p-4">
        <span className="list-decimal list-inside space-y-2 text-blue-900">
          Change GCP Configuration for on-prem installs only.
        </span>
      </div>

      {editOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-4">
              <h2 className="text-xl font-semibold">GCP service account JSON</h2>
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
            <label className="cursor-pointer inline-block mb-2 text-sm text-blue-600 hover:underline">
              Choose JSON file
              <input
                type="file"
                accept=".json,application/json"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  setFileName(file.name);
                  const reader = new FileReader();
                  reader.onload = (ev) => {
                    const text = ev.target?.result as string;
                    setJsonText(text);
                    setError(null);
                  };
                  reader.readAsText(file);
                }}
              />
            </label>
            {fileName && <span className="text-sm text-gray-600 ml-2">{fileName}</span>}
            <textarea
              className="w-full h-48 mt-2 p-2 text-xs font-mono border border-gray-300 rounded"
              placeholder="Paste service account JSON…"
              value={jsonText}
              onChange={(e) => {
                setJsonText(e.target.value);
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
                disabled={!jsonText.trim()}
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

export default GCPConfigManager;
