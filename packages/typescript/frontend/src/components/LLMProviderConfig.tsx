'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { DataTable, type DataTableColumn } from '@/components/data-table';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { DocRouterAccountApi } from '@/utils/api';
import { LLMProvider } from '@docrouter/sdk';
import { LLMChatModel, LLMEmbeddingModel } from '@docrouter/sdk';
import LLMTestModal from './LLMTestModal';
import LLMEmbeddingTestModal from './LLMEmbeddingTestModal';
import { useLlmMaxConcurrentSettings } from './useLlmMaxConcurrentSettings';

interface LLMProviderConfigProps {
  providerName: string;
}

const LLMProviderConfig: React.FC<LLMProviderConfigProps> = ({ providerName }) => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const { loadMaxConcurrentSettings, createMaxConcurrentColumn } =
    useLlmMaxConcurrentSettings(docRouterAccountApi);
  const [provider, setProvider] = useState<LLMProvider | null>(null);
  const [chatModels, setChatModels] = useState<LLMChatModel[]>([]);
  const [embeddingModels, setEmbeddingModels] = useState<LLMEmbeddingModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
          const [modelsResponse] = await Promise.all([
            docRouterAccountApi.listLLMModels({
              providerName: providerName,
              providerEnabled: false,
              llmEnabled: false,
            }),
            loadMaxConcurrentSettings(),
          ]);
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
  }, [providerName, docRouterAccountApi, loadMaxConcurrentSettings]);

  const chatAgentModels = provider?.litellm_models_chat_agent ?? provider?.litellm_models_enabled ?? [];

  const maxConcurrentColumn = createMaxConcurrentColumn<LLMChatModel>({
    getModelName: (row) => String(row.litellm_model),
    isEnabled: (row) =>
      provider?.litellm_models_enabled.includes(String(row.litellm_model)) ?? false,
  });

  const maxConcurrentEmbeddingColumn = createMaxConcurrentColumn<LLMEmbeddingModel>({
    getModelName: (row) => String(row.litellm_model),
    isEnabled: (row) =>
      provider?.litellm_models_enabled.includes(String(row.litellm_model)) ?? false,
  });

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

  // Chat models columns (with test button and chat agent toggle)
  const chatModelColumns: DataTableColumn<LLMChatModel>[] = [
    { field: 'litellm_model', headerName: 'Model Name', flex: 1, minWidth: 150 },
    {
      field: 'enabled',
      headerName: 'Enabled',
      width: 100,
      minWidth: 100,
      sortable: false,
      renderCell: ({ row }) => (
        <Switch
          checked={provider?.litellm_models_enabled.includes(row.litellm_model)}
          onCheckedChange={(checked) => void handleToggleModel(row.litellm_model, checked === true)}
        />
      ),
    },
    {
      field: 'chat_agent',
      headerName: 'Chat Agent',
      width: 120,
      minWidth: 120,
      sortable: false,
      renderCell: ({ row }) => (
        <Switch
          checked={chatAgentModels.includes(row.litellm_model)}
          onCheckedChange={(checked) => void handleToggleChatAgent(row.litellm_model, checked === true)}
          disabled={!provider?.litellm_models_enabled.includes(row.litellm_model)}
        />
      ),
    },
    {
      field: 'test',
      headerName: 'Test',
      width: 100,
      minWidth: 100,
      sortable: false,
      renderCell: ({ row }) => (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => handleTestModel(row.litellm_model)}
          disabled={!provider?.litellm_models_enabled.includes(row.litellm_model)}
        >
          Test
        </Button>
      ),
    },
    maxConcurrentColumn,
    { field: 'max_input_tokens', headerName: 'Max Input Tokens', width: 140, minWidth: 140 },
    { field: 'max_output_tokens', headerName: 'Max Output Tokens', width: 140, minWidth: 140 },
    { field: 'input_cost_per_token', headerName: 'Input Cost', width: 100, minWidth: 100 },
    { field: 'output_cost_per_token', headerName: 'Output Cost', width: 100, minWidth: 100 },
  ];

  // Embedding models columns (with test button)
  const embeddingModelColumns: DataTableColumn<LLMEmbeddingModel>[] = [
    { field: 'litellm_model', headerName: 'Model Name', flex: 1, minWidth: 150 },
    {
      field: 'enabled',
      headerName: 'Enabled',
      width: 100,
      minWidth: 100,
      sortable: false,
      renderCell: ({ row }) => (
        <Switch
          checked={provider?.litellm_models_enabled.includes(row.litellm_model)}
          onCheckedChange={(checked) => void handleToggleModel(row.litellm_model, checked === true)}
        />
      ),
    },
    {
      field: 'test',
      headerName: 'Test',
      width: 100,
      minWidth: 100,
      sortable: false,
      renderCell: ({ row }) => (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => handleTestEmbeddingModel(row.litellm_model)}
          disabled={!provider?.litellm_models_enabled.includes(row.litellm_model)}
        >
          Test
        </Button>
      ),
    },
    maxConcurrentEmbeddingColumn,
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
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Provider: {provider.display_name}{!provider.enabled && <span className="text-gray-500 italic"> (disabled)</span>}</h2>      
      <div className="mb-4">
        <p><b>Enabled:</b> {provider.enabled ? 'Yes' : 'No'}</p>
        {providerName !== 'vertex_ai' && providerName !== 'bedrock' && (
          <p><b>Token:</b> {provider.token ? `${provider.token.slice(0, 16)}••••••••` : 'Not set'}</p>
        )}
      </div>

      {providerName === 'bedrock' && (
        <div className="mb-6 p-4 border border-gray-200 rounded-lg bg-gray-50">
          <p className="text-sm text-gray-600 mb-2">
            AWS Bedrock uses the same IAM credentials as the rest of this deployment (S3, Textract). Configure them under{' '}
            <Link to="/settings/account/development/aws-config" className="text-primary-600 underline font-medium">
              Account → Development → AWS setup
            </Link>
            . There is no separate Bedrock API key here.
          </p>
        </div>
      )}
      
      {providerName === 'vertex_ai' && (
        <div className="mb-6 p-4 border border-gray-200 rounded-lg bg-gray-50">
          <p className="text-sm text-gray-600 mb-2">
            Vertex AI uses a GCP service account JSON configured under{' '}
            <Link to="/settings/account/development/gcp-config" className="text-primary-600 underline font-medium">
              Account → Development → GCP setup
            </Link>
            .
          </p>
        </div>
      )}

      {/* Chat Models Section */}
      {chatModelRows.length > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-2">Chat Models</h3>
          <p className="text-sm text-gray-600 mb-2">
            Use <strong>Chat Agent</strong> to allow a model in the document chat agent (conversation UI). Only enabled models can be selected.
            Max concurrent limits are per worker process; leave empty or 0 for unlimited.
          </p>
          <div className="w-full overflow-x-auto">
            <DataTable
              rows={chatModelRows}
              columns={chatModelColumns}
              getRowId={(row) => row.litellm_model}
            />
          </div>
        </div>
      )}

      {/* Embedding Models Section */}
      {embeddingModelRows.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-2">Embedding Models</h3>
          <div className="w-full overflow-x-auto">
            <DataTable
              rows={embeddingModelRows}
              columns={embeddingModelColumns}
              getRowId={(row) => row.litellm_model}
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
