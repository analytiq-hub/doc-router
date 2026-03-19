import React, { useEffect, useState, useMemo } from 'react';
import { 
  ChevronDownIcon, 
  MagnifyingGlassIcon,
  PencilIcon,
  CheckIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import { Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Menu, MenuItem, Typography } from '@mui/material';
import { styled, alpha } from '@mui/material/styles';
import { DocRouterAccountApi, DocRouterOrgApi } from '@/utils/api';
import type { Organization } from '@docrouter/sdk';
import type { Prompt } from '@docrouter/sdk';
import { useOCRBlocks } from '@/hooks/useOCRBlocks';
import type { GetLLMResultResponse } from '@docrouter/sdk';
import type { HighlightInfo } from '@/hooks/useOCRBlocks';

interface Props {
  organizationId: string;
  id: string;
  onHighlight: (highlight: HighlightInfo) => void;
  onClearHighlight?: () => void;
}

interface EditingState {
  promptId: string;
  key: string;
  value: string;
}

// Update the type definition to handle nested structures
type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

const StyledMenuItem = styled(MenuItem)(({ theme }) => ({
  fontSize: '0.875rem',
  padding: '4px 16px',
  '& .MuiListItemIcon-root': {
    minWidth: '32px',
  },
  '& .MuiSvgIcon-root': {
    color: alpha(theme.palette.text.primary, 0.6),
  },
}));

const PDFExtractionSidebarContent = ({ organizationId, id, onHighlight }: Props) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const { loadOCRBlocks, findBlocksWithContext } = useOCRBlocks();
  const [llmResults, setLlmResults] = useState<Record<string, GetLLMResultResponse>>({});
  const [matchingPrompts, setMatchingPrompts] = useState<Prompt[]>([]);
  const [runningPrompts, setRunningPrompts] = useState<Set<string>>(new Set());
  const [expandedPrompt, setExpandedPrompt] = useState<string>('default');
  const [loadingPrompts, setLoadingPrompts] = useState<Set<string>>(new Set());
  const [failedPrompts, setFailedPrompts] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<EditingState | null>(null);
  const [editMode, setEditMode] = useState<boolean>(false);
  const [documentState, setDocumentState] = useState<string | null>(null);
  const defaultLlmFetchStartedRef = React.useRef(false);

  const [documentName, setDocumentName] = useState<string | null>(null);
  const [organization, setOrganization] = useState<Organization | null>(null);

  // Per-prompt kebab menu + "Run Info" modal
  const [kebabAnchorEl, setKebabAnchorEl] = useState<HTMLElement | null>(null);
  const [kebabPromptId, setKebabPromptId] = useState<string | null>(null);
  const [runInfoOpen, setRunInfoOpen] = useState(false);
  const [runInfoLoading, setRunInfoLoading] = useState(false);
  const [runInfoResult, setRunInfoResult] = useState<GetLLMResultResponse | null>(null);

  // Refs mirror state so the fetch effect can read current values without being in the dependency array
  const llmResultsRef = React.useRef(llmResults);
  const loadingPromptsRef = React.useRef(loadingPrompts);
  const failedPromptsRef = React.useRef(failedPrompts);
  llmResultsRef.current = llmResults;
  loadingPromptsRef.current = loadingPrompts;
  failedPromptsRef.current = failedPrompts;

  const getStatusFromError = (err: unknown): number | undefined => {
    if (!err || typeof err !== 'object') return undefined;
    const maybe = err as { status?: unknown; response?: { status?: unknown } };
    const rawStatus = maybe.status ?? maybe.response?.status;
    if (typeof rawStatus === 'number') return rawStatus;
    if (typeof rawStatus === 'string') {
      const parsed = Number(rawStatus);
      return Number.isFinite(parsed) ? parsed : undefined;
    }
    return undefined;
  };

  const getMessageFromError = (err: unknown): string => {
    if (err instanceof Error) return err.message;
    if (!err || typeof err !== 'object') return '';
    const maybe = err as { message?: unknown };
    return typeof maybe.message === 'string' ? maybe.message : '';
  };

  useEffect(() => {
    defaultLlmFetchStartedRef.current = false;
  }, [id]);

  // Fetch document metadata (state, name) then load prompts and default LLM result.
  useEffect(() => {
    const fetchData = async () => {
      let fetchedState: string | null = null;
      let fetchedName: string | null = null;
      let defaultPromptEnabled = true;

      try {
        try {
          const orgResponse = await docRouterAccountApi.getOrganization(organizationId);
          setOrganization(orgResponse);
          defaultPromptEnabled = orgResponse.default_prompt_enabled !== false;
        } catch (error) {
          console.error('Error fetching organization metadata:', error);
          // If we cannot load the organization, fall back to enabled behavior
          defaultPromptEnabled = true;
        }

        try {
          const docResponse = await docRouterOrgApi.getDocument({
            documentId: id,
            fileType: 'pdf',
            includeContent: false,
          });
          fetchedState = docResponse.state;
          fetchedName = docResponse.document_name ?? null;
          setDocumentState(fetchedState);
          setDocumentName(fetchedName);
        } catch (error) {
          console.error('Error fetching document metadata:', error);
        }

        const isProcessing = fetchedState === 'ocr_processing' || fetchedState === 'llm_processing';
        const alreadyHaveDefault =
          llmResultsRef.current['default'] ||
          loadingPromptsRef.current.has('default') ||
          failedPromptsRef.current.has('default') ||
          defaultLlmFetchStartedRef.current;
        const needDefault = defaultPromptEnabled && !isProcessing && !alreadyHaveDefault;

        if (needDefault) {
          defaultLlmFetchStartedRef.current = true;
          setLoadingPrompts(prev => new Set(prev).add('default'));
        }

        const listPromptsPromise = docRouterOrgApi.listPrompts({ document_id: id, limit: 100 });
        const defaultPromise = needDefault
          ? docRouterOrgApi
              .getLLMResult({ documentId: id, promptRevId: 'default', fallback: false })
              .then((data): { success: true; data: GetLLMResultResponse } => ({ success: true, data }))
              .catch((error): { success: false; error: unknown } => ({ success: false, error }))
          : Promise.resolve<null>(null);

        const [promptsResponse, defaultResult] = await Promise.all([listPromptsPromise, defaultPromise]);

        setMatchingPrompts(promptsResponse.prompts);

        if (needDefault && defaultResult !== null) {
          if (defaultResult.success) {
            setLlmResults(prev => ({ ...prev, 'default': defaultResult.data }));
            setFailedPrompts(prev => {
              const next = new Set(prev);
              next.delete('default');
              return next;
            });
          } else {
            const errorMessage = defaultResult.error instanceof Error ? defaultResult.error.message : String(defaultResult.error);
            const isNotFound = errorMessage.includes('not found') || errorMessage.includes('404');
              if (!isNotFound) {
                console.error('Error fetching default results:', defaultResult.error);
                setFailedPrompts(prev => new Set(prev).add('default'));
              }
          }
          setLoadingPrompts(prev => {
            const next = new Set(prev);
            next.delete('default');
            return next;
          });
        }
      } catch (error) {
        console.error('Error fetching prompts:', error);
      }
    };

    fetchData();
  }, [organizationId, id, docRouterOrgApi, docRouterAccountApi]);

  // Poll document state when processing
  useEffect(() => {
    const defaultPromptEnabled = organization ? organization.default_prompt_enabled !== false : true;
    if (!defaultPromptEnabled || !documentState || (documentState !== 'ocr_processing' && documentState !== 'llm_processing')) {
      return;
    }
    const pollInterval = setInterval(async () => {
      try {
        const docResponse = await docRouterOrgApi.getDocument({ documentId: id, fileType: 'pdf', includeContent: false });
        setDocumentState(docResponse.state);
        if (defaultPromptEnabled &&
            (docResponse.state === 'llm_completed' || docResponse.state === 'ocr_completed') &&
            !llmResults['default'] && !loadingPrompts.has('default') && !failedPrompts.has('default')) {
          setLoadingPrompts(prev => new Set(prev).add('default'));
          try {
            const defaultResults = await docRouterOrgApi.getLLMResult({
              documentId: id, promptRevId: 'default', fallback: false,
            });
            setLlmResults(prev => ({ ...prev, 'default': defaultResults }));
                  } catch (error) {
                    // If the backend doesn't have a result yet, show "No results available"
                    // instead of treating it as a permanent failure.
                    const status = getStatusFromError(error);
                    if (status !== 404) {
                      setFailedPrompts(prev => new Set(prev).add('default'));
                    }
          }
          setLoadingPrompts(prev => { const next = new Set(prev); next.delete('default'); return next; });
        }
      } catch (error) {
        console.error('Error polling document state:', error);
      }
    }, 2000);
    return () => clearInterval(pollInterval);
  }, [documentState, id, docRouterOrgApi, llmResults, loadingPrompts, failedPrompts, organization]);

  useEffect(() => {
    if (documentName) {
      loadOCRBlocks(organizationId, id, documentName);
    }
  }, [id, organizationId, documentName, loadOCRBlocks]);

  const handlePromptChange = async (promptId: string) => {
    if (expandedPrompt === promptId) {
      setExpandedPrompt('');
      return;
    }

    setExpandedPrompt(promptId);
    
    if (!llmResults[promptId]) {
      setLoadingPrompts(prev => new Set(prev).add(promptId));
      try {
        const results = await docRouterOrgApi.getLLMResult({
          documentId: id, 
          promptRevId: promptId,
          fallback: true
        });
        setLlmResults(prev => ({
          ...prev,
          [promptId]: results
        }));
        setFailedPrompts(prev => {
          const newSet = new Set(prev);
          newSet.delete(promptId);
          return newSet;
        });
      } catch (error) {
        const status = getStatusFromError(error);
        const message = getMessageFromError(error).toLowerCase();
        const isNotFound = status === 404 || message.includes('not found');

        if (!isNotFound) {
          console.error('Error fetching LLM results:', error);
          // Check if document is still processing - if so, don't mark as failed
          const isProcessing = documentState === 'ocr_processing' || documentState === 'llm_processing';
          if (!isProcessing) {
            setFailedPrompts(prev => new Set(prev).add(promptId));
          }
        }
      } finally {
        setLoadingPrompts(prev => {
          const newSet = new Set(prev);
          newSet.delete(promptId);
          return newSet;
        });
      }
    }
  };

  const handleRunPrompt = async (promptId: string) => {
    setRunningPrompts(prev => new Set(prev).add(promptId));
    try {
      await docRouterOrgApi.runLLM({
        documentId: id,
        promptRevId: promptId,
        force: true
      });
      
      const result = await docRouterOrgApi.getLLMResult({
        documentId: id,
        promptRevId: promptId,
        fallback: false
      });
      
      setLlmResults(prev => ({
        ...prev,
        [promptId]: result
      }));
    } catch (error) {
      console.error('Error running prompt:', error);
    } finally {
      setRunningPrompts(prev => {
        const next = new Set(prev);
        next.delete(promptId);
        return next;
      });
    }
  };

  const handleOpenKebabMenu = (e: React.MouseEvent<HTMLElement>, promptId: string) => {
    e.stopPropagation();
    setKebabAnchorEl(e.currentTarget);
    setKebabPromptId(promptId);
  };

  const handleCloseKebabMenu = () => {
    setKebabAnchorEl(null);
    setKebabPromptId(null);
  };

  const handleOpenRunInfo = async (promptId: string) => {
    handleCloseKebabMenu();
    setRunInfoLoading(true);
    setRunInfoOpen(true);
    try {
      const result = await docRouterOrgApi.getLLMResult({
        documentId: id,
        promptRevId: promptId,
        fallback: true
      });
      setRunInfoResult(result);
    } catch (err) {
      console.error('Error loading run info:', err);
      setRunInfoResult(null);
    } finally {
      setRunInfoLoading(false);
    }
  };

  const handleFind = (promptId: string, key: string, value: string) => {
    // Make sure value is not empty or null
    if (!value || value === 'null') return;
    
    // Clean up the value if needed
    const searchValue = value.trim();
    if (searchValue === '') return;
    
    const highlightInfo = findBlocksWithContext(searchValue, promptId, key);
    if (highlightInfo.blocks.length > 0) {
      onHighlight(highlightInfo);
    } else {
      console.log('No matches found for:', searchValue);
    }
  };

  const handleEdit = (promptId: string, key: string, value: string) => {
    if (!editMode) return; // Only allow editing when edit mode is enabled
    setEditing({ promptId, key, value });
  };

  const handleSave = async () => {
    if (!editing) return;

    try {
      const currentResult = llmResults[editing.promptId];
      if (!currentResult) return;

      // Create a deep copy of the current result
      const updatedResult = JSON.parse(JSON.stringify(currentResult.updated_llm_result));
      
      // Check if we're dealing with an array item - matches patterns like "items[2]" or "items[2].name"
      const arrayItemRegex = /(.*?)\[(\d+)\](\..*)?$/;
      const matches = editing.key.match(arrayItemRegex);
      
      if (matches) {
        // Extract array path, index, and any nested path that follows
        const arrayPath = matches[1];      // e.g., "items" 
        const index = parseInt(matches[2], 10); // e.g., 2
        const nestedPath = matches[3] ? matches[3].substring(1) : null; // e.g., "name" (without the leading dot)
        
        // Navigate to the array
        let current = updatedResult;
        const pathParts = arrayPath.split('.');
        
        // Navigate to the containing array
        for (const part of pathParts) {
          if (current[part] !== undefined) {
            current = current[part];
          } else {
            console.error('Array path not found:', arrayPath);
            return;
          }
        }
        
        // Make sure we found the array and the index is valid
        if (Array.isArray(current) && index >= 0 && index < current.length) {
          if (nestedPath) {
            // We need to update a property inside an object in the array
            const nestedPathParts = nestedPath.split('.');
            const arrayItem = current[index];
            
            // Navigate to the nested object that contains the property to update
            let currentNested = arrayItem;
            for (let i = 0; i < nestedPathParts.length - 1; i++) {
              const part = nestedPathParts[i];
              if (!currentNested[part]) {
                currentNested[part] = {};
              }
              currentNested = currentNested[part];
            }
            
            // Update the nested property
            const lastKey = nestedPathParts[nestedPathParts.length - 1];
            currentNested[lastKey] = editing.value;
          } else {
            // Update the array item directly (it's a primitive value)
            current[index] = editing.value;
          }
        }
      } else {
        // Handle normal path (non-array) - existing logic
        const pathParts = editing.key.split('.');
        let current = updatedResult;
        
        // Navigate to the nested object that contains the property to update
        for (let i = 0; i < pathParts.length - 1; i++) {
          current = current[pathParts[i]];
          if (!current) break;
        }
        
        // Update the value if we found the containing object
        if (current) {
          const lastKey = pathParts[pathParts.length - 1];
          current[lastKey] = editing.value;
        }
      }

      // Use the stored prompt_revid from the result (not the requested key) so that
      // when GET was done with fallback=true we update the actual stored record.
      const result = await docRouterOrgApi.updateLLMResult({
        documentId: id,
        promptId: currentResult.prompt_revid,
        result: updatedResult,
        isVerified: false
      });

      setLlmResults(prev => ({
        ...prev,
        [editing.promptId]: result
      }));
      setEditing(null);
    } catch (error) {
      console.error('Error saving edit:', error);
    }
  };

  const handleCancel = () => {
    setEditing(null);
  };

  // Replace the isKeyValuePairs function with a more flexible approach
  const isEditableValue = (value: unknown): boolean => {
    return typeof value === 'string' || 
           typeof value === 'number' || 
           value === null ||
           typeof value === 'boolean';
  };

  // Update the renderNestedValue function to handle arrays with editing capabilities
  const renderNestedValue = (
    promptId: string, 
    parentKey: string, 
    value: JsonValue, 
    level: number = 0,
    onFind: (promptId: string, key: string, value: string) => void,
    onEdit: (promptId: string, key: string, value: string) => void,
    editing: EditingState | null,
    handleSave: () => void,
    handleCancel: () => void,
    editMode: boolean = false
  ) => {
    // If the value is editable (string, number, boolean, null), render it with edit controls
    if (isEditableValue(value)) {
      const stringValue = value?.toString() ?? '';
      const isEmpty = stringValue === '' || stringValue === 'null' || value === null;
      const fullKey = parentKey;
      
      if (editing && editing.promptId === promptId && editing.key === fullKey) {
        return (
          <div className="flex items-center gap-2 min-w-0">
            <input
              type="text"
              value={editing.value}
              onChange={(e) => setEditing({ ...editing, value: e.target.value })}
              className="min-w-0 w-0 flex-1 px-2 py-1 text-sm border rounded"
              autoFocus
            />
            <div className="flex items-center flex-shrink-0 gap-0.5">
              <button
                onClick={handleSave}
                className="p-1.5 text-green-600 hover:bg-gray-100 rounded"
                title="Save changes"
              >
                <CheckIcon className="w-4 h-4" />
              </button>
              <button
                onClick={handleCancel}
                className="p-1.5 text-red-600 hover:bg-gray-100 rounded"
                title="Cancel"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            </div>
          </div>
        );
      }
      
      return (
        <div className="flex items-center justify-between gap-2">
          <div className={`flex-1 ${isEmpty ? 'text-gray-400 italic' : ''}`}>
            {isEmpty ? 'null' : stringValue}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onFind(promptId, fullKey, stringValue)}
              className="p-1 text-gray-600 hover:bg-gray-100 rounded"
              title="Find in document"
            >
              <MagnifyingGlassIcon className="w-4 h-4" />
            </button>
            {editMode && (
              <button
                onClick={() => onEdit(promptId, fullKey, stringValue)}
                className="p-1 text-gray-600 hover:bg-gray-100 rounded"
                title="Edit value"
              >
                <PencilIcon className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      );
    }
    
    // If it's an object, render each property recursively
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      // If the object is empty, render an empty state
      if (Object.keys(value).length === 0) {
        return (
          <div className="text-sm text-gray-500 italic">Empty object</div>
        );
      }
      
      return (
        <div className={`space-y-2 ${level > 0 ? 'ml-4 pl-2 border-l border-gray-200' : ''}`}>
          {Object.entries(value).map(([key, val]) => {
            const fullKey = parentKey ? `${parentKey}.${key}` : key;
            return (
              <div key={fullKey} className="text-sm">
                <div className="text-xs text-gray-500 mb-1">{key}</div>
                {renderNestedValue(promptId, fullKey, val, level + 1, onFind, onEdit, editing, handleSave, handleCancel, editMode)}
              </div>
            );
          })}
        </div>
      );
    }
    
    // If it's an array, render with editing capabilities
    if (Array.isArray(value)) {
      if (value.length === 0) {
        return (
          <div className="text-sm text-gray-500 italic flex justify-between items-center">
            <span>Empty array</span>
            {editMode && (
              <button
                onClick={() => handleArrayItemAdd(promptId, parentKey, [])}
                className="px-2 py-1 text-xs bg-green-50 text-green-600 rounded hover:bg-green-100"
                title="Add item"
              >
                Add Item
              </button>
            )}
          </div>
        );
      }
      
      // For arrays with primitive values, display with edit controls
      const isPrimitiveArray = value.every(item => isEditableValue(item));
      
      if (isPrimitiveArray) {
        return (
          <div className="space-y-2">
            {value.map((item, index) => {
              // Ensure array path is constructed properly for searching
              const arrayItemKey = `${parentKey}[${index}]`;
              const stringValue = item?.toString() ?? '';
              
              if (editing && editing.promptId === promptId && editing.key === arrayItemKey) {
                return (
                  <div key={index} className="flex items-center gap-2 min-w-0 pl-2 border-l-2 border-gray-200">
                    <span className="text-gray-500 text-xs w-6 flex-shrink-0">[{index}]</span>
                    <input
                      type="text"
                      value={editing.value}
                      onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                      className="min-w-0 w-0 flex-1 px-2 py-1 text-sm border rounded"
                      autoFocus
                    />
                    <div className="flex items-center flex-shrink-0 gap-0.5">
                      <button
                        onClick={handleSave}
                        className="p-1.5 text-green-600 hover:bg-gray-100 rounded"
                        title="Save changes"
                      >
                        <CheckIcon className="w-4 h-4" />
                      </button>
                      <button
                        onClick={handleCancel}
                        className="p-1.5 text-red-600 hover:bg-gray-100 rounded"
                        title="Cancel"
                      >
                        <XMarkIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              }
              
              return (
                <div key={index} className="flex items-center gap-2 pl-2 border-l-2 border-gray-200">
                  <span className="text-gray-500 text-xs w-6">[{index}]</span>
                  <span className="flex-1 font-medium text-gray-900">{stringValue}</span>
                  <button
                    onClick={() => {
                      // Ensure the value is properly formatted for search
                      const searchableValue = stringValue.trim();
                      if (searchableValue !== '') {
                        onFind(promptId, arrayItemKey, searchableValue);
                      }
                    }}
                    className="p-1 text-gray-600 hover:bg-gray-100 rounded"
                    title="Find in document"
                    disabled={!stringValue || stringValue === 'null'}
                  >
                    <MagnifyingGlassIcon className="w-4 h-4" />
                  </button>
                  {editMode && (
                    <>
                      <button
                        onClick={() => onEdit(promptId, arrayItemKey, stringValue)}
                        className="p-1 text-gray-600 hover:bg-gray-100 rounded"
                        title="Edit item"
                      >
                        <PencilIcon className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleArrayItemDelete(promptId, arrayItemKey)}
                        className="p-1 text-red-600 hover:bg-gray-100 rounded"
                        title="Delete item"
                      >
                        <XMarkIcon className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              );
            })}
            
            {editMode && (
              <div className="mt-2">
                <button
                  onClick={() => handleArrayItemAdd(promptId, parentKey, value)}
                  className="px-2 py-1 text-xs bg-green-50 text-green-600 rounded hover:bg-green-100 w-full"
                  title="Add item"
                >
                  Add Item
                </button>
              </div>
            )}
          </div>
        );
      }
      
      // For arrays of objects, render a more structured editor with proper paths
      return (
        <div className="space-y-3">
          {value.map((item, index) => {
            // Ensure array path is constructed properly
            const arrayItemKey = `${parentKey}[${index}]`;
            
            return (
              <div key={index} className="border rounded p-2 bg-gray-50 min-w-0">
                <div className="flex justify-between items-center gap-2 min-w-0 mb-2">
                  <span className="font-medium text-sm text-gray-700 min-w-0 truncate">Item {index}</span>
                  {editMode && (
                    <button
                      onClick={() => handleArrayItemDelete(promptId, arrayItemKey)}
                      className="p-1.5 text-red-600 hover:bg-gray-100 rounded flex-shrink-0"
                      title="Delete item"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  )}
                </div>
                
                {typeof item === 'object' && item !== null ? (
                  <div className="pl-3 border-l-2 border-gray-300">
                    {renderNestedValue(
                      promptId,
                      arrayItemKey,
                      item,
                      level + 1,
                      onFind,
                      onEdit,
                      editing,
                      handleSave,
                      handleCancel,
                      editMode
                    )}
                  </div>
                ) : (
                  <div className="text-sm font-medium text-gray-900">{item?.toString() ?? ''}</div>
                )}
              </div>
            );
          })}
          
          {editMode && (
            <div className="mt-2">
              <button
                onClick={() => handleArrayObjectAdd(promptId, parentKey, value)}
                className="px-2 py-1 text-xs bg-green-50 text-green-600 rounded hover:bg-green-100 w-full"
                title="Add item"
              >
                Add Item
              </button>
            </div>
          )}
        </div>
      );
    }
    
    // Fallback for any other type
    return (
      <div className="text-sm whitespace-pre-wrap break-words text-gray-700 bg-gray-50 rounded p-2">
        {JSON.stringify(value, null, 2)}
      </div>
    );
  };

  const renderPromptResults = (promptId: string) => {
    const result = llmResults[promptId];
    if (!result) {
      // Check if document is still processing
      const isProcessing = documentState === 'ocr_processing' || documentState === 'llm_processing';
      
      if (loadingPrompts.has(promptId) || isProcessing) {
        const processingMessage = isProcessing 
          ? (documentState === 'ocr_processing' ? 'Processing OCR...' : 'Processing LLM...')
          : 'Loading...';
        return <div className="p-4 text-sm text-gray-500">{processingMessage}</div>;
      }
      if (failedPrompts.has(promptId)) {
        return <div className="p-4 text-sm text-red-500">Failed to load results</div>;
      }
      return <div className="p-4 text-sm text-gray-500">No results available</div>;
    }

    // Optional grouped peer-run metadata for grouped-peer prompts.
    // Backend returns `peer_run` and omits it for legacy single-document runs.
    const peerRun: {
      match_values?: Record<string, unknown>;
      match_document_ids?: string[];
    } | undefined = (result as unknown as {
      peer_run?: {
        match_values?: Record<string, unknown>;
        match_document_ids?: string[];
      };
    }).peer_run;

    return (
      <div className="p-4 space-y-3">
        {peerRun && (peerRun.match_values || peerRun.match_document_ids) && (
          <div className="mb-3 rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-gray-900">
            <div className="mb-1 font-semibold text-blue-900">Peer match</div>
            {peerRun.match_values && (
              <div className="mb-1">
                <div className="font-medium text-blue-900">Match values</div>
                <ul className="ml-3 list-disc space-y-0.5">
                  {Object.entries(peerRun.match_values).map(([key, value]) => (
                    <li key={key}>
                      <span className="font-medium">{key}</span>
                      <span className="mx-1 text-gray-500">=</span>
                      <span className="break-all">{String(value)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {peerRun.match_document_ids && peerRun.match_document_ids.length > 0 && (
              <div className="mt-1">
                <div className="font-medium text-blue-900">Matched peer documents</div>
                <ul className="ml-3 list-disc space-y-0.5">
                  {peerRun.match_document_ids.map((docId) => (
                    <li key={docId}>
                      <a
                        href={`/orgs/${organizationId}/docs/${docId}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-700 hover:underline break-all"
                      >
                        {docId}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {renderNestedValue(
          promptId, 
          '', 
          result.updated_llm_result, 
          0, 
          handleFind, 
          handleEdit, 
          editing, 
          handleSave, 
          handleCancel,
          editMode
        )}
      </div>
    );
  };

  // Add these new handler functions to the component
  const handleArrayItemDelete = async (promptId: string, arrayKey: string) => {
    // Only allow array item deletion when edit mode is enabled
    if (!editMode) return;
    
    try {
      const result = llmResults[promptId];
      if (!result) return;

      // Create a deep copy of the current result
      const updatedResult = JSON.parse(JSON.stringify(result.updated_llm_result));
      
      // Extract the array path and index from the arrayKey
      const arrayItemRegex = /(.*?)\[(\d+)\](\..*)?$/;
      const matches = arrayKey.match(arrayItemRegex);
      
      if (!matches) {
        console.error('Invalid array key format:', arrayKey);
        return;
      }
      
      const arrayPath = matches[1];      // e.g., "items"
      const arrayIndex = parseInt(matches[2], 10); // e.g., 2
      
      // Navigate to the array
      let current = updatedResult;
      const pathParts = arrayPath.split('.');
      
      // Navigate to the containing array
      for (const part of pathParts) {
        if (current[part] !== undefined) {
          current = current[part];
        } else {
          console.error('Array path not found:', arrayPath);
          return;
        }
      }
      
      // Make sure we found the array and the index is valid
      if (Array.isArray(current) && arrayIndex >= 0 && arrayIndex < current.length) {
        // Remove the item at the specified index
        current.splice(arrayIndex, 1);
        
        // Update the result with API (use stored prompt_revid for fallback compatibility)
        const apiResult = await docRouterOrgApi.updateLLMResult({
          documentId: id,
          promptId: result.prompt_revid,
          result: updatedResult,
          isVerified: false
        });

        setLlmResults(prev => ({
          ...prev,
          [promptId]: apiResult
        }));
      }
    } catch (error) {
      console.error('Error deleting array item:', error);
    }
  };

  const handleArrayItemAdd = async (promptId: string, arrayKey: string, currentArray: JsonValue[]) => {
    // Only allow array item addition when edit mode is enabled
    if (!editMode) return;
    
    try {
      const result = llmResults[promptId];
      if (!result) return;

      // Create a deep copy of the current result
      const updatedResult = JSON.parse(JSON.stringify(result.updated_llm_result));
      
      // Determine default value based on existing array items
      let defaultValue: JsonValue = "";
      if (currentArray.length > 0) {
        const firstItem = currentArray[0];
        if (typeof firstItem === 'string') defaultValue = "";
        else if (typeof firstItem === 'number') defaultValue = 0;
        else if (typeof firstItem === 'boolean') defaultValue = false;
        else if (firstItem === null) defaultValue = null;
      }
      
      // Find the array to modify
      const pathParts = arrayKey.split('.');
      let current = updatedResult;
      let parent = updatedResult;
      let lastKey = arrayKey;
      
      // Navigate to the containing object
      for (let i = 0; i < pathParts.length; i++) {
        const part = pathParts[i];
        parent = current;
        lastKey = part;
        if (current[part] !== undefined) {
          current = current[part];
        } else {
          console.error('Path not found:', arrayKey);
          return;
        }
      }
      
      // Add the new item to the array
      if (Array.isArray(parent[lastKey])) {
        parent[lastKey].push(defaultValue);
        
        // Update the result with API (use stored prompt_revid for fallback compatibility)
        const apiResult = await docRouterOrgApi.updateLLMResult({
          documentId: id,
          promptId: result.prompt_revid,
          result: updatedResult,
          isVerified: false
        });

        setLlmResults(prev => ({
          ...prev,
          [promptId]: apiResult
        }));
      }
    } catch (error) {
      console.error('Error adding array item:', error);
    }
  };

  const handleArrayObjectAdd = async (promptId: string, arrayKey: string, currentArray: JsonValue[]) => {
    // Only allow array object addition when edit mode is enabled
    if (!editMode) return;
    
    try {
      const result = llmResults[promptId];
      if (!result) return;

      // Create a deep copy of the current result
      const updatedResult = JSON.parse(JSON.stringify(result.updated_llm_result));
      
      // Determine default object structure based on existing array items
      let defaultValue: JsonValue = {};
      if (currentArray.length > 0) {
        const firstItem = currentArray[0];
        if (typeof firstItem === 'object' && firstItem !== null) {
          // Create an empty object with the same keys
          defaultValue = Object.fromEntries(
            Object.keys(firstItem).map(key => {
              // Set default values based on the type of each field
              const val = (firstItem as Record<string, JsonValue>)[key];
              if (typeof val === 'string') return [key, ""];
              if (typeof val === 'number') return [key, 0];
              if (typeof val === 'boolean') return [key, false];
              if (val === null) return [key, null];
              if (Array.isArray(val)) return [key, []];
              return [key, {}];
            })
          );
        }
      }
      
      // Find the array to modify
      const pathParts = arrayKey.split('.');
      let current = updatedResult;
      let parent = updatedResult;
      let lastKey = arrayKey;
      
      // Navigate to the containing object
      for (let i = 0; i < pathParts.length; i++) {
        const part = pathParts[i];
        parent = current;
        lastKey = part;
        if (current[part] !== undefined) {
          current = current[part];
        } else {
          console.error('Path not found:', arrayKey);
          return;
        }
      }
      
      // Add the new object to the array
      if (Array.isArray(parent[lastKey])) {
        parent[lastKey].push(defaultValue);
        
        // Update the result with API (use stored prompt_revid for fallback compatibility)
        const apiResult = await docRouterOrgApi.updateLLMResult({
          documentId: id,
          promptId: result.prompt_revid,
          result: updatedResult,
          isVerified: false
        });

        setLlmResults(prev => ({
          ...prev,
          [promptId]: apiResult
        }));
      }
    } catch (error) {
      console.error('Error adding array object:', error);
    }
  };

  const handleDownloadResult = async (promptId: string) => {
    try {
      // Try to get the latest result from the API, even if not currently loaded
      const result = await docRouterOrgApi.getLLMResult({
        documentId: id,
        promptRevId: promptId,
        fallback: true
      });

      // Get prompt name for filename
      let promptName = 'unknown_prompt';
      if (promptId === 'default') {
        promptName = 'document_summary';
      } else {
        // Find the prompt in matchingPrompts
        const prompt = matchingPrompts.find(p => p.prompt_revid === promptId);
        if (prompt) {
          promptName = prompt.name.toLowerCase().replace(/\s+/g, '_');
        }
      }

      // Create the download data
      const downloadData = {
        prompt_id: promptId,
        document_id: id,
        organization_id: organizationId,
        extraction_result: result.updated_llm_result,
        metadata: {
          prompt_version: result.prompt_version,
          created_at: result.created_at,
          updated_at: result.updated_at,
          is_edited: result.is_edited,
          is_verified: result.is_verified
        }
      };

      // Create and download the file
      const blob = new Blob([JSON.stringify(downloadData, null, 2)], {
        type: 'application/json'
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${promptName}_${result.prompt_revid}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading result:', error);
      // Fallback to local result if API call fails
      const localResult = llmResults[promptId];
      if (localResult) {
        // Get prompt name for filename
        let promptName = 'unknown_prompt';
        if (promptId === 'default') {
          promptName = 'document_summary';
        } else {
          // Find the prompt in matchingPrompts
          const prompt = matchingPrompts.find(p => p.prompt_revid === promptId);
          if (prompt) {
            promptName = prompt.name.toLowerCase().replace(/\s+/g, '_');
          }
        }

        const downloadData = {
          prompt_id: promptId,
          document_id: id,
          organization_id: organizationId,
          extraction_result: localResult.updated_llm_result,
          metadata: {
            prompt_version: localResult.prompt_version,
            created_at: localResult.created_at,
            updated_at: localResult.updated_at,
            is_edited: localResult.is_edited,
            is_verified: localResult.is_verified
          }
        };

        const blob = new Blob([JSON.stringify(downloadData, null, 2)], {
          type: 'application/json'
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${promptName}_${localResult.prompt_revid}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    }
  };

  const defaultPromptEnabledForRender = organization?.default_prompt_enabled !== false;

  return (
    <div className="w-full h-full flex flex-col border-r border-black/10">
      <div className="h-12 min-h-[48px] flex items-center justify-between px-4 bg-gray-100 text-black font-bold border-b border-black/10">
        <span>Available Prompts</span>
        <div className="flex items-center gap-2">
          {editMode && (
            <span className="text-xs text-blue-600 bg-blue-100 px-2 py-1 rounded-md">
              Edit Mode
            </span>
          )}
          <button
            onClick={() => setEditMode(prev => !prev)}
            className={`p-1 rounded-full hover:bg-black/5 transition-colors cursor-pointer ${editMode ? 'bg-blue-100' : ''}`}
            title={editMode ? "Disable editing mode" : "Enable editing mode"}
          >
            <PencilIcon className={`w-4 h-4 ${editMode ? 'text-blue-600' : 'text-gray-600'}`} />
          </button>
        </div>
      </div>
      
      <div className="overflow-auto flex-grow">
        {/* Default prompt (title from API: e.g. Document Summary) */}
        {defaultPromptEnabledForRender && (
          <div className="border-b border-black/10">
            <div
              onClick={() => handlePromptChange('default')}
              className="w-full min-h-[48px] flex items-center justify-between px-4 bg-gray-100/[0.6] hover:bg-gray-100/[0.8] transition-colors cursor-pointer"
            >
              <span className="text-sm text-gray-900">
                {llmResults['default']?.prompt_display_name ?? 'Document Summary'}
              </span>
              <div className="flex items-center gap-2">
                <div
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRunPrompt('default');
                  }}
                  className="p-1 rounded-full hover:bg-black/5 transition-colors cursor-pointer"
                  title="Reload extraction"
                >
                  {runningPrompts.has('default') ? (
                    <div className="w-4 h-4 border-2 border-[#2B4479]/60 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <RefreshIcon fontSize="small" className="text-gray-600" />
                  )}
                </div>
                <div
                  onClick={(e) => handleOpenKebabMenu(e, 'default')}
                  className="p-1 rounded-full hover:bg-black/5 transition-colors cursor-pointer"
                  title="More actions"
                >
                  <MoreVertIcon fontSize="small" className="text-gray-600" />
                </div>
                <ChevronDownIcon 
                  className={`w-5 h-5 text-gray-600 transition-transform ${
                    expandedPrompt === 'default' ? 'rotate-180' : ''
                  }`}
                />
              </div>
            </div>
            <div 
              className={`transition-all duration-200 ease-in-out bg-white ${
                expandedPrompt === 'default' ? '' : 'hidden'
              }`}
            >
              {renderPromptResults('default')}
            </div>
          </div>
        )}

        {/* Other Prompts */}
        {matchingPrompts.length === 0 ? (
          <div className="px-4 py-3 text-sm text-gray-500">
            No tagged prompts are available for this document. Create prompts with tags matching this document&apos;s tags in the Prompts section to see them here.
          </div>
        ) : (
        matchingPrompts.map((prompt) => {
          const isExpanded = expandedPrompt === prompt.prompt_revid;
          const llmResult = llmResults[prompt.prompt_revid];
          const retrievedVersion = llmResult?.prompt_version;
          
          return (
            <div key={prompt.prompt_revid} className="border-b border-black/10">
              <div
                onClick={() => handlePromptChange(prompt.prompt_revid)}
                className="w-full min-h-[48px] flex items-center justify-between px-4 bg-gray-100/[0.6] hover:bg-gray-100/[0.8] transition-colors cursor-pointer"
              >
                <span className="text-sm text-gray-900">
                  {prompt.name} <span className="text-gray-500 text-xs">
                    {isExpanded && retrievedVersion !== undefined 
                      ? `(v${retrievedVersion})` 
                      : `(v${prompt.prompt_version})`
                    }
                  </span>
                </span>
                <div className="flex items-center gap-2">
                  <div
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRunPrompt(prompt.prompt_revid);
                    }}
                    className="p-1 rounded-full hover:bg-black/5 transition-colors cursor-pointer"
                    title="Reload extraction"
                  >
                    {runningPrompts.has(prompt.prompt_revid) ? (
                      <div className="w-4 h-4 border-2 border-[#2B4479]/60 border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <RefreshIcon fontSize="small" className="text-gray-600" />
                    )}
                  </div>
                  <div
                    onClick={(e) => handleOpenKebabMenu(e, prompt.prompt_revid)}
                    className="p-1 rounded-full hover:bg-black/5 transition-colors cursor-pointer"
                    title="More actions"
                  >
                    <MoreVertIcon fontSize="small" className="text-gray-600" />
                  </div>
                  <ChevronDownIcon 
                    className={`w-5 h-5 text-gray-600 transition-transform ${
                      isExpanded ? 'rotate-180' : ''
                    }`}
                  />
                </div>
              </div>
              <div 
                className={`transition-all duration-200 ease-in-out ${
                  isExpanded ? '' : 'hidden'
                }`}
              >
                {renderPromptResults(prompt.prompt_revid)}
              </div>
            </div>
          );
        }))}
      </div>

      {/* Kebab menu (per prompt) */}
      <Menu
        anchorEl={kebabAnchorEl}
        open={Boolean(kebabAnchorEl)}
        onClose={handleCloseKebabMenu}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <StyledMenuItem
          onClick={() => {
            if (!kebabPromptId) return;
            handleCloseKebabMenu();
            handleDownloadResult(kebabPromptId);
          }}
        >
          <DownloadIcon fontSize="small" sx={{ mr: 1 }} />
          Download
        </StyledMenuItem>
        <StyledMenuItem
          onClick={() => {
            if (!kebabPromptId) return;
            handleOpenRunInfo(kebabPromptId);
          }}
        >
          <DescriptionOutlinedIcon fontSize="small" sx={{ mr: 1 }} />
          Run Info
        </StyledMenuItem>
      </Menu>

      {/* Run info modal */}
      <Dialog open={runInfoOpen} onClose={() => setRunInfoOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Run Info</DialogTitle>
        <DialogContent dividers>
          {runInfoLoading ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 2 }}>
              <CircularProgress size={18} />
              <Typography variant="body2" color="text.secondary">
                Loading run info...
              </Typography>
            </Box>
          ) : runInfoResult ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box>
                <Typography variant="subtitle2">Prompt</Typography>
                <Typography variant="body2" color="text.secondary">
                  {runInfoResult.prompt_display_name ?? (runInfoResult.prompt_revid === 'default' ? 'Document Summary' : runInfoResult.prompt_revid)} (v{runInfoResult.prompt_version})
                </Typography>
              </Box>

              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 1 }}>
                <Typography variant="body2">
                  <strong>Created:</strong> {runInfoResult.created_at}
                </Typography>
                <Typography variant="body2">
                  <strong>Updated:</strong> {runInfoResult.updated_at}
                </Typography>
                <Typography variant="body2">
                  <strong>Edited:</strong> {String(runInfoResult.is_edited)}
                </Typography>
                <Typography variant="body2">
                  <strong>Verified:</strong> {String(runInfoResult.is_verified)}
                </Typography>
              </Box>

              <Box>
                <Typography variant="subtitle2">Prompt used (reported)</Typography>
                <Box
                  sx={{
                    mt: 1,
                    border: '1px solid rgba(0,0,0,0.12)',
                    borderRadius: 1,
                    bgcolor: 'rgba(0,0,0,0.02)',
                    p: 1.5,
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'monospace',
                    maxHeight: 320,
                    overflow: 'auto'
                  }}
                >
                  {(runInfoResult as unknown as { prompt_used?: string }).prompt_used?.trim()
                    ? (runInfoResult as unknown as { prompt_used?: string }).prompt_used as string
                    : 'No prompt_used reported by the backend for this run.'}
                </Box>
              </Box>
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary">
              No run info available.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRunInfoOpen(false)} variant="outlined">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default PDFExtractionSidebarContent;
