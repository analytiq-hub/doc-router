import React, { useState, useEffect, useMemo } from 'react';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import Switch from '@mui/material/Switch';
import Button from '@mui/material/Button';
import { DocRouterAccountApi } from '@/utils/api';
import { LLMProvider } from '@docrouter/sdk';
import { LLMChatModel, LLMEmbeddingModel } from '@docrouter/sdk';
import colors from 'tailwindcss/colors';
import LLMTestModal from './LLMTestModal';

const LLMModelsConfig: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [chatModels, setChatModels] = useState<LLMChatModel[]>([]);
  const [embeddingModels, setEmbeddingModels] = useState<LLMEmbeddingModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Test modal state
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [providersResponse, modelsResponse] = await Promise.all([
          docRouterAccountApi.listLLMProviders(),
          docRouterAccountApi.listLLMModels({})
        ]);
        setProviders(providersResponse.providers);
        setChatModels(modelsResponse.chat_models);
        setEmbeddingModels(modelsResponse.embedding_models);
      } catch (error) {
        console.error('Error fetching data:', error);
        setError('An error occurred while fetching data.');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [docRouterAccountApi]);

  const handleToggleModel = async (providerName: string, model: string, enabled: boolean) => {
    const provider = providers.find(p => p.name === providerName);
    if (!provider) return;

    try {
      const updatedModels = enabled
        ? [...provider.litellm_models_enabled, model]
        : provider.litellm_models_enabled.filter(m => m !== model);

      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        enabled: provider.enabled,
        token: provider.token,
        litellm_models_enabled: updatedModels
      });

      // Refresh providers data
      const response = await docRouterAccountApi.listLLMProviders();
      setProviders(response.providers);
    } catch (error) {
      console.error('Error toggling model:', error);
      setError('An error occurred while updating the model.');
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

  const columns: GridColDef[] = [
    { field: 'provider', headerName: 'Provider', flex: 1, minWidth: 120 },
    { field: 'name', headerName: 'Model Name', flex: 1, minWidth: 150 },
    {
      field: 'enabled',
      headerName: 'Enabled',
      width: 100,
      minWidth: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Switch
          checked={params.row.enabled}
          onChange={(e) => handleToggleModel(params.row.provider, params.row.name, e.target.checked)}
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
          onClick={() => handleTestModel(params.row.name)}
          disabled={!params.row.enabled}
        >
          Test
        </Button>
      ),
    },
    { field: 'max_input_tokens', headerName: 'Max Input Tokens', width: 140, minWidth: 140 },
    { field: 'max_output_tokens', headerName: 'Max Output Tokens / Dimensions', width: 180, minWidth: 180 },
    { field: 'input_cost_per_token', headerName: 'Input Cost', width: 100, minWidth: 100 },
    { field: 'output_cost_per_token', headerName: 'Output Cost', width: 100, minWidth: 100 },
  ];

  if (loading) return <div>Loading...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  const rows = providers.flatMap(provider =>
    provider.litellm_models_available.map(modelName => {
      // Find the model info by matching both provider and model name
      // Check chat models first, then embedding models
      const chatModelInfo = chatModels.find(m => 
        m.litellm_model === modelName && 
        m.litellm_provider === provider.litellm_provider
      );
      const embeddingModelInfo = embeddingModels.find(m => 
        m.litellm_model === modelName && 
        m.litellm_provider === provider.litellm_provider
      );
      
      const modelInfo = chatModelInfo || embeddingModelInfo;
      
      if (!modelInfo) {
        console.warn(`No model info found for ${provider.litellm_provider}/${modelName}`);
      }
      
      return {
        id: `${provider.name}-${modelName}`,
        provider: provider.name,
        name: modelName,
        enabled: provider.litellm_models_enabled.includes(modelName),
        max_input_tokens: modelInfo?.max_input_tokens ?? 0,
        max_output_tokens: chatModelInfo ? (chatModelInfo.max_output_tokens ?? 0) : (embeddingModelInfo ? 'N/A' : 0),
        dimensions: embeddingModelInfo ? (embeddingModelInfo.dimensions ?? 0) : undefined,
        input_cost_per_token: chatModelInfo ? (chatModelInfo.input_cost_per_token ?? 0) : (embeddingModelInfo ? 'N/A' : 0),
        output_cost_per_token: modelInfo?.output_cost_per_token ?? 0,
        output_cost_per_token_batches: embeddingModelInfo ? (embeddingModelInfo.output_cost_per_token_batches ?? 0) : undefined,
      };
    })
  );

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-2xl font-bold mb-4">All Language Models</h2>
      <div className="w-full overflow-x-auto">
        <DataGrid
          rows={rows}
          columns={columns}
          disableRowSelectionOnClick
          sx={{
            minWidth: 800,
            height: 400,
            '& .MuiDataGrid-cell': {
              padding: '8px',
              display: 'flex',
              alignItems: 'center',
              height: '100%',
            },
            '& .MuiDataGrid-row': {
              height: '48px !important',
            },
            '& .MuiDataGrid-row:nth-of-type(odd)': {
              backgroundColor: colors.gray[100],
            },
            '& .MuiDataGrid-row:hover': {
              backgroundColor: `${colors.gray[200]} !important`,
            },
          }}
        />
      </div>

      {/* Test Modal */}
      <LLMTestModal
        open={testModalOpen}
        onClose={handleCloseTestModal}
        modelName={selectedModel}
      />
    </div>
  );
};

export default LLMModelsConfig;
