import React, { useEffect, useState, useMemo, useRef, useId } from 'react';
import { Check, Download, FileText, Pencil, Play, RefreshCw, Search, X } from 'lucide-react';
import { ExtractionPromptRow } from '@/components/pdf/ExtractionPromptRow';
import { resultPreview } from '@/lib/results';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { DocRouterAccountApi, DocRouterOrgApi } from '@/utils/api';
import type { Organization } from '@docrouter/sdk';
import type { Prompt } from '@docrouter/sdk';
import { useOCRBlocks } from '@/hooks/useOCRBlocks';
import type { GetLLMResultResponse } from '@docrouter/sdk';
import type { HighlightInfo } from '@/hooks/useOCRBlocks';
import DraggablePanel from '@/components/DraggablePanel';
import type { PDFDocumentProxy } from 'pdfjs-dist';

interface Props {
  organizationId: string;
  id: string;
  pdfDocument?: PDFDocumentProxy | null;
  onHighlight: (highlight: HighlightInfo) => void;
}

interface EditingState {
  promptId: string;
  key: string;
  value: string;
}

// Update the type definition to handle nested structures
type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

const PDFExtractionSidebarContent = ({ organizationId, id, pdfDocument, onHighlight }: Props) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const { loadOCRBlocks, findBlocksWithContext } = useOCRBlocks();
  const [llmResults, setLlmResults] = useState<Record<string, GetLLMResultResponse>>({});
  const [matchingPrompts, setMatchingPrompts] = useState<Prompt[]>([]);
  const [runningPrompts, setRunningPrompts] = useState<Set<string>>(new Set());
  const [expandedPrompt, setExpandedPrompt] = useState<string>('default');
  const [loadingPrompts, setLoadingPrompts] = useState<Set<string>>(new Set());
  const [prefetchingPrompts, setPrefetchingPrompts] = useState<Set<string>>(new Set());
  const [failedPrompts, setFailedPrompts] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<EditingState | null>(null);
  const [editMode, setEditMode] = useState<boolean>(false);
  const [documentState, setDocumentState] = useState<string | null>(null);
  const defaultLlmFetchStartedRef = React.useRef(false);
  /** Cycle index for repeated Search on the same extraction (first click = 1st match, then next match). */
  const extractionFindCycleRef = useRef<{ sig: string; index: number } | null>(null);

  const [documentName, setDocumentName] = useState<string | null>(null);
  const [organization, setOrganization] = useState<Organization | null>(null);

  const [runInfoOpen, setRunInfoOpen] = useState(false);
  const [runInfoPromptId, setRunInfoPromptId] = useState<string | null>(null);
  const [runInfoLoading, setRunInfoLoading] = useState(false);
  const [runInfoResult, setRunInfoResult] = useState<GetLLMResultResponse | null>(null);

  // Refs mirror state so the fetch effect can read current values without being in the dependency array
  const llmResultsRef = React.useRef(llmResults);
  const loadingPromptsRef = React.useRef(loadingPrompts);
  const prefetchingPromptsRef = React.useRef(prefetchingPrompts);
  const failedPromptsRef = React.useRef(failedPrompts);
  llmResultsRef.current = llmResults;
  loadingPromptsRef.current = loadingPrompts;
  prefetchingPromptsRef.current = prefetchingPrompts;
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
    extractionFindCycleRef.current = null;
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
              .getLLMResult({ documentId: id, promptRevId: 'default', promptRevIdFallback: false })
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
              documentId: id, promptRevId: 'default', promptRevIdFallback: false,
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

  // Load results for tagged prompts so collapsed row previews are correct before the user expands.
  useEffect(() => {
    const isProcessing =
      documentState === 'ocr_processing' || documentState === 'llm_processing';
    if (isProcessing || matchingPrompts.length === 0) return;

    let cancelled = false;

    const prefetchOne = async (promptId: string) => {
      if (
        llmResultsRef.current[promptId] ||
        loadingPromptsRef.current.has(promptId) ||
        prefetchingPromptsRef.current.has(promptId) ||
        failedPromptsRef.current.has(promptId)
      ) {
        return;
      }

      setPrefetchingPrompts((prev) => new Set(prev).add(promptId));
      try {
        const results = await docRouterOrgApi.getLLMResult({
          documentId: id,
          promptRevId: promptId,
          promptRevIdFallback: true,
        });
        if (cancelled) return;
        setLlmResults((prev) => ({ ...prev, [promptId]: results }));
        setFailedPrompts((prev) => {
          const next = new Set(prev);
          next.delete(promptId);
          return next;
        });
      } catch (error) {
        if (cancelled) return;
        const status = getStatusFromError(error);
        const message = getMessageFromError(error).toLowerCase();
        const isNotFound = status === 404 || message.includes('not found');
        if (!isNotFound) {
          console.error('Error prefetching LLM results:', error);
          setFailedPrompts((prev) => new Set(prev).add(promptId));
        }
      } finally {
        if (!cancelled) {
          setPrefetchingPrompts((prev) => {
            const next = new Set(prev);
            next.delete(promptId);
            return next;
          });
        }
      }
    };

    const prefetchMatchingPromptResults = async () => {
      await Promise.all(matchingPrompts.map((prompt) => prefetchOne(prompt.prompt_revid)));
    };

    void prefetchMatchingPromptResults();
    return () => {
      cancelled = true;
    };
  }, [matchingPrompts, documentState, id, docRouterOrgApi]);

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

    if (!llmResults[promptId] && !prefetchingPromptsRef.current.has(promptId)) {
      setLoadingPrompts(prev => new Set(prev).add(promptId));
      try {
        const results = await docRouterOrgApi.getLLMResult({
          documentId: id, 
          promptRevId: promptId,
          promptRevIdFallback: true
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
        promptRevIdFallback: false
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

  const handleOpenRunInfo = async (promptId: string) => {
    setRunInfoPromptId(promptId);
    setRunInfoOpen(true);
    const cachedResult = llmResults[promptId];
    if (cachedResult) {
      setRunInfoResult(cachedResult);
      setRunInfoLoading(false);
      return;
    }

    setRunInfoLoading(true);
    setRunInfoResult(null);
    try {
      const result = await docRouterOrgApi.getLLMResult({
        documentId: id,
        promptRevId: promptId,
        promptRevIdFallback: true
      });
      setRunInfoResult(result);
    } catch (err) {
      console.error('Error loading run info:', err);
      setRunInfoResult(null);
    } finally {
      setRunInfoLoading(false);
    }
  };

  const handleFind = async (promptId: string, key: string, value: string) => {
    // Make sure value is not empty or null
    if (!value || value === 'null') return;
    
    // Clean up the value if needed
    const searchValue = value.trim();
    if (searchValue === '') return;
    
    const full = await findBlocksWithContext(searchValue, promptId, key, pdfDocument);
    const ocrCount = full.blocks.length;
    const pdfHits = full.pdfFallbackHits ?? [];
    const pdfCount = pdfHits.length;

    if (ocrCount === 0 && pdfCount === 0) {
      extractionFindCycleRef.current = null;
      console.log('No matches found for:', searchValue);
      return;
    }

    const sig = `${promptId}\0${key ?? ''}\0${searchValue}`;
    const total = ocrCount > 0 ? ocrCount : pdfCount;

    let idx: number;
    const prev = extractionFindCycleRef.current;
    if (!prev || prev.sig !== sig) {
      idx = 0;
    } else {
      idx = (prev.index + 1) % total;
    }
    extractionFindCycleRef.current = { sig, index: idx };

    const highlightInfo: HighlightInfo =
      ocrCount > 0
        ? { ...full, blocks: [full.blocks[idx]], pdfFallbackHits: undefined }
        : { ...full, blocks: [], pdfFallbackHits: [pdfHits[idx]] };

    onHighlight(highlightInfo);
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
          <div className="flex min-w-0 items-center gap-2">
            <Input
              type="text"
              value={editing.value}
              onChange={(e) => setEditing({ ...editing, value: e.target.value })}
              className="min-w-0 flex-1"
              autoFocus
            />
            <div className="flex shrink-0 items-center gap-0.5">
              <Button type="button" variant="ghost" size="icon-sm" onClick={handleSave} title="Save changes">
                <Check className="text-success" />
              </Button>
              <Button type="button" variant="ghost" size="icon-sm" onClick={handleCancel} title="Cancel">
                <X className="text-destructive" />
              </Button>
            </div>
          </div>
        );
      }
      
      return (
        <div className="group flex items-start justify-between gap-2">
          <span
            className={`min-w-0 flex-1 break-words text-sm whitespace-pre-wrap ${
              isEmpty ? 'text-muted-foreground italic' : 'text-foreground'
            }`}
          >
            {isEmpty ? '—' : stringValue}
          </span>
          <div className="flex shrink-0 items-center gap-0.5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => onFind(promptId, fullKey, stringValue)}
              title="Find in document"
              disabled={isEmpty}
            >
              <Search />
            </Button>
            {editMode ? (
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => onEdit(promptId, fullKey, stringValue)}
                title="Edit value"
              >
                <Pencil />
              </Button>
            ) : null}
          </div>
        </div>
      );
    }
    
    // If it's an object, render each property recursively
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      // If the object is empty, render an empty state
      if (Object.keys(value).length === 0) {
        return (
          <span className="text-sm text-muted-foreground">No fields</span>
        );
      }
      
      return (
        <dl className={level > 0 ? 'flex flex-col gap-1 border-l border-border pl-3' : 'flex flex-col gap-2'}>
          {Object.entries(value).map(([key, val]) => {
            const fullKey = parentKey ? `${parentKey}.${key}` : key;
            return (
              <div key={fullKey} className="min-w-0 text-sm">
                <dt className="text-xs text-muted-foreground">{key}</dt>
                <dd className="break-words">
                  {renderNestedValue(promptId, fullKey, val, level + 1, onFind, onEdit, editing, handleSave, handleCancel, editMode)}
                </dd>
              </div>
            );
          })}
        </dl>
      );
    }
    
    // If it's an array, render with editing capabilities
    if (Array.isArray(value)) {
      if (value.length === 0) {
        return (
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>None</span>
            {editMode ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => handleArrayItemAdd(promptId, parentKey, [])}
              >
                Add item
              </Button>
            ) : null}
          </div>
        );
      }
      
      // For arrays with primitive values, display with edit controls
      const isPrimitiveArray = value.every(item => isEditableValue(item));
      
      if (isPrimitiveArray) {
        return (
          <ol className="flex list-decimal flex-col gap-2 pl-5">
            {value.map((item, index) => {
              // Ensure array path is constructed properly for searching
              const arrayItemKey = `${parentKey}[${index}]`;
              const stringValue = item?.toString() ?? '';
              
              if (editing && editing.promptId === promptId && editing.key === arrayItemKey) {
                return (
                  <li key={index} className="flex min-w-0 items-center gap-2">
                    <Input
                      type="text"
                      value={editing.value}
                      onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                      className="min-w-0 flex-1"
                      autoFocus
                    />
                    <Button type="button" variant="ghost" size="icon-sm" onClick={handleSave} title="Save changes">
                      <Check className="text-success" />
                    </Button>
                    <Button type="button" variant="ghost" size="icon-sm" onClick={handleCancel} title="Cancel">
                      <X className="text-destructive" />
                    </Button>
                  </li>
                );
              }
              
              return (
                <li key={index} className="group flex items-start gap-2">
                  <span className="min-w-0 flex-1 break-words text-sm">{stringValue}</span>
                  <div className="flex shrink-0 items-center gap-0.5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => {
                        const searchableValue = stringValue.trim();
                        if (searchableValue !== '') {
                          onFind(promptId, arrayItemKey, searchableValue);
                        }
                      }}
                      title="Find in document"
                      disabled={!stringValue || stringValue === 'null'}
                    >
                      <Search />
                    </Button>
                    {editMode ? (
                      <>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => onEdit(promptId, arrayItemKey, stringValue)}
                          title="Edit item"
                        >
                          <Pencil />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => handleArrayItemDelete(promptId, arrayItemKey)}
                          title="Delete item"
                        >
                          <X className="text-destructive" />
                        </Button>
                      </>
                    ) : null}
                  </div>
                </li>
              );
            })}
            
            {editMode ? (
              <li className="list-none">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => handleArrayItemAdd(promptId, parentKey, value)}
                >
                  Add item
                </Button>
              </li>
            ) : null}
          </ol>
        );
      }
      
      // For arrays of objects, render a more structured editor with proper paths
      return (
        <ol className="flex list-decimal flex-col gap-3 pl-5">
          {value.map((item, index) => {
            const arrayItemKey = `${parentKey}[${index}]`;
            
            return (
              <li key={index} className="min-w-0">
                <div className="mb-2 flex items-center justify-between gap-2">
                  {editMode ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="ml-auto"
                      onClick={() => handleArrayItemDelete(promptId, arrayItemKey)}
                      title="Delete item"
                    >
                      <X className="text-destructive" />
                    </Button>
                  ) : null}
                </div>
                {typeof item === 'object' && item !== null ? (
                  renderNestedValue(
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
                  )
                ) : (
                  <span className="text-sm">{item?.toString() ?? ''}</span>
                )}
              </li>
            );
          })}
          
          {editMode ? (
            <li className="list-none">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => handleArrayObjectAdd(promptId, parentKey, value)}
              >
                Add item
              </Button>
            </li>
          ) : null}
        </ol>
      );
    }
    
    // Fallback for any other type
    return (
      <pre className="overflow-x-auto rounded-md border border-border bg-muted/30 p-2 text-xs whitespace-pre-wrap break-words">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  };

  const renderPromptResults = (promptId: string) => {
    const result = llmResults[promptId];
    if (!result) {
      const isProcessing = documentState === 'ocr_processing' || documentState === 'llm_processing';

      if (prefetchingPrompts.has(promptId) && !loadingPrompts.has(promptId)) {
        return null;
      }

      if (loadingPrompts.has(promptId) || isProcessing) {
        const processingMessage = isProcessing
          ? documentState === 'ocr_processing'
            ? 'Processing OCR…'
            : 'Processing LLM…'
          : 'Loading…';
        return (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-4" />
            {processingMessage}
          </p>
        );
      }
      if (failedPrompts.has(promptId)) {
        return (
          <Alert variant="destructive">
            <AlertDescription>Failed to load results.</AlertDescription>
          </Alert>
        );
      }
      return <p className="text-sm text-muted-foreground">No results on this document yet.</p>;
    }

    const payload = result.updated_llm_result;
    const entries = Object.entries(payload);

    if (entries.length === 1) {
      return (
        <div className="text-sm break-words">
          {renderNestedValue(
            promptId,
            entries[0][0],
            entries[0][1],
            0,
            handleFind,
            handleEdit,
            editing,
            handleSave,
            handleCancel,
            editMode,
          )}
        </div>
      );
    }

    return renderNestedValue(
      promptId,
      '',
      payload,
      0,
      handleFind,
      handleEdit,
      editing,
      handleSave,
      handleCancel,
      editMode,
    );
  };

  const collapsedPreview = (promptId: string): { text: string; failed?: boolean } => {
    const result = llmResults[promptId];
    if (result) {
      return { text: resultPreview(result.updated_llm_result as Record<string, unknown>) };
    }
    if (prefetchingPrompts.has(promptId)) {
      return { text: '' };
    }
    const isProcessing = documentState === 'ocr_processing' || documentState === 'llm_processing';
    if (loadingPrompts.has(promptId) || runningPrompts.has(promptId) || isProcessing) {
      if (isProcessing) {
        return {
          text:
            documentState === 'ocr_processing' ? 'Processing OCR…' : 'Processing LLM…',
        };
      }
      return { text: runningPrompts.has(promptId) ? 'Running…' : 'Loading…' };
    }
    if (failedPrompts.has(promptId)) {
      return { text: 'Failed to load results', failed: true };
    }
    return { text: 'Not run yet' };
  };

  const promptRowActions = (promptId: string) => {
    const hasResult = Boolean(llmResults[promptId]);
    const running = runningPrompts.has(promptId);
    return [
      {
        label: hasResult ? 'Run again' : 'Run',
        icon: hasResult ? RefreshCw : Play,
        onSelect: () => void handleRunPrompt(promptId),
        disabled: running,
      },
      hasResult && {
        label: 'Correct',
        icon: Pencil,
        onSelect: () => {
          setEditMode(true);
          if (expandedPrompt !== promptId) {
            void handlePromptChange(promptId);
          }
        },
      },
      hasResult && {
        label: 'Download',
        icon: Download,
        onSelect: () => void handleDownloadResult(promptId),
      },
      {
        label: 'Run info',
        icon: FileText,
        onSelect: () => void handleOpenRunInfo(promptId),
      },
    ];
  };

  const listBaseId = useId();

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
        promptRevIdFallback: true
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
        prompt_revid: result.prompt_revid,
        prompt_id: result.prompt_id,
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
          prompt_revid: localResult.prompt_revid,
          prompt_id: localResult.prompt_id,
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
    <div className="flex h-full w-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border pb-2">
        <span className="text-sm font-medium text-foreground">Results</span>
        <div className="flex items-center gap-1.5">
          {editMode ? (
            <Badge variant="secondary" className="font-normal">
              Editing
            </Badge>
          ) : null}
          <Button
            type="button"
            variant={editMode ? 'secondary' : 'ghost'}
            size="icon-sm"
            onClick={() => setEditMode((prev) => !prev)}
            title={editMode ? 'Disable editing' : 'Enable editing'}
            aria-pressed={editMode}
          >
            <Pencil />
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto overscroll-y-contain">
        {defaultPromptEnabledForRender ? (
          <ExtractionPromptRow
            ariaLabel={llmResults.default?.prompt_display_name ?? 'Document Summary'}
            title={llmResults.default?.prompt_display_name ?? 'Document Summary'}
            versionLabel={
              llmResults.default?.prompt_version !== undefined
                ? `v${llmResults.default.prompt_version}`
                : undefined
            }
            open={expandedPrompt === 'default'}
            preview={collapsedPreview('default').text}
            previewFailed={collapsedPreview('default').failed}
            running={runningPrompts.has('default')}
            loading={loadingPrompts.has('default')}
            failed={failedPrompts.has('default')}
            isVerified={llmResults.default?.is_verified}
            isEdited={llmResults.default?.is_edited}
            bodyId={`${listBaseId}-default`}
            onToggle={() => void handlePromptChange('default')}
            actions={promptRowActions('default')}
          >
            {renderPromptResults('default')}
          </ExtractionPromptRow>
        ) : null}

        {matchingPrompts.length === 0 ? (
          <p className="py-3 text-sm text-muted-foreground">
            No tagged prompts match this document. Add prompts whose tags overlap this document&apos;s tags
            to see them here.
          </p>
        ) : (
          matchingPrompts.map((prompt) => {
            const promptId = prompt.prompt_revid;
            const isExpanded = expandedPrompt === promptId;
            const llmResult = llmResults[promptId];
            const version = isExpanded && llmResult?.prompt_version !== undefined
              ? llmResult.prompt_version
              : prompt.prompt_version;
            const previewMeta = collapsedPreview(promptId);

            return (
              <ExtractionPromptRow
                key={promptId}
                ariaLabel={prompt.name}
                title={prompt.name}
                versionLabel={`v${version}`}
                open={isExpanded}
                preview={previewMeta.text}
                previewFailed={previewMeta.failed}
                running={runningPrompts.has(promptId)}
                loading={loadingPrompts.has(promptId) && isExpanded}
                failed={failedPrompts.has(promptId)}
                isVerified={llmResult?.is_verified}
                isEdited={llmResult?.is_edited}
                bodyId={`${listBaseId}-${promptId}`}
                onToggle={() => void handlePromptChange(promptId)}
                actions={promptRowActions(promptId)}
              >
                {renderPromptResults(promptId)}
              </ExtractionPromptRow>
            );
          })
        )}
      </div>

      {runInfoOpen && (
        <>
          <div
            className="fixed inset-0 z-[70] bg-black/50"
            onClick={() => {
              setRunInfoOpen(false);
              setRunInfoPromptId(null);
            }}
            role="presentation"
          />
          <DraggablePanel
            open={runInfoOpen}
            resetToken={`${id}-${runInfoPromptId ?? ''}`}
            anchorPercent={{ x: 50, y: 45 }}
            width="min(100vw - 32px, 42rem)"
            height="min(90vh, 820px)"
            zIndex={71}
            ariaLabel="Run info"
            title={
              <>
                <FileText className="size-4 shrink-0 text-primary" aria-hidden />
                <span className="truncate">Run Info</span>
              </>
            }
            headerActions={
              <button
                type="button"
                onClick={() => {
                  setRunInfoOpen(false);
                  setRunInfoPromptId(null);
                }}
                className="rounded-md bg-primary-600 px-3 py-1.5 text-xs text-white hover:bg-primary-700"
              >
                Close
              </button>
            }
          >
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-6 pb-6 pt-2">
            {runInfoLoading ? (
              <div className="flex items-center gap-3 py-6">
                <div
                  className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-primary-600"
                  aria-hidden
                />
                <span className="text-sm italic text-gray-500">Loading run info...</span>
              </div>
            ) : runInfoResult ? (
              (() => {
                const runMeta = runInfoResult.run;
                const hasPeerBlock =
                  !!runMeta &&
                  ((runMeta.match_values && Object.keys(runMeta.match_values).length > 0) ||
                    (!!runMeta.match_document_ids && runMeta.match_document_ids.length > 0));
                const promptUsedText = runMeta?.prompt?.trim();
                // The backend prompt editor route expects `promptRevId` to be a Mongo ObjectId.
                // Our "default" prompt is synthetic and uses `prompt_revid="default"`, so
                // linking to `/prompts/default` would fail. Route to the prompts list instead.
                const promptEditHref =
                  runInfoResult.prompt_revid === 'default'
                    ? `/orgs/${organizationId}/prompts`
                    : `/orgs/${organizationId}/prompts/${encodeURIComponent(runInfoResult.prompt_revid)}`;
                const promptLinkLabel =
                  runInfoResult.prompt_revid === 'default'
                    ? 'Document Summary'
                    : runInfoResult.prompt_revid;
                const showDisplayNamePrefix =
                  !!runInfoResult.prompt_display_name && runInfoResult.prompt_revid !== 'default';
                return (
                  <div className="flex min-h-0 flex-1 flex-col gap-4">
                    <div className="min-h-0 shrink overflow-y-auto [&::-webkit-scrollbar]:w-2.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent">
                      <div className="space-y-4">
                    <div>
                      <label className="mb-1 block text-sm font-semibold text-gray-700">Prompt</label>
                      <div className="break-words rounded border bg-gray-50 p-2 text-sm text-gray-900">
                        {showDisplayNamePrefix ? (
                          <span className="text-gray-800">{runInfoResult.prompt_display_name} · </span>
                        ) : null}
                        <a
                          href={promptEditHref}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="break-all font-mono text-primary-600 hover:underline"
                        >
                          {promptLinkLabel}
                        </a>
                        <span className="text-gray-600"> (v{runInfoResult.prompt_version})</span>
                      </div>
                    </div>

                    <div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="mb-1 block text-xs font-semibold text-gray-700">Created</label>
                          <div className="break-all rounded border bg-gray-50 p-2 font-mono text-xs text-gray-900">
                            {runInfoResult.created_at}
                          </div>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-semibold text-gray-700">Updated</label>
                          <div className="break-all rounded border bg-gray-50 p-2 font-mono text-xs text-gray-900">
                            {runInfoResult.updated_at}
                          </div>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-semibold text-gray-700">Edited</label>
                          <div className="rounded border bg-gray-50 p-2 text-gray-900">
                            {String(runInfoResult.is_edited)}
                          </div>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-semibold text-gray-700">Verified</label>
                          <div className="rounded border bg-gray-50 p-2 text-gray-900">
                            {String(runInfoResult.is_verified)}
                          </div>
                        </div>
                      </div>
                    </div>

                    {hasPeerBlock && runMeta && (
                      <div>
                        <div className="grid grid-cols-2 gap-4">
                          {runMeta.match_values && Object.keys(runMeta.match_values).length > 0 && (
                              <div>
                                <label className="mb-1 block text-xs font-semibold text-gray-700">
                                  Match values
                                </label>
                                <div className="rounded border bg-gray-50 p-2 text-sm text-gray-900">
                                  <ul className="list-disc space-y-1 pl-4">
                                    {Object.entries(runMeta.match_values).map(([key, value]) => (
                                      <li key={key} className="break-all">
                                        <span className="font-semibold">{key}</span>
                                        <span className="mx-1 text-gray-400">=</span>
                                        <span className="font-mono text-xs">{String(value)}</span>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              </div>
                            )}
                          {runMeta.match_document_ids && runMeta.match_document_ids.length > 0 && (
                              <div>
                                <label className="mb-1 block text-xs font-semibold text-gray-700">
                                  Matched peer documents
                                </label>
                                <div className="rounded border bg-gray-50 p-2 text-sm">
                                  <ul className="list-disc space-y-1 pl-4">
                                    {runMeta.match_document_ids.map(docId => (
                                      <li key={docId} className="break-all">
                                        <a
                                          href={`/orgs/${organizationId}/docs/${docId}`}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="font-mono text-sm text-primary-600 hover:underline"
                                        >
                                          {docId}
                                        </a>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              </div>
                            )}
                        </div>
                      </div>
                    )}
                      </div>
                    </div>

                    <div className="flex min-h-0 flex-1 flex-col">
                      <label className="mb-1 shrink-0 block text-sm font-semibold text-gray-700">
                        Context sent to model
                      </label>
                      <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words rounded border bg-gray-50 p-2 font-mono text-xs leading-relaxed text-gray-800 [&::-webkit-scrollbar]:w-2.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent">
                        {promptUsedText
                          ? promptUsedText
                          : 'No prompt text reported by the backend for this run.'}
                      </pre>
                    </div>
                  </div>
                );
              })()
            ) : (
              <p className="py-4 text-sm text-gray-500">No run info available.</p>
            )}
            </div>
          </DraggablePanel>
        </>
      )}
    </div>
  );
};

export default PDFExtractionSidebarContent;
