import { forwardRef, useImperativeHandle, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Prompt } from '@docrouter/sdk';
import { Document, Tag } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';
import { toast } from 'react-hot-toast';
import { ChevronRightIcon } from '@heroicons/react/24/outline';
import SingleTagSelector from './SingleTagSelector';

// Batch size constant - will be increased to 25 later
const BATCH_SIZE = 10;

interface DocumentBulkRunLLMProps {
  organizationId: string;
  searchParameters: {
    searchTerm: string;
    selectedTagFilters: Tag[];
    metadataSearch: string;
    paginationModel: { page: number; pageSize: number };
  };
  totalDocuments: number;
  disabled?: boolean;
  onProgress?: (processed: number) => void;
  onComplete?: () => void;
  availableTags: Tag[];
  onDataChange?: (data: {
    selectedTag: Tag | null;
    executionCount: number;
    isCancelling: boolean;
    isCancelled: boolean;
    isCompleted: boolean;
    isAnalyzing: boolean;
  }) => void;
}

interface PromptExecution {
  prompt: Prompt;
  documentId: string;
  documentName: string;
  status: 'pending' | 'running' | 'completed' | 'error' | 'cancelled';
  error?: string;
}

interface PromptExecutionGroup {
  prompt: Prompt;
  executions: PromptExecution[];
  totalExecutions: number;
  completedExecutions: number;
}

export interface DocumentBulkRunLLMRef {
  executeRunLLM: () => Promise<void>;
  cancelRunLLM: () => void;
  resetRunLLM: () => void;
}

type ExecutionMode = 'all' | 'missing' | 'outdated';

export const DocumentBulkRunLLM = forwardRef<DocumentBulkRunLLMRef, DocumentBulkRunLLMProps>(
  ({ organizationId, searchParameters, disabled, onProgress, onComplete, availableTags, onDataChange }, ref) => {
    const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
    const [selectedTag, setSelectedTag] = useState<Tag | null>(null);
    const [executionMode, setExecutionMode] = useState<ExecutionMode>('outdated');
    const [promptGroups, setPromptGroups] = useState<PromptExecutionGroup[]>([]);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isExecuting, setIsExecuting] = useState(false);
    const [isCancelling, setIsCancelling] = useState(false);
    const [isCancelled, setIsCancelled] = useState(false);
    const [isCompleted, setIsCompleted] = useState(false);
    const [totalExecutions, setTotalExecutions] = useState(0);
    const [completedExecutions, setCompletedExecutions] = useState(0);

    // Analysis progress tracking
    const [analysisProgress, setAnalysisProgress] = useState(0);
    const [totalAnalysisItems, setTotalAnalysisItems] = useState(0);
    const [isCancellingAnalysis, setIsCancellingAnalysis] = useState(false);
    const [isAnalysisCancelled, setIsAnalysisCancelled] = useState(false);

    // Use ref for immediate cancellation without waiting for state updates
    const isCancelledRef = useRef(false);
    const analysisAbortController = useRef<AbortController | null>(null);

    // Parse and URL-encode metadata search to handle special characters
    const parseAndEncodeMetadataSearch = (searchStr: string): string | null => {
      try {
        const pairs: string[] = [];
        const rawPairs = searchStr.split(',');

        for (const rawPair of rawPairs) {
          const trimmed = rawPair.trim();
          if (!trimmed) continue;

          const equalIndex = trimmed.indexOf('=');
          if (equalIndex === -1) continue;

          const key = trimmed.substring(0, equalIndex).trim();
          const value = trimmed.substring(equalIndex + 1).trim();

          if (key && value) {
            const encodedKey = encodeURIComponent(key);
            const encodedValue = encodeURIComponent(value);
            pairs.push(`${encodedKey}=${encodedValue}`);
          }
        }

        return pairs.length > 0 ? pairs.join(',') : null;
      } catch (error) {
        console.error('Error parsing metadata search:', error);
        return null;
      }
    };

    // Helper function to fetch all prompts with pagination
    const fetchAllPrompts = useCallback(async () => {
      const allPrompts: Prompt[] = [];
      let skip = 0;
      const limit = 1000; // API maximum

      while (true) {
        const response = await docRouterOrgApi.listPrompts({
          tag_ids: selectedTag!.id,
          skip,
          limit
        });

        allPrompts.push(...response.prompts);

        // If we got less than the limit, we've reached the end
        if (response.prompts.length < limit) {
          break;
        }

        skip += limit;
      }

      return allPrompts;
    }, [selectedTag, docRouterOrgApi]);

    // Helper function to fetch all documents with pagination
    const fetchAllDocuments = useCallback(async () => {
      const allDocuments: Document[] = [];
      let skip = 0;
      const limit = 1000; // API maximum

      // Combine existing tag filters with the selected tag for LLM operations
      const tagFilters = [...searchParameters.selectedTagFilters.map(tag => tag.id)];
      if (selectedTag && !tagFilters.includes(selectedTag.id)) {
        tagFilters.push(selectedTag.id);
      }

      while (true) {
        const response = await docRouterOrgApi.listDocuments({
          skip,
          limit,
          nameSearch: searchParameters.searchTerm.trim() || undefined,
          tagIds: tagFilters.length > 0 ? tagFilters.join(',') : undefined,
          metadataSearch: searchParameters.metadataSearch.trim()
            ? parseAndEncodeMetadataSearch(searchParameters.metadataSearch.trim()) || undefined
            : undefined,
        });

        allDocuments.push(...response.documents);

        // If we got less than the limit, we've reached the end
        if (response.documents.length < limit) {
          break;
        }

        skip += limit;
      }

      return allDocuments;
    }, [selectedTag, searchParameters.searchTerm, searchParameters.selectedTagFilters, searchParameters.metadataSearch, docRouterOrgApi]);

    const analyzeExecutions = useCallback(async () => {
      if (!selectedTag) return;

      // Create new abort controller for this analysis
      analysisAbortController.current = new AbortController();
      const signal = analysisAbortController.current.signal;

      setIsAnalyzing(true);
      setIsCancellingAnalysis(false);
      setIsAnalysisCancelled(false);
      setAnalysisProgress(0);
      setTotalAnalysisItems(0);

      try {
        // Get all prompts for the selected tag using pagination
        const allPrompts = await fetchAllPrompts();

        if (signal.aborted) return;

        if (allPrompts.length === 0) {
          toast('No prompts found for the selected tag');
          setPromptGroups([]);
          setTotalExecutions(0);
          return;
        }

        // Group prompts by prompt_id and keep only the latest version of each
        const promptGroups = allPrompts.reduce((groups: Record<string, Prompt>, prompt) => {
          const existingPrompt = groups[prompt.prompt_id];
          if (!existingPrompt || prompt.prompt_version > existingPrompt.prompt_version) {
            groups[prompt.prompt_id] = prompt;
          }
          return groups;
        }, {});

        const latestPrompts = Object.values(promptGroups);

        // Get all documents that match the current filters using pagination
        const allDocuments = await fetchAllDocuments();

        if (signal.aborted) return;

        if (allDocuments.length === 0) {
          toast('No documents match the current filters');
          setPromptGroups([]);
          setTotalExecutions(0);
          return;
        }

        // Calculate total analysis items for progress tracking
        const totalAnalysisOperations = latestPrompts.length * allDocuments.length;
        setTotalAnalysisItems(totalAnalysisOperations);

        // For each prompt, check which documents need LLM execution with batching
        const groups: PromptExecutionGroup[] = [];
        let totalExecs = 0;
        let completedAnalysisItems = 0;

        for (const prompt of latestPrompts) {
          if (signal.aborted) return;

          const executions: PromptExecution[] = [];

          // Process documents in batches to improve performance
          for (let i = 0; i < allDocuments.length; i += BATCH_SIZE) {
            if (signal.aborted) return;

            const batch = allDocuments.slice(i, i + BATCH_SIZE);

            // Process batch in parallel
            const batchResults = await Promise.all(
              batch.map(async (document) => {
                if (signal.aborted) return null;

                let needsExecution = false;

                if (executionMode === 'all') {
                  // Always run on all documents
                  needsExecution = true;
                } else if (executionMode === 'missing') {
                  // Only run if no result exists for any version of this prompt
                  try {
                    await docRouterOrgApi.getLLMResult({
                      documentId: document.id,
                      promptRevId: prompt.prompt_revid,
                      fallback: true
                    });
                    // If we get here, some result exists - skip execution
                    needsExecution = false;
                  } catch {
                    // No result exists - needs execution
                    needsExecution = true;
                  }
                } else if (executionMode === 'outdated') {
                  // Run if no result exists OR if result exists but for older version
                  try {
                    const existingResult = await docRouterOrgApi.getLLMResult({
                      documentId: document.id,
                      promptRevId: prompt.prompt_revid,
                      fallback: true
                    });
                    // Result exists - check if it's for the latest version
                    needsExecution = existingResult.prompt_version < prompt.prompt_version;
                  } catch {
                    // No result exists - needs execution
                    needsExecution = true;
                  }
                }

                completedAnalysisItems++;
                setAnalysisProgress(completedAnalysisItems);

                return needsExecution ? {
                  prompt,
                  documentId: document.id,
                  documentName: document.document_name,
                  status: 'pending' as const
                } : null;
              })
            );

            // Filter out null results and add to executions
            executions.push(...batchResults.filter(result => result !== null) as PromptExecution[]);
          }

          if (executions.length > 0) {
            groups.push({
              prompt,
              executions,
              totalExecutions: executions.length,
              completedExecutions: 0
            });
            totalExecs += executions.length;
          }
        }

        if (!signal.aborted) {
          setPromptGroups(groups);
          setTotalExecutions(totalExecs);
        }

      } catch (error) {
        if (signal.aborted) {
          // Analysis was cancelled
          setPromptGroups([]);
          setTotalExecutions(0);
          setIsAnalysisCancelled(true);
        } else {
          console.error('Error analyzing executions:', error);
          toast.error('Failed to analyze required executions');
        }
      } finally {
        setIsAnalyzing(false);
        setIsCancellingAnalysis(false);
        analysisAbortController.current = null;
      }
    }, [selectedTag, executionMode, fetchAllPrompts, fetchAllDocuments, docRouterOrgApi]);

    // Analyze what needs to be executed when tag selection, mode, or search parameters change
    useEffect(() => {
      if (selectedTag) {
        analyzeExecutions();
      } else {
        setPromptGroups([]);
        setTotalExecutions(0);
      }
    }, [selectedTag, executionMode, searchParameters.searchTerm, searchParameters.selectedTagFilters, searchParameters.metadataSearch, analyzeExecutions]);

    // Update parent component with data changes
    useEffect(() => {
      if (onDataChange) {
        onDataChange({
          selectedTag,
          executionCount: totalExecutions,
          isCancelling,
          isCancelled,
          isCompleted,
          isAnalyzing
        });
      }
    }, [selectedTag, totalExecutions, isCancelling, isCancelled, isCompleted, isAnalyzing, onDataChange]);

    const cancelAnalysis = () => {
      setIsCancellingAnalysis(true);
      if (analysisAbortController.current) {
        analysisAbortController.current.abort();
      }

      // Clear execution details
      setPromptGroups([]);
      setTotalExecutions(0);
      setAnalysisProgress(0);
      setTotalAnalysisItems(0);
      setIsAnalysisCancelled(true);

      toast('Analysis cancelled');
    };

    const cancelRunLLM = () => {
      // Set ref immediately for synchronous cancellation check
      isCancelledRef.current = true;
      setIsCancelling(true);
      setIsCancelled(true);

      // Mark all pending executions as cancelled
      setPromptGroups(prev => prev.map(group => ({
        ...group,
        executions: group.executions.map(exec =>
          exec.status === 'pending'
            ? { ...exec, status: 'cancelled' as const }
            : exec
        )
      })));

      toast('LLM execution cancelled - remaining operations will be skipped');
    };

    const resetRunLLM = () => {
      // Reset ref as well
      isCancelledRef.current = false;
      setIsCompleted(false);
      setIsCancelled(false);
      setIsCancelling(false);
      setCompletedExecutions(0);
      setPromptGroups([]);
      setTotalExecutions(0);

      // Re-analyze executions for the current tag and mode
      if (selectedTag) {
        analyzeExecutions();
      }

      toast('LLM run state reset - ready for new execution');
    };

    const executeRunLLM = async () => {
      if (!selectedTag || promptGroups.length === 0) {
        toast('Please select a tag and ensure there are executions to run');
        return;
      }

      if (isAnalyzing) {
        toast('Please wait for analysis to complete before starting execution');
        return;
      }

      // Reset cancellation ref at start of execution
      isCancelledRef.current = false;
      setIsExecuting(true);
      setIsCancelling(false);
      setIsCancelled(false);
      setIsCompleted(false);
      setCompletedExecutions(0);

      try {
        // Process all executions in batches
        groupLoop: for (const group of promptGroups) {
          const executions = [...group.executions];

          // Process in batches of BATCH_SIZE
          for (let i = 0; i < executions.length; i += BATCH_SIZE) {
            // Check for cancellation before each batch using ref for immediate response
            if (isCancelledRef.current) {
              break groupLoop;
            }

            const batch = executions.slice(i, i + BATCH_SIZE);

            // Execute batch in parallel
            const batchPromises = batch.map(async (execution) => {
              try {
                // Check if cancelled before starting this specific execution using ref
                if (isCancelledRef.current) {
                  // Mark as cancelled instead of running
                  setPromptGroups(prev => prev.map(g =>
                    g.prompt.prompt_revid === group.prompt.prompt_revid
                      ? {
                          ...g,
                          executions: g.executions.map(e =>
                            e.documentId === execution.documentId
                              ? { ...e, status: 'cancelled' as const }
                              : e
                          )
                        }
                      : g
                  ));
                  return; // Don't execute the LLM call
                }

                // Update status to running
                setPromptGroups(prev => prev.map(g =>
                  g.prompt.prompt_revid === group.prompt.prompt_revid
                    ? {
                        ...g,
                        executions: g.executions.map(e =>
                          e.documentId === execution.documentId
                            ? { ...e, status: 'running' as const }
                            : e
                        )
                      }
                    : g
                ));

                // Run the LLM (force=true for 'all' mode to rerun existing results)
                await docRouterOrgApi.runLLM({
                  documentId: execution.documentId,
                  promptRevId: execution.prompt.prompt_revid,
                  force: executionMode === 'all'
                });

                // Update status to completed
                setPromptGroups(prev => prev.map(g =>
                  g.prompt.prompt_revid === group.prompt.prompt_revid
                    ? {
                        ...g,
                        executions: g.executions.map(e =>
                          e.documentId === execution.documentId
                            ? { ...e, status: 'completed' as const }
                            : e
                        ),
                        completedExecutions: g.completedExecutions + 1
                      }
                    : g
                ));

                // Update progress
                setCompletedExecutions(prev => {
                  const newCompleted = prev + 1;
                  if (onProgress) {
                    onProgress(newCompleted);
                  }
                  return newCompleted;
                });

              } catch (error) {
                console.error(`Error running LLM for document ${execution.documentId}:`, error);

                // Update status to error
                setPromptGroups(prev => prev.map(g =>
                  g.prompt.prompt_revid === group.prompt.prompt_revid
                    ? {
                        ...g,
                        executions: g.executions.map(e =>
                          e.documentId === execution.documentId
                            ? {
                                ...e,
                                status: 'error' as const,
                                error: error instanceof Error ? error.message : 'Unknown error'
                              }
                            : e
                        )
                      }
                    : g
                ));

                // Still update progress counter for failed executions
                setCompletedExecutions(prev => {
                  const newCompleted = prev + 1;
                  if (onProgress) {
                    onProgress(newCompleted);
                  }
                  return newCompleted;
                });
              }
            });

            // Wait for batch to complete before starting next batch
            await Promise.all(batchPromises);
          }
        }

        if (isCancelledRef.current) {
          toast(`LLM execution cancelled - completed ${completedExecutions} out of ${totalExecutions} executions`);
        } else {
          toast.success(`Completed LLM execution on ${totalExecutions} document-prompt combinations`);
          setIsCompleted(true);
        }

        if (onComplete) {
          onComplete();
        }

      } catch (error) {
        console.error('Error during bulk LLM execution:', error);
        toast.error('Failed to complete bulk LLM execution');
      } finally {
        setIsExecuting(false);
        // Reset cancelling state when execution is fully done
        setIsCancelling(false);
      }
    };

    useImperativeHandle(ref, () => ({
      executeRunLLM,
      cancelRunLLM,
      resetRunLLM
    }));

    const getStatusIcon = (status: string) => {
      switch (status) {
        case 'running':
          return <div className="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />;
        case 'completed':
          return <div className="w-3 h-3 bg-green-500 rounded-full" />;
        case 'error':
          return <div className="w-3 h-3 bg-red-500 rounded-full" />;
        case 'cancelled':
          return <div className="w-3 h-3 bg-orange-500 rounded-full" />;
        default:
          return <div className="w-3 h-3 bg-gray-300 rounded-full" />;
      }
    };

    return (
      <div className="space-y-4">
        {/* Tag Selection and Execution Mode Side by Side */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Tag Selection */}
          <div>
            <SingleTagSelector
              availableTags={availableTags}
              selectedTag={selectedTag}
              onChange={setSelectedTag}
              disabled={disabled || isExecuting}
              placeholder="Select a tag for LLM operations..."
              label="Select Tag for LLM Operations"
            />
          </div>

          {/* Execution Mode Selection */}
          {selectedTag && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Execution Strategy
              </label>
              <div className="space-y-2">
                <div className="flex items-start">
                  <input
                    id="mode-outdated"
                    name="executionMode"
                    type="radio"
                    value="outdated"
                    checked={executionMode === 'outdated'}
                    onChange={(e) => setExecutionMode(e.target.value as ExecutionMode)}
                    disabled={disabled || isExecuting || isAnalyzing}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 mt-0.5"
                  />
                  <label htmlFor="mode-outdated" className="ml-2 block text-sm text-gray-900">
                    <span className="font-medium">Run when missing or outdated</span>
                    <span className="block text-xs text-gray-500 mt-0.5">
                      Execute only if no result exists or if the prompt version has been updated since last run
                    </span>
                  </label>
                </div>

                <div className="flex items-start">
                  <input
                    id="mode-missing"
                    name="executionMode"
                    type="radio"
                    value="missing"
                    checked={executionMode === 'missing'}
                    onChange={(e) => setExecutionMode(e.target.value as ExecutionMode)}
                    disabled={disabled || isExecuting || isAnalyzing}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 mt-0.5"
                  />
                  <label htmlFor="mode-missing" className="ml-2 block text-sm text-gray-900">
                    <span className="font-medium">Run only when completely missing</span>
                    <span className="block text-xs text-gray-500 mt-0.5">
                      Execute only if no result exists at all for this prompt (ignore version differences)
                    </span>
                  </label>
                </div>

                <div className="flex items-start">
                  <input
                    id="mode-all"
                    name="executionMode"
                    type="radio"
                    value="all"
                    checked={executionMode === 'all'}
                    onChange={(e) => setExecutionMode(e.target.value as ExecutionMode)}
                    disabled={disabled || isExecuting || isAnalyzing}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 mt-0.5"
                  />
                  <label htmlFor="mode-all" className="ml-2 block text-sm text-gray-900">
                    <span className="font-medium">Run on all matching documents</span>
                    <span className="block text-xs text-gray-500 mt-0.5">
                      Execute on every document with this tag, regardless of existing results (will overwrite previous results)
                    </span>
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Analysis Status */}
        {isAnalyzing && (
          <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm font-medium text-blue-900">
                  Analyzing required executions...
                </span>
              </div>
              <button
                onClick={cancelAnalysis}
                disabled={isCancellingAnalysis}
                className="px-3 py-1 text-xs font-medium text-red-700 bg-red-100 border border-red-300 rounded hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isCancellingAnalysis ? 'Cancelling...' : 'Cancel'}
              </button>
            </div>
            {totalAnalysisItems > 0 && (
              <div>
                <div className="flex items-center justify-between text-xs text-blue-700 mb-1">
                  <span>Progress</span>
                  <span>{analysisProgress} / {totalAnalysisItems}</span>
                </div>
                <div className="w-full bg-blue-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${totalAnalysisItems > 0 ? (analysisProgress / totalAnalysisItems) * 100 : 0}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Execution Summary */}
        {selectedTag && !isAnalyzing && (
          <div className="bg-gray-50 rounded-md p-3">
            <div className="text-sm text-gray-700">
              <div className="flex items-center justify-between">
                <span className="font-medium">Tag: {selectedTag.name}</span>
                <span className="text-gray-500">
                  {totalExecutions} executions needed
                </span>
              </div>
              {isExecuting && (
                <div className="mt-2">
                  <div className="flex items-center justify-between text-xs">
                    <span>Progress</span>
                    <span>{completedExecutions} / {totalExecutions}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${totalExecutions > 0 ? (completedExecutions / totalExecutions) * 100 : 0}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Prompt Groups */}
        {promptGroups.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-gray-900">Execution Details</h4>
            <div className="max-h-64 overflow-y-auto space-y-2">
              {promptGroups.map((group) => (
                <div key={group.prompt.prompt_revid} className="border border-gray-200 rounded-md">
                  <div className="bg-gray-50 px-3 py-2 border-b border-gray-200">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ChevronRightIcon className="h-4 w-4 text-gray-400" />
                        <span className="font-medium text-sm text-gray-900">
                          {group.prompt.name}
                        </span>
                        <span className="text-xs text-gray-500">
                          v{group.prompt.prompt_version}
                        </span>
                      </div>
                      <span className="text-xs text-gray-500">
                        {group.completedExecutions} / {group.totalExecutions}
                      </span>
                    </div>
                  </div>
                  <div className="p-3 space-y-1 max-h-32 overflow-y-auto">
                    {group.executions.map((execution) => (
                      <div key={`${execution.documentId}`} className="flex items-center justify-between text-xs">
                        <span className="text-gray-700 truncate max-w-[200px]">
                          {execution.documentName}
                        </span>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {getStatusIcon(execution.status)}
                          <span className={`capitalize ${
                            execution.status === 'completed' ? 'text-green-600' :
                            execution.status === 'error' ? 'text-red-600' :
                            execution.status === 'running' ? 'text-blue-600' :
                            execution.status === 'cancelled' ? 'text-orange-600' :
                            'text-gray-500'
                          }`}>
                            {execution.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Analysis cancelled or no executions needed */}
        {selectedTag && !isAnalyzing && promptGroups.length === 0 && totalExecutions === 0 && (
          <div className="text-sm text-center py-4">
            {isAnalysisCancelled ? (
              <span className="text-orange-600">Analysis Cancelled</span>
            ) : (
              <span className="text-gray-500">All documents already have the latest prompt results for this tag.</span>
            )}
          </div>
        )}
      </div>
    );
  }
);

DocumentBulkRunLLM.displayName = 'DocumentBulkRunLLM';