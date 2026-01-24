import React, { useState, useEffect, useMemo } from 'react';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import Switch from '@mui/material/Switch';
import Button from '@mui/material/Button';
import { DocRouterAccountApi } from '@/utils/api';
import { LLMProvider } from '@docrouter/sdk';
import { LLMModel } from '@docrouter/sdk';
import LLMTestModal from './LLMTestModal';

interface LLMProviderConfigProps {
  providerName: string;
}

const LLMProviderConfig: React.FC<LLMProviderConfigProps> = ({ providerName }) => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [provider, setProvider] = useState<LLMProvider | null>(null);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Test modal state
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>('');

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
          setModels(modelsResponse.models);
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

  const handleToggleModel = async (model: string, enabled: boolean) => {
    if (!provider) return;

    try {
      const updatedModels = enabled
        ? [...provider.litellm_chat_models_enabled, model]
        : provider.litellm_chat_models_enabled.filter(m => m !== model);

      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        enabled: provider.enabled,
        token: provider.token,
        litellm_chat_models_enabled: updatedModels,
        litellm_embedding_models_enabled: null
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

  const handleTestModel = (modelName: string) => {
    setSelectedModel(modelName);
    setTestModalOpen(true);
  };

  const handleCloseTestModal = () => {
    setTestModalOpen(false);
    setSelectedModel('');
  };

  const columns: GridColDef[] = [
    { field: 'litellm_model', headerName: 'Model Name', flex: 1, minWidth: 150 },
    {
      field: 'enabled',
      headerName: 'Enabled',
      width: 100,
      minWidth: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Switch
          checked={provider?.litellm_chat_models_enabled?.includes(params.row.litellm_model) ?? false}
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
          onClick={() => handleTestModel(params.row.litellm_model)}
          disabled={!provider?.litellm_chat_models_enabled?.includes(params.row.litellm_model)}
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

  if (loading) return <div>Loading...</div>;
  if (error) return <div className="text-red-500">{error}</div>;
  if (!provider) return <div>Provider not found</div>;

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-2xl font-bold mb-4">Provider: {provider.display_name}{!provider.enabled && <span className="text-gray-500 italic"> (disabled)</span>}</h2>      
      <div className="mb-4">
      <p><b>Enabled:</b> {provider.enabled ? 'Yes' : 'No'}</p>
      <p><b>Token:</b> {provider.token ? `${provider.token.slice(0, 16)}••••••••` : 'Not set'}</p>
      </div>
      <h3 className="text-lg font-semibold mb-2">Models</h3>
      <div className="w-full overflow-x-auto">
        <DataGrid
          rows={models}
          columns={columns}
          disableRowSelectionOnClick
          getRowId={(row) => row.litellm_model}
          sx={{
            minWidth: 800,
            height: 300,
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

export default LLMProviderConfig;
