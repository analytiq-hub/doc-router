import React, { useState, useEffect, useMemo } from 'react';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import Switch from '@mui/material/Switch';
import Button from '@mui/material/Button';
import { DocRouterAccountApi } from '@/utils/api';
import { LLMProvider } from '@docrouter/sdk';
import { LLMChatModel, LLMEmbeddingModel } from '@docrouter/sdk';
import LLMTestModal from './LLMTestModal';
import LLMEmbeddingTestModal from './LLMEmbeddingTestModal';

interface LLMProviderConfigProps {
  providerName: string;
}

const LLMProviderConfig: React.FC<LLMProviderConfigProps> = ({ providerName }) => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [provider, setProvider] = useState<LLMProvider | null>(null);
  const [chatModels, setChatModels] = useState<LLMChatModel[]>([]);
  const [embeddingModels, setEmbeddingModels] = useState<LLMEmbeddingModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Vertex AI service account credentials state
  const [credentialJson, setCredentialJson] = useState('');
  const [credentialFileName, setCredentialFileName] = useState('');
  const [credentialSaving, setCredentialSaving] = useState(false);
  const [credentialError, setCredentialError] = useState<string | null>(null);
  const [credentialSuccess, setCredentialSuccess] = useState(false);

  // Test modal state
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [embeddingTestModalOpen, setEmbeddingTestModalOpen] = useState(false);
  const [selectedEmbeddingModel, setSelectedEmbeddingModel] = useState<string>('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // Fetch provider data
        const providerResponse = await docRouterAccountApi.listLLMProviders();
        const foundProvider = providerResponse.providers.find(p => p.name === providerName);
        if (foundProvider) {
          setProvider(foundProvider);
          // Fetch model data for this provider
          const modelsResponse = await docRouterAccountApi.listLLMModels({
            providerName: providerName,
            providerEnabled: false,
            llmEnabled: false
          });
          setChatModels(modelsResponse.chat_models);
          setEmbeddingModels(modelsResponse.embedding_models);
        } else {
          setError('Provider not found');
        }
      } catch (error) {
        console.error('Error fetching data:', error);
        setError('An error occurred while fetching data.');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [providerName, docRouterAccountApi]);

  const chatAgentModels = provider?.litellm_models_chat_agent ?? provider?.litellm_models_enabled ?? [];

  const handleToggleModel = async (model: string, enabled: boolean) => {
    if (!provider) return;

    try {
      const updatedModels = enabled
        ? [...provider.litellm_models_enabled, model]
        : provider.litellm_models_enabled.filter(m => m !== model);

      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        enabled: provider.enabled,
        token: null,
        litellm_models_enabled: updatedModels,
        litellm_models_chat_agent: chatAgentModels.filter(m => updatedModels.includes(m))
      });

      // Refresh provider data
      const response = await docRouterAccountApi.listLLMProviders();
      const updatedProvider = response.providers.find(p => p.name === providerName);
      if (updatedProvider) {
        setProvider(updatedProvider);
      }
    } catch (error) {
      console.error('Error toggling model:', error);
      setError('An error occurred while updating the model.');
    }
  };

  const handleToggleChatAgent = async (model: string, enabled: boolean) => {
    if (!provider) return;

    try {
      const updatedChatAgent = enabled
        ? [...chatAgentModels, model]
        : chatAgentModels.filter(m => m !== model);
      if (updatedChatAgent.some(m => !provider.litellm_models_enabled.includes(m))) {
        setError('Chat agent models must be a subset of enabled models.');
        return;
      }

      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        enabled: provider.enabled,
        token: null,
        litellm_models_enabled: provider.litellm_models_enabled,
        litellm_models_chat_agent: updatedChatAgent
      });

      const response = await docRouterAccountApi.listLLMProviders();
      const updatedProvider = response.providers.find(p => p.name === providerName);
      if (updatedProvider) {
        setProvider(updatedProvider);
      }
    } catch (err) {
      console.error('Error toggling chat agent model:', err);
      setError('An error occurred while updating the chat agent model.');
    }
  };

  const handleTestModel = (modelName: string) => {
    setSelectedModel(modelName);
    setTestModalOpen(true);
  };

  const handleCloseTestModal = () => {
    setTestModalOpen(false);
    setSelectedModel('');
  };

  const handleTestEmbeddingModel = (modelName: string) => {
    setSelectedEmbeddingModel(modelName);
    setEmbeddingTestModalOpen(true);
  };

  const handleCloseEmbeddingTestModal = () => {
    setEmbeddingTestModalOpen(false);
    setSelectedEmbeddingModel('');
  };

  const handleCredentialFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setCredentialFileName(file.name);
    const reader = new FileReader();
    reader.onload = (evt) => {
      const text = evt.target?.result as string;
      try {
        JSON.parse(text); // validate it's JSON
        setCredentialJson(text);
        setCredentialError(null);
      } catch {
        setCredentialError('Invalid JSON file. Please upload a valid service account key file.');
        setCredentialJson('');
      }
    };
    reader.readAsText(file);
  };

  const handleClearCredential = async () => {
    if (!provider) return;
    try {
      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        enabled: provider.enabled,
        token: "",
        litellm_models_enabled: provider.litellm_models_enabled,
        litellm_models_chat_agent: provider.litellm_models_chat_agent ?? provider.litellm_models_enabled,
      });
      const response = await docRouterAccountApi.listLLMProviders();
      const updated = response.providers.find(p => p.name === providerName);
      if (updated) setProvider(updated);
    } catch (err) {
      console.error('Error clearing credentials:', err);
      setCredentialError('Failed to clear credentials. Please try again.');
    }
  };

  const handleSaveCredential = async () => {
    if (!provider || !credentialJson) return;
    setCredentialError(null);
    setCredentialSuccess(false);
    try {
      JSON.parse(credentialJson);
    } catch {
      setCredentialError('Invalid JSON. Please provide a valid service account key.');
      return;
    }
    setCredentialSaving(true);
    try {
      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        enabled: true,
        token: credentialJson,
        litellm_models_enabled: provider.litellm_models_enabled,
        litellm_models_chat_agent: provider.litellm_models_chat_agent ?? provider.litellm_models_enabled,
      });
      const response = await docRouterAccountApi.listLLMProviders();
      const updated = response.providers.find(p => p.name === providerName);
      if (updated) setProvider(updated);
      setCredentialJson('');
      setCredentialFileName('');
      setCredentialSuccess(true);
    } catch (err) {
      console.error('Error saving credentials:', err);
      setCredentialError('Failed to save credentials. Please try again.');
    } finally {
      setCredentialSaving(false);
    }
  };

  // Chat models columns (with test button and chat agent toggle)
  const chatModelColumns: GridColDef[] = [
    { field: 'litellm_model', headerName: 'Model Name', flex: 1, minWidth: 150 },
    {
      field: 'enabled',
      headerName: 'Enabled',
      width: 100,
      minWidth: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Switch
          checked={provider?.litellm_models_enabled.includes(params.row.litellm_model)}
          onChange={(e) => handleToggleModel(params.row.litellm_model, e.target.checked)}
          size="small"
          color="primary"
        />
      ),
    },
    {
      field: 'chat_agent',
      headerName: 'Chat Agent',
      width: 120,
      minWidth: 120,
      renderCell: (params: GridRenderCellParams) => (
        <Switch
          checked={chatAgentModels.includes(params.row.litellm_model)}
          onChange={(e) => handleToggleChatAgent(params.row.litellm_model, e.target.checked)}
          size="small"
          color="secondary"
          disabled={!provider?.litellm_models_enabled.includes(params.row.litellm_model)}
        />
      ),
    },
    {
      field: 'test',
      headerName: 'Test',
      width: 100,
      minWidth: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Button
          variant="outlined"
          size="small"
          onClick={() => handleTestModel(params.row.litellm_model)}
          disabled={!provider?.litellm_models_enabled.includes(params.row.litellm_model)}
        >
          Test
        </Button>
      ),
    },
    { field: 'max_input_tokens', headerName: 'Max Input Tokens', width: 140, minWidth: 140 },
    { field: 'max_output_tokens', headerName: 'Max Output Tokens', width: 140, minWidth: 140 },
    { field: 'input_cost_per_token', headerName: 'Input Cost', width: 100, minWidth: 100 },
    { field: 'output_cost_per_token', headerName: 'Output Cost', width: 100, minWidth: 100 },
  ];

  // Embedding models columns (with test button)
  const embeddingModelColumns: GridColDef[] = [
    { field: 'litellm_model', headerName: 'Model Name', flex: 1, minWidth: 150 },
    {
      field: 'enabled',
      headerName: 'Enabled',
      width: 100,
      minWidth: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Switch
          checked={provider?.litellm_models_enabled.includes(params.row.litellm_model)}
          onChange={(e) => handleToggleModel(params.row.litellm_model, e.target.checked)}
          size="small"
          color="primary"
        />
      ),
    },
    {
      field: 'test',
      headerName: 'Test',
      width: 100,
      minWidth: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Button
          variant="outlined"
          size="small"
          onClick={() => handleTestEmbeddingModel(params.row.litellm_model)}
          disabled={!provider?.litellm_models_enabled.includes(params.row.litellm_model)}
        >
          Test
        </Button>
      ),
    },
    { field: 'max_input_tokens', headerName: 'Max Input Tokens', width: 140, minWidth: 140 },
    { field: 'dimensions', headerName: 'Dimensions', width: 120, minWidth: 120 },
    { field: 'input_cost_per_token', headerName: 'Input Cost', width: 100, minWidth: 100 },
    { field: 'input_cost_per_token_batches', headerName: 'Input Cost (Batches)', width: 150, minWidth: 150 },
  ];

  if (loading) return <div>Loading...</div>;
  if (error) return <div className="text-red-500">{error}</div>;
  if (!provider) return <div>Provider not found</div>;

  // Prepare chat models for display (already have all needed fields)
  const chatModelRows = chatModels;

  // Prepare embedding models for display (already have all needed fields)
  const embeddingModelRows = embeddingModels;

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-2xl font-bold mb-4">Provider: {provider.display_name}{!provider.enabled && <span className="text-gray-500 italic"> (disabled)</span>}</h2>      
      <div className="mb-4">
        <p><b>Enabled:</b> {provider.enabled ? 'Yes' : 'No'}</p>
        {providerName !== 'vertex_ai' && (
          <p><b>Token:</b> {provider.token ? `${provider.token.slice(0, 16)}••••••••` : 'Not set'}</p>
        )}
      </div>

      {/* Vertex AI service account credentials */}
      {providerName === 'vertex_ai' && (
        <div className="mb-6 p-4 border border-gray-200 rounded-lg">
          <h3 className="text-lg font-semibold mb-1">Service Account Credentials</h3>
          <p className="text-sm text-gray-600 mb-3">
            Upload a Google Cloud service account JSON key file. The credentials are encrypted and stored securely.
          </p>
          <p className="mb-3">
            <b>Status:</b>{' '}
            {provider.token
              ? <span className="text-green-600">Credentials set{provider.token_created_at ? ` (updated ${new Date(provider.token_created_at).toLocaleDateString()})` : ''}</span>
              : <span className="text-yellow-600">Not configured</span>
            }
          </p>
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <label className="cursor-pointer bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded border border-gray-300 text-sm">
                Choose JSON File
                <input type="file" accept=".json,application/json" className="hidden" onChange={handleCredentialFileUpload} />
              </label>
              {credentialFileName && <span className="text-sm text-gray-600">{credentialFileName}</span>}
            </div>
            <textarea
              className="w-full h-32 p-2 text-xs font-mono border border-gray-300 rounded resize-y"
              placeholder="Or paste service account JSON here..."
              value={credentialJson}
              onChange={(e) => {
                setCredentialJson(e.target.value);
                setCredentialError(null);
                setCredentialSuccess(false);
              }}
            />
            {credentialError && <p className="text-red-500 text-sm">{credentialError}</p>}
            {credentialSuccess && <p className="text-green-600 text-sm">Credentials saved successfully.</p>}
            <div className="flex gap-2">
              <Button
                variant="contained"
                size="small"
                onClick={handleSaveCredential}
                disabled={!credentialJson || credentialSaving}
              >
                {credentialSaving ? 'Saving...' : 'Save Credentials'}
              </Button>
              {provider.token && (
                <Button
                  variant="outlined"
                  size="small"
                  color="error"
                  onClick={handleClearCredential}
                >
                  Clear Credentials
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* Chat Models Section */}
      {chatModelRows.length > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-2">Chat Models</h3>
          <p className="text-sm text-gray-600 mb-2">Use <strong>Chat Agent</strong> to allow a model in the document chat agent (conversation UI). Only enabled models can be selected.</p>
          <div className="w-full overflow-x-auto">
            <DataGrid
              rows={chatModelRows}
              columns={chatModelColumns}
              disableRowSelectionOnClick
              getRowId={(row) => row.litellm_model}
              sx={{
                minWidth: 800,
                height: 300,
              }}
            />
          </div>
        </div>
      )}

      {/* Embedding Models Section */}
      {embeddingModelRows.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-2">Embedding Models</h3>
          <div className="w-full overflow-x-auto">
            <DataGrid
              rows={embeddingModelRows}
              columns={embeddingModelColumns}
              disableRowSelectionOnClick
              getRowId={(row) => row.litellm_model}
              sx={{
                minWidth: 800,
                height: 300,
              }}
            />
          </div>
        </div>
      )}

      {/* Test Modals */}
      <LLMTestModal
        open={testModalOpen}
        onClose={handleCloseTestModal}
        modelName={selectedModel}
      />
      <LLMEmbeddingTestModal
        open={embeddingTestModalOpen}
        onClose={handleCloseEmbeddingTestModal}
        modelName={selectedEmbeddingModel}
      />
    </div>
  );
};

export default LLMProviderConfig;
