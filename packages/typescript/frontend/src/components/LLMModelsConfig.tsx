import React, { useState, useEffect, useMemo } from 'react';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import Switch from '@mui/material/Switch';
import Button from '@mui/material/Button';
import { DocRouterAccountApi } from '@/utils/api';
import { LLMProvider } from '@docrouter/sdk';
import { LLMChatModel, LLMEmbeddingModel } from '@docrouter/sdk';
import colors from 'tailwindcss/colors';
import LLMTestModal from './LLMTestModal';
import LLMEmbeddingTestModal from './LLMEmbeddingTestModal';

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
  const [embeddingTestModalOpen, setEmbeddingTestModalOpen] = useState(false);
  const [selectedEmbeddingModel, setSelectedEmbeddingModel] = useState<string>('');

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

  const handleTestEmbeddingModel = (modelName: string) => {
    setSelectedEmbeddingModel(modelName);
    setEmbeddingTestModalOpen(true);
  };

  const handleCloseEmbeddingTestModal = () => {
    setEmbeddingTestModalOpen(false);
    setSelectedEmbeddingModel('');
  };

  // Chat models columns (with test button)
  const chatModelColumns: GridColDef[] = [
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
    { field: 'max_output_tokens', headerName: 'Max Output Tokens', width: 140, minWidth: 140 },
    { field: 'input_cost_per_token', headerName: 'Input Cost', width: 100, minWidth: 100 },
    { field: 'output_cost_per_token', headerName: 'Output Cost', width: 100, minWidth: 100 },
  ];

  // Embedding models columns (with test button)
  const embeddingModelColumns: GridColDef[] = [
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
          onClick={() => handleTestEmbeddingModel(params.row.name)}
          disabled={!params.row.enabled}
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

  // Build chat model rows
  const chatModelRows = providers.flatMap(provider =>
    provider.litellm_models_available
      .filter(modelName => {
        const chatModelInfo = chatModels.find(m => 
          m.litellm_model === modelName && 
          m.litellm_provider === provider.litellm_provider
        );
        return chatModelInfo !== undefined;
      })
      .map(modelName => {
        const chatModelInfo = chatModels.find(m => 
          m.litellm_model === modelName && 
          m.litellm_provider === provider.litellm_provider
        );
        
        return {
          id: `${provider.name}-${modelName}`,
          provider: provider.name,
          name: modelName,
          enabled: provider.litellm_models_enabled.includes(modelName),
          max_input_tokens: chatModelInfo?.max_input_tokens ?? 0,
          max_output_tokens: chatModelInfo?.max_output_tokens ?? 0,
          input_cost_per_token: chatModelInfo?.input_cost_per_token ?? 0,
          output_cost_per_token: chatModelInfo?.output_cost_per_token ?? 0,
        };
      })
  );

  // Build embedding model rows
  const embeddingModelRows = providers.flatMap(provider =>
    provider.litellm_models_available
      .filter(modelName => {
        const embeddingModelInfo = embeddingModels.find(m => 
          m.litellm_model === modelName && 
          m.litellm_provider === provider.litellm_provider
        );
        return embeddingModelInfo !== undefined;
      })
      .map(modelName => {
        const embeddingModelInfo = embeddingModels.find(m => 
          m.litellm_model === modelName && 
          m.litellm_provider === provider.litellm_provider
        );
        
        // Type-safe access to embedding model properties
        const inputCostPerToken = embeddingModelInfo?.input_cost_per_token ?? 0;
        const inputCostPerTokenBatches = embeddingModelInfo 
          ? ('input_cost_per_token_batches' in embeddingModelInfo 
              ? embeddingModelInfo.input_cost_per_token_batches 
              : 0)
          : 0;
        
        return {
          id: `${provider.name}-${modelName}`,
          provider: provider.name,
          name: modelName,
          enabled: provider.litellm_models_enabled.includes(modelName),
          max_input_tokens: embeddingModelInfo?.max_input_tokens ?? 0,
          dimensions: embeddingModelInfo?.dimensions ?? 0,
          input_cost_per_token: inputCostPerToken,
          input_cost_per_token_batches: inputCostPerTokenBatches,
        };
      })
  );

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-2xl font-bold mb-6">LLM Models Configuration</h2>
      
      {/* Chat Models Section */}
      <div className="mb-8">
        <h3 className="text-xl font-semibold mb-4">Chat Models</h3>
        <div className="w-full overflow-x-auto">
          <DataGrid
            rows={chatModelRows}
            columns={chatModelColumns}
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
      </div>

      {/* Embedding Models Section */}
      <div>
        <h3 className="text-xl font-semibold mb-4">Embedding Models</h3>
        <div className="w-full overflow-x-auto">
          <DataGrid
            rows={embeddingModelRows}
            columns={embeddingModelColumns}
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
      </div>

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

export default LLMModelsConfig;
