import React, { useEffect, useState } from 'react';
import { 
  ChevronDownIcon, 
  ArrowPathIcon,
  MagnifyingGlassIcon,
  PencilIcon,
  CheckIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import { getLLMResultApi, listPromptsApi, runLLMApi, updateLLMResultApi } from '@/utils/api';
import type { Prompt } from '@/types/index';
import { useOCR, OCRProvider } from '@/contexts/OCRContext';
import type { GetLLMResultResponse } from '@/types/index';
import type { HighlightInfo } from '@/contexts/OCRContext';

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

const PDFLeftSidebarContent = ({ organizationId, id, onHighlight }: Props) => {
  const { loadOCRBlocks, findBlocksWithContext } = useOCR();
  const [llmResults, setLlmResults] = useState<Record<string, GetLLMResultResponse>>({});
  const [matchingPrompts, setMatchingPrompts] = useState<Prompt[]>([]);
  const [runningPrompts, setRunningPrompts] = useState<Set<string>>(new Set());
  const [expandedPrompt, setExpandedPrompt] = useState<string>('default');
  const [loadingPrompts, setLoadingPrompts] = useState<Set<string>>(new Set());
  const [failedPrompts, setFailedPrompts] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<EditingState | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const promptsResponse = await listPromptsApi({organizationId: organizationId, document_id: id, limit: 100 });
        setMatchingPrompts(promptsResponse.prompts);
        
        // Fetch default prompt results
        setLoadingPrompts(prev => new Set(prev).add('default'));
        try {
          const defaultResults = await getLLMResultApi({
            organizationId: organizationId,
            documentId: id, 
            promptId: 'default',
          });
          setLlmResults(prev => ({
            ...prev,
            'default': defaultResults
          }));
          setLoadingPrompts(prev => {
            const next = new Set(prev);
            next.delete('default');
            return next;
          });
        } catch (error) {
          console.error('Error fetching default results:', error);
          setFailedPrompts(prev => new Set(prev).add('default'));
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
  }, [organizationId, id]);

  useEffect(() => {
    // Load OCR blocks in the background
    loadOCRBlocks(organizationId, id);
  }, [id, organizationId, loadOCRBlocks]);

  const handlePromptChange = async (promptId: string) => {
    if (expandedPrompt === promptId) {
      setExpandedPrompt('');
      return;
    }

    setExpandedPrompt(promptId);
    
    if (!llmResults[promptId]) {
      setLoadingPrompts(prev => new Set(prev).add(promptId));
      try {
        const results = await getLLMResultApi({
          organizationId: organizationId,
          documentId: id, 
          promptId: promptId,
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
        console.error('Error fetching LLM results:', error);
        setFailedPrompts(prev => new Set(prev).add(promptId));
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
      await runLLMApi({
        organizationId: organizationId,
        documentId: id,
        promptId: promptId,
        force: true
      });
      
      const result = await getLLMResultApi({
        organizationId: organizationId,
        documentId: id,
        promptId: promptId
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

  const handleFind = (promptId: string, key: string, value: string) => {
    const highlightInfo = findBlocksWithContext(value, promptId, key);
    if (highlightInfo.blocks.length > 0) {
      onHighlight(highlightInfo);
    }
  };

  const handleEdit = (promptId: string, key: string, value: string) => {
    setEditing({ promptId, key, value });
  };

  const handleSave = async () => {
    if (!editing) return;

    try {
      const currentResult = llmResults[editing.promptId];
      if (!currentResult) return;

      // Create a deep copy of the current result
      const updatedResult = JSON.parse(JSON.stringify(currentResult.updated_llm_result));
      
      // Check if we're dealing with an array item
      const isArrayItem = editing.key.includes('[') && editing.key.includes(']');
      
      if (isArrayItem) {
        // Parse the array path, e.g., "items[2]" => { path: "items", index: 2 }
        const matches = editing.key.match(/(.*)\[(\d+)\]$/);
        if (matches && matches.length === 3) {
          const arrayPath = matches[1];
          const index = parseInt(matches[2], 10);
          
          // Navigate to the array
          let current = updatedResult;
          const pathParts = arrayPath.split('.');
          
          // Navigate to the containing array
          for (let i = 0; i < pathParts.length; i++) {
            const part = pathParts[i];
            if (current[part] !== undefined) {
              current = current[part];
            } else {
              console.error('Array path not found:', arrayPath);
              return;
            }
          }
          
          // Update the array item if found
          if (Array.isArray(current) && index >= 0 && index < current.length) {
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

      const result = await updateLLMResultApi({
        organizationId,
        documentId: id,
        promptId: editing.promptId,
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
    handleCancel: () => void
  ) => {
    // If the value is editable (string, number, boolean, null), render it with edit controls
    if (isEditableValue(value)) {
      const stringValue = value?.toString() ?? '';
      const isEmpty = stringValue === '' || stringValue === 'null' || value === null;
      const fullKey = parentKey;
      
      if (editing && editing.promptId === promptId && editing.key === fullKey) {
        return (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={editing.value}
              onChange={(e) => setEditing({ ...editing, value: e.target.value })}
              className="flex-1 px-2 py-1 text-sm border rounded"
              autoFocus
            />
            <button
              onClick={handleSave}
              className="p-1 text-green-600 hover:bg-gray-100 rounded"
              title="Save changes"
            >
              <CheckIcon className="w-4 h-4" />
            </button>
            <button
              onClick={handleCancel}
              className="p-1 text-red-600 hover:bg-gray-100 rounded"
              title="Cancel"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
        );
      }

      return (
        <div className="flex items-center gap-2">
          <span className="flex-1 font-medium text-gray-900">
            {isEmpty ? '' : stringValue}
          </span>
          <button
            onClick={() => onFind(promptId, fullKey, stringValue)}
            className={`p-1 text-gray-600 hover:bg-gray-100 rounded ${isEmpty ? 'opacity-50' : ''}`}
            title="Find in document"
            disabled={isEmpty}
          >
            <MagnifyingGlassIcon className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit(promptId, fullKey, stringValue)}
            className="p-1 text-gray-600 hover:bg-gray-100 rounded"
            title="Edit extraction"
          >
            <PencilIcon className="w-4 h-4" />
          </button>
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
                {renderNestedValue(promptId, fullKey, val, level + 1, onFind, onEdit, editing, handleSave, handleCancel)}
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
            <button
              onClick={() => handleArrayItemAdd(promptId, parentKey, [])}
              className="px-2 py-1 text-xs bg-green-50 text-green-600 rounded hover:bg-green-100"
              title="Add item"
            >
              Add Item
            </button>
          </div>
        );
      }
      
      // For arrays with primitive values, display with edit controls
      const isPrimitiveArray = value.every(item => isEditableValue(item));
      
      if (isPrimitiveArray) {
        return (
          <div className="space-y-2">
            {value.map((item, index) => {
              const arrayItemKey = `${parentKey}[${index}]`;
              const stringValue = item?.toString() ?? '';
              
              if (editing && editing.promptId === promptId && editing.key === arrayItemKey) {
                return (
                  <div key={index} className="flex items-center gap-2 pl-2 border-l-2 border-gray-200">
                    <span className="text-gray-500 text-xs w-6">[{index}]</span>
                    <input
                      type="text"
                      value={editing.value}
                      onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                      className="flex-1 px-2 py-1 text-sm border rounded"
                      autoFocus
                    />
                    <button
                      onClick={handleSave}
                      className="p-1 text-green-600 hover:bg-gray-100 rounded"
                      title="Save changes"
                    >
                      <CheckIcon className="w-4 h-4" />
                    </button>
                    <button
                      onClick={handleCancel}
                      className="p-1 text-red-600 hover:bg-gray-100 rounded"
                      title="Cancel"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                );
              }
              
              return (
                <div key={index} className="flex items-center gap-2 pl-2 border-l-2 border-gray-200">
                  <span className="text-gray-500 text-xs w-6">[{index}]</span>
                  <span className="flex-1 font-medium text-gray-900">{stringValue}</span>
                  <button
                    onClick={() => onFind(promptId, arrayItemKey, stringValue)}
                    className="p-1 text-gray-600 hover:bg-gray-100 rounded"
                    title="Find in document"
                  >
                    <MagnifyingGlassIcon className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => onEdit(promptId, arrayItemKey, stringValue)}
                    className="p-1 text-gray-600 hover:bg-gray-100 rounded"
                    title="Edit item"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleArrayItemDelete(promptId, parentKey, index, value)}
                    className="p-1 text-red-600 hover:bg-gray-100 rounded"
                    title="Delete item"
                  >
                    <XMarkIcon className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
            
            <div className="mt-2">
              <button
                onClick={() => handleArrayItemAdd(promptId, parentKey, value)}
                className="px-2 py-1 text-xs bg-green-50 text-green-600 rounded hover:bg-green-100 w-full"
                title="Add item"
              >
                Add Item
              </button>
            </div>
          </div>
        );
      }
      
      // For arrays of objects, render a more structured editor
      return (
        <div className="space-y-3">
          {value.map((item, index) => {
            const arrayItemKey = `${parentKey}[${index}]`;
            
            return (
              <div key={index} className="border rounded p-2 bg-gray-50">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-medium text-sm text-gray-700">Item {index}</span>
                  <button
                    onClick={() => handleArrayItemDelete(promptId, parentKey, index, value)}
                    className="p-1 text-red-600 hover:bg-gray-100 rounded"
                    title="Delete item"
                  >
                    <XMarkIcon className="w-4 h-4" />
                  </button>
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
                      handleCancel
                    )}
                  </div>
                ) : (
                  <div className="text-sm font-medium text-gray-900">{item?.toString() ?? ''}</div>
                )}
              </div>
            );
          })}
          
          <div className="mt-2">
            <button
              onClick={() => handleArrayObjectAdd(promptId, parentKey, value)}
              className="px-2 py-1 text-xs bg-green-50 text-green-600 rounded hover:bg-green-100 w-full"
              title="Add item"
            >
              Add Item
            </button>
          </div>
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
      if (loadingPrompts.has(promptId)) {
        return <div className="p-4 text-sm text-gray-500">Loading...</div>;
      }
      if (failedPrompts.has(promptId)) {
        return <div className="p-4 text-sm text-red-500">Failed to load results</div>;
      }
      return <div className="p-4 text-sm text-gray-500">No results available</div>;
    }

    return (
      <div className="p-4 space-y-3">
        {renderNestedValue(
          promptId, 
          '', 
          result.updated_llm_result, 
          0, 
          handleFind, 
          handleEdit, 
          editing, 
          handleSave, 
          handleCancel
        )}
      </div>
    );
  };

  // Add these new handler functions to the component
  const handleArrayItemDelete = async (promptId: string, arrayKey: string, index: number, currentArray: JsonValue[]) => {
    try {
      const result = llmResults[promptId];
      if (!result) return;

      // Create a deep copy of the current result
      const updatedResult = JSON.parse(JSON.stringify(result.updated_llm_result));
      
      // Find the array to modify
      const pathParts = arrayKey.split('.');
      let current = updatedResult;
      
      // Navigate to the containing object
      for (let i = 0; i < pathParts.length; i++) {
        const part = pathParts[i];
        if (current[part] !== undefined) {
          current = current[part];
        } else {
          console.error('Path not found:', arrayKey);
          return;
        }
      }
      
      // Remove the specified index if it's an array
      if (Array.isArray(current)) {
        current.splice(index, 1);
        
        // Update the result with API
        const apiResult = await updateLLMResultApi({
          organizationId,
          documentId: id,
          promptId: promptId,
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
        
        // Update the result with API
        const apiResult = await updateLLMResultApi({
          organizationId,
          documentId: id,
          promptId: promptId,
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
              const val = (firstItem as any)[key];
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
        
        // Update the result with API
        const apiResult = await updateLLMResultApi({
          organizationId,
          documentId: id,
          promptId: promptId,
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

  return (
    <div className="w-full h-full flex flex-col border-r border-black/10">
      <div className="h-12 min-h-[48px] flex items-center px-4 bg-gray-100 text-black font-bold border-b border-black/10">
        Available Prompts
      </div>
      
      <div className="overflow-auto flex-grow">
        {/* Default Prompt */}
        <div className="border-b border-black/10">
          <div
            onClick={() => handlePromptChange('default')}
            className="w-full min-h-[48px] flex items-center justify-between px-4 bg-gray-100/[0.6] hover:bg-gray-100/[0.8] transition-colors cursor-pointer"
          >
            <span className="text-sm text-gray-900">Default Prompt</span>
            <div className="flex items-center gap-2">
              <div
                onClick={(e) => {
                  e.stopPropagation();
                  handleRunPrompt('default');
                }}
                className="p-1 rounded-full hover:bg-black/5 transition-colors cursor-pointer"
              >
                {runningPrompts.has('default') ? (
                  <div className="w-4 h-4 border-2 border-[#2B4479]/60 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <ArrowPathIcon className="w-4 h-4 text-gray-600" />
                )}
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

        {/* Other Prompts */}
        {matchingPrompts.map((prompt) => (
          <div key={prompt.id} className="border-b border-black/10">
            <div
              onClick={() => handlePromptChange(prompt.id)}
              className="w-full min-h-[48px] flex items-center justify-between px-4 bg-gray-100/[0.6] hover:bg-gray-100/[0.8] transition-colors cursor-pointer"
            >
              <span className="text-sm text-gray-900">
                {prompt.name} <span className="text-gray-500 text-xs">(v{prompt.version})</span>
              </span>
              <div className="flex items-center gap-2">
                <div
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRunPrompt(prompt.id);
                  }}
                  className="p-1 rounded-full hover:bg-black/5 transition-colors cursor-pointer"
                >
                  {runningPrompts.has(prompt.id) ? (
                    <div className="w-4 h-4 border-2 border-[#2B4479]/60 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <ArrowPathIcon className="w-4 h-4 text-gray-600" />
                  )}
                </div>
                <ChevronDownIcon 
                  className={`w-5 h-5 text-gray-600 transition-transform ${
                    expandedPrompt === prompt.id ? 'rotate-180' : ''
                  }`}
                />
              </div>
            </div>
            <div 
              className={`transition-all duration-200 ease-in-out ${
                expandedPrompt === prompt.id ? '' : 'hidden'
              }`}
            >
              {renderPromptResults(prompt.id)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// Wrap the component with OCRProvider
const PDFLeftSidebar = (props: Props) => {
  return (
    <OCRProvider>
      <PDFLeftSidebarContent {...props} />
    </OCRProvider>
  );
};

export default PDFLeftSidebar;
