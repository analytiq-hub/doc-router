import React, { useState, useEffect, useMemo } from 'react';
import { Delete as DeleteIcon, Edit as EditIcon, MoreVert as MoreVertIcon, Settings as SettingsIcon, Close as CloseIcon } from '@mui/icons-material';
import { DocRouterAccountApi } from '@/utils/api';
import { LLMProvider } from '@docrouter/sdk';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import colors from 'tailwindcss/colors';
import Checkbox from '@mui/material/Checkbox';
import Switch from '@mui/material/Switch';
import Link from 'next/link';

const LLMManager: React.FC = () => {
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [llmProviders, setLLMProviders] = useState<LLMProvider[]>([]);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [editTokenValue, setEditTokenValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [modelSelectionOpen, setModelSelectionOpen] = useState(false);

  useEffect(() => {
    const getLLMProvidersData = async () => {
      try {
        setLoading(true);
        const response = await docRouterAccountApi.listLLMProviders();
        setLLMProviders(response.providers);
      } catch (error) {
        console.error('Error fetching LLM providers:', error);
      } finally {
        setLoading(false);
      }
    };

    getLLMProvidersData();
  }, [docRouterAccountApi]);

  const handleEditLLMToken = (provider: string) => {
    setEditingProvider(provider);
    setEditTokenValue('');
    setEditModalOpen(true);
  };

  const handleSaveLLMToken = async () => {
    if (!editingProvider) return;

    try {
      await docRouterAccountApi.setLLMProviderConfig(editingProvider, {
        token: editTokenValue,
        enabled: true,
        litellm_chat_models_enabled: null,
        litellm_embedding_models_enabled: null
      });
      setEditModalOpen(false);
      // Refresh the LLM providers list
      const response = await docRouterAccountApi.listLLMProviders();
      setLLMProviders(response.providers);
    } catch (error) {
      console.error('Error saving LLM token:', error);
      setError('An error occurred while saving the LLM token. Please try again.');
    }
  };

  const handleDeleteLLMToken = async (providerName: string) => {
    try {
      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        token: null,
        enabled: false,
        litellm_chat_models_enabled: null,
        litellm_embedding_models_enabled: null
      });
      // Refresh the LLM providers list
      const response = await docRouterAccountApi.listLLMProviders();
      setLLMProviders(response.providers);
    } catch (error) {
      console.error('Error deleting LLM token:', error);
      setError('An error occurred while deleting the LLM token. Please try again.');
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, provider: string) => {
    setAnchorEl(event.currentTarget);
    setSelectedProvider(provider);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleCloseModelSelection = () => {
    setModelSelectionOpen(false);
    setSelectedProvider(null);
  };

  const handleToggleProvider = async (providerName: string, enabled: boolean) => {
    try {
      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        enabled,
        token: null,
        litellm_chat_models_enabled: null,
        litellm_embedding_models_enabled: null
      });
      // Refresh the LLM providers list
      const response = await docRouterAccountApi.listLLMProviders();
      setLLMProviders(response.providers);
    } catch (error) {
      console.error('Error toggling provider:', error);
      setError('An error occurred while updating the provider. Please try again.');
    }
  };

  const handleToggleModel = async (providerName: string, model: string, enabled: boolean) => {
    try {
      const provider = llmProviders.find(p => p.name === providerName);
      if (!provider) return;

      const updatedModels = enabled
        ? [...(provider.litellm_chat_models_enabled || []), model]
        : (provider.litellm_chat_models_enabled || []).filter(m => m !== model);

      await docRouterAccountApi.setLLMProviderConfig(providerName, {
        enabled: provider.enabled,
        token: provider.token,
        litellm_chat_models_enabled: updatedModels,
        litellm_embedding_models_enabled: null
      });
      // Refresh the LLM providers list
      const response = await docRouterAccountApi.listLLMProviders();
      setLLMProviders(response.providers);
    } catch (error) {
      console.error('Error toggling model:', error);
      setError('An error occurred while updating the models. Please try again.');
    }
  };

  // Filter providers based on search
  const filteredProviders = llmProviders.filter(provider => 
    searchQuery === '' || 
    provider.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Provider',
      flex: .5,
      minWidth: 150,
      renderCell: (params: GridRenderCellParams) => (
        <Link
          href={`/settings/account/development/llm-manager/providers/${params.row.name}`}
          className="text-blue-600 hover:text-blue-800"
        >
          {params.row.display_name}
        </Link>
      ),
    },
    {
      field: 'enabled',
      headerName: 'Enabled',
      width: 120,
      renderCell: (params: GridRenderCellParams) => (
        <div className="flex items-center gap-2">
          <Switch
            checked={params.value}
            onChange={(e) => handleToggleProvider(params.row.name, e.target.checked)}
            size="small"
            color="primary"
          />
        </div>
      ),
    },
    {
      field: 'litellm_chat_models_enabled',
      headerName: 'Enabled Chat Models',
      flex: 1,
      minWidth: 200,
      renderCell: (params: GridRenderCellParams) => {
        const chatCount = params.row.litellm_chat_models_enabled?.length || 0;
        const embeddingCount = params.row.litellm_embedding_models_enabled?.length || 0;
        return (
          <span className="text-sm text-gray-600">
            {chatCount} chat, {embeddingCount} embedding {chatCount + embeddingCount === 1 ? 'model' : 'models'} enabled
          </span>
        );
      },
    },
    {
      field: 'token',
      headerName: 'Token',
      flex: 1,
      minWidth: 200,
      renderCell: (params: GridRenderCellParams) => (
        <span>{params.value ? `${params.value.slice(0, 16)}••••••••` : 'Not set'}</span>
      ),
    },
    {
      field: 'token_created_at',
      headerName: 'Created At',
      flex: 1,
      minWidth: 150,
      renderCell: (params: GridRenderCellParams) => (
        <span>{params.value ? new Date(params.value).toLocaleString() : '-'}</span>
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 80,
      renderCell: (params) => (
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => handleMenuOpen(e, params.row.name)}
            className="p-1 text-gray-600 hover:text-gray-900 rounded-full hover:bg-gray-100"
          >
            <MoreVertIcon className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="bg-white p-6 rounded-lg shadow h-[calc(100vh-184px)] flex flex-col">
      <div className="mb-4">
        <input
          type="text"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          placeholder="Search providers..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <div className="flex-1 overflow-hidden">
        <DataGrid
          rows={filteredProviders}
          columns={columns}
          loading={loading}
          disableRowSelectionOnClick
          getRowId={(row) => row.name}
          sx={{
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

      {/* Edit Token Modal */}
      {editModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Edit {editingProvider} Token</h2>
              <button
                onClick={() => setEditModalOpen(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="mt-4">
              <label htmlFor="token" className="block text-sm font-medium text-gray-700 mb-1">
                Token
              </label>
              <input
                id="token"
                type="text"
                value={editTokenValue}
                onChange={(e) => setEditTokenValue(e.target.value)}
                placeholder="Enter your token"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
              />
            </div>

            <div className="flex justify-end space-x-2 mt-6">
              <button
                onClick={() => setEditModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveLLMToken}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem
          component={Link}
          href={`/settings/account/development/llm-manager/providers/${selectedProvider}`}
          onClick={handleMenuClose}
          className="flex items-center gap-2"
        >
          <SettingsIcon fontSize="small" className="text-blue-600" />
          <span>Configure Models</span>
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (selectedProvider) handleEditLLMToken(selectedProvider);
            handleMenuClose();
          }}
          className="flex items-center gap-2"
        >
          <EditIcon fontSize="small" className="text-blue-600" />
          <span>Edit Token</span>
        </MenuItem>
        {selectedProvider && llmProviders.find(p => p.name === selectedProvider) && (
          <MenuItem
            onClick={() => {
              const provider = llmProviders.find(p => p.name === selectedProvider);
              if (provider) handleDeleteLLMToken(provider.name);
              handleMenuClose();
            }}
            className="flex items-center gap-2"
          >
            <DeleteIcon fontSize="small" className="text-red-600" />
            <span>Delete Token</span>
          </MenuItem>
        )}
      </Menu>

      {/* Add Model Selection Dialog */}
      {modelSelectionOpen && selectedProvider && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Configure Models for {selectedProvider}</h2>
              <button onClick={handleCloseModelSelection} className="text-gray-500 hover:text-gray-700">
                <CloseIcon />
              </button>
            </div>
            <div className="max-h-96 overflow-y-auto">
              <div className="mb-4">
                <h3 className="font-semibold mb-2">Chat Models</h3>
                {llmProviders.find(p => p.name === selectedProvider)?.litellm_chat_models_available.map(model => (
                  <div key={model} className="flex items-center gap-2 py-2 border-b">
                    <Checkbox
                      checked={llmProviders.find(p => p.name === selectedProvider)?.litellm_chat_models_enabled?.includes(model) ?? false}
                      onChange={(e) => handleToggleModel(selectedProvider, model, e.target.checked)}
                    />
                    <span>{model}</span>
                  </div>
                ))}
              </div>
              <div>
                <h3 className="font-semibold mb-2">Embedding Models</h3>
                {llmProviders.find(p => p.name === selectedProvider)?.litellm_embedding_models_available.map(model => (
                  <div key={model} className="flex items-center gap-2 py-2 border-b">
                    <Checkbox
                      checked={llmProviders.find(p => p.name === selectedProvider)?.litellm_embedding_models_enabled?.includes(model) ?? false}
                      onChange={(e) => {
                        // TODO: Implement embedding model toggle when we add embedding model management
                        console.log('Embedding model toggle not yet implemented:', model, e.target.checked);
                      }}
                    />
                    <span>{model}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex justify-end mt-4">
              <button
                onClick={handleCloseModelSelection}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error Toast */}
      {error && (
        <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 bg-white border-l-4 border-red-500 shadow-lg rounded-lg p-4 animate-slide-up">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="ml-3 w-full">
              <p className="text-sm text-gray-800">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="ml-auto flex-shrink-0 text-gray-400 hover:text-gray-500"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default LLMManager;
