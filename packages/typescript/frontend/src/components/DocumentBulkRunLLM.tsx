import { forwardRef, useImperativeHandle, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Prompt, BulkAnalyzeLLMResponse } from '@docrouter/sdk';
import { Tag } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';
import { toast } from 'react-hot-toast';
import { ChevronRightIcon } from '@heroicons/react/24/outline';
import SingleTagSelector from './SingleTagSelector';

const DEFAULT_PARALLEL_RUNS = 10;
const MIN_PARALLEL_RUNS = 1;
const MAX_PARALLEL_RUNS = 50;
const BULK_LLM_PARALLEL_RUNS_KEY = 'docrouter.bulkLlmParallelRuns';

function clampParallelRuns(value: number): number {
  const n = Math.floor(value);
  if (!Number.isFinite(n)) return DEFAULT_PARALLEL_RUNS;
  return Math.min(MAX_PARALLEL_RUNS, Math.max(MIN_PARALLEL_RUNS, n));
}

function readParallelRunsFromSession(): number {
  if (typeof window === 'undefined') return DEFAULT_PARALLEL_RUNS;
  try {
    const raw = sessionStorage.getItem(BULK_LLM_PARALLEL_RUNS_KEY);
    if (raw === null) return DEFAULT_PARALLEL_RUNS;
    return clampParallelRuns(parseInt(raw, 10));
  } catch {
    return DEFAULT_PARALLEL_RUNS;
  }
}

function persistParallelRunsToSession(value: number): void {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(BULK_LLM_PARALLEL_RUNS_KEY, String(value));
  } catch {
    // ignore quota / private mode
  }
}

type WorkItem = {
  group: PromptExecutionGroup;
  execution: PromptExecution;
};

async function runWithConcurrency(
  items: WorkItem[],
  limit: number,
  worker: (item: WorkItem) => Promise<void>,
  shouldStop: () => boolean,
): Promise<void> {
  if (items.length === 0) return;

  let nextIndex = 0;
  const runWorker = async () => {
    while (true) {
      if (shouldStop()) return;
      const index = nextIndex++;
      if (index >= items.length) return;
      await worker(items[index]);
    }
  };

  const workerCount = Math.min(limit, items.length);
  await Promise.all(Array.from({ length: workerCount }, () => runWorker()));
}

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
    const [parallelRuns, setParallelRuns] = useState(readParallelRunsFromSession);
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
    const isMountedRef = useRef(false);
    const analyzeGenerationRef = useRef(0);
    const onDataChangeRef = useRef(onDataChange);
    onDataChangeRef.current = onDataChange;
    const onProgressRef = useRef(onProgress);
    onProgressRef.current = onProgress;
    const completedExecutionsRef = useRef(0);

    const notifyExecutionProgress = useCallback((processed: number) => {
      queueMicrotask(() => {
        if (isMountedRef.current) {
          onProgressRef.current?.(processed);
        }
      });
    }, []);

    useEffect(() => {
      isMountedRef.current = true;
      return () => {
        isMountedRef.current = false;
        analysisAbortController.current?.abort();
      };
    }, []);

    const handleParallelRunsCommit = useCallback(() => {
      const clamped = clampParallelRuns(parallelRuns);
      setParallelRuns(clamped);
      persistParallelRunsToSession(clamped);
    }, [parallelRuns]);

    const parseMetadataSearch = (searchStr: string): Record<string, string> | undefined => {
      if (!searchStr.trim()) return undefined;
      try {
        const result: Record<string, string> = {};
        for (const rawPair of searchStr.split(',')) {
          const trimmed = rawPair.trim();
          if (!trimmed) continue;

          const equalIndex = trimmed.indexOf('=');
          if (equalIndex === -1) continue;

          const key = trimmed.substring(0, equalIndex).trim();
          const value = trimmed.substring(equalIndex + 1).trim();
          if (key && value) {
            result[key] = value;
          }
        }
        return Object.keys(result).length > 0 ? result : undefined;
      } catch (error) {
        console.error('Error parsing metadata search:', error);
        return undefined;
      }
    };

    const buildDocumentFilters = useCallback(() => {
      const tagFilters = searchParameters.selectedTagFilters.map(tag => tag.id);
      if (selectedTag && !tagFilters.includes(selectedTag.id)) {
        tagFilters.push(selectedTag.id);
      }

      return {
        name_search: searchParameters.searchTerm.trim() || undefined,
        tag_ids: tagFilters.length > 0 ? tagFilters : undefined,
        metadata_search: parseMetadataSearch(searchParameters.metadataSearch.trim()),
      };
    }, [selectedTag, searchParameters.searchTerm, searchParameters.selectedTagFilters, searchParameters.metadataSearch]);

    const analyzeExecutions = useCallback(async () => {
      if (!selectedTag) return;

      const generation = ++analyzeGenerationRef.current;
      analysisAbortController.current?.abort();
      analysisAbortController.current = new AbortController();
      const signal = analysisAbortController.current.signal;

      if (!isMountedRef.current) return;

      setIsAnalyzing(true);
      setIsCancellingAnalysis(false);
      setIsAnalysisCancelled(false);
      setAnalysisProgress(0);
      setTotalAnalysisItems(0);

      try {
        const response = await docRouterOrgApi.bulkAnalyzeLLM({
          tagId: selectedTag.id,
          mode: executionMode,
          documentFilters: buildDocumentFilters(),
        });

        if (
          signal.aborted ||
          !isMountedRef.current ||
          generation !== analyzeGenerationRef.current
        ) {
          return;
        }

        const groups: PromptExecutionGroup[] = response.groups.map((group: BulkAnalyzeLLMResponse['groups'][number]) => {
          const prompt: Prompt = {
            prompt_revid: group.prompt_revid,
            prompt_id: group.prompt_id,
            prompt_version: group.prompt_version,
            name: group.name,
            content: '',
            created_at: '',
            created_by: '',
          };
          const executions: PromptExecution[] = group.executions.map((exec) => ({
            prompt,
            documentId: exec.document_id,
            documentName: exec.document_name,
            status: 'pending' as const,
          }));
          return {
            prompt,
            executions,
            totalExecutions: executions.length,
            completedExecutions: 0,
          };
        });

        setPromptGroups(groups);
        setTotalExecutions(response.total_executions);
        setAnalysisProgress(response.total_executions);
        setTotalAnalysisItems(response.total_executions);
      } catch (error) {
        if (
          signal.aborted ||
          !isMountedRef.current ||
          generation !== analyzeGenerationRef.current
        ) {
          if (signal.aborted && isMountedRef.current) {
            setPromptGroups([]);
            setTotalExecutions(0);
            setIsAnalysisCancelled(true);
          }
          return;
        }
        console.error('Error analyzing executions:', error);
        toast.error('Failed to analyze required executions');
      } finally {
        if (
          isMountedRef.current &&
          generation === analyzeGenerationRef.current
        ) {
          setIsAnalyzing(false);
          setIsCancellingAnalysis(false);
          analysisAbortController.current = null;
        }
      }
    }, [selectedTag, executionMode, buildDocumentFilters, docRouterOrgApi]);

    // Analyze what needs to be executed when tag selection, mode, or search parameters change
    useEffect(() => {
      if (!selectedTag) {
        setPromptGroups([]);
        setTotalExecutions(0);
        return;
      }

      void analyzeExecutions();

      return () => {
        analysisAbortController.current?.abort();
      };
    }, [selectedTag, executionMode, searchParameters.searchTerm, searchParameters.selectedTagFilters, searchParameters.metadataSearch, analyzeExecutions]);

    // Update parent component with data changes (after mount, avoid parent updates during unmount)
    useEffect(() => {
      if (!isMountedRef.current) return;

      onDataChangeRef.current?.({
        selectedTag,
        executionCount: totalExecutions,
        isCancelling,
        isCancelled,
        isCompleted,
        isAnalyzing,
      });
    }, [selectedTag, totalExecutions, isCancelling, isCancelled, isCompleted, isAnalyzing]);

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
      completedExecutionsRef.current = 0;
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
      completedExecutionsRef.current = 0;
      setCompletedExecutions(0);

      const concurrencyLimit = clampParallelRuns(parallelRuns);
      const work: WorkItem[] = promptGroups.flatMap((group) =>
        group.executions.map((execution) => ({ group, execution })),
      );

      const markExecutionStatus = (
        group: PromptExecutionGroup,
        documentId: string,
        update: Partial<PromptExecution> & { status: PromptExecution['status'] },
        incrementGroupCompleted = false,
      ) => {
        setPromptGroups((prev) =>
          prev.map((g) =>
            g.prompt.prompt_revid === group.prompt.prompt_revid
              ? {
                  ...g,
                  executions: g.executions.map((e) =>
                    e.documentId === documentId ? { ...e, ...update } : e,
                  ),
                  completedExecutions: incrementGroupCompleted
                    ? g.completedExecutions + 1
                    : g.completedExecutions,
                }
              : g,
          ),
        );
      };

      const recordProgress = () => {
        completedExecutionsRef.current += 1;
        setCompletedExecutions(completedExecutionsRef.current);
        notifyExecutionProgress(completedExecutionsRef.current);
      };

      try {
        await runWithConcurrency(
          work,
          concurrencyLimit,
          async ({ group, execution }) => {
            if (isCancelledRef.current) {
              markExecutionStatus(group, execution.documentId, { status: 'cancelled' });
              return;
            }

            markExecutionStatus(group, execution.documentId, { status: 'running' });

            try {
              await docRouterOrgApi.runLLM({
                documentId: execution.documentId,
                promptRevId: execution.prompt.prompt_revid,
                force: executionMode === 'all',
              });

              markExecutionStatus(
                group,
                execution.documentId,
                { status: 'completed' },
                true,
              );
              recordProgress();
            } catch (error) {
              console.error(`Error running LLM for document ${execution.documentId}:`, error);
              markExecutionStatus(group, execution.documentId, {
                status: 'error',
                error: error instanceof Error ? error.message : 'Unknown error',
              });
              recordProgress();
            }
          },
          () => isCancelledRef.current,
        );

        if (isCancelledRef.current) {
          toast(
            `LLM execution cancelled - completed ${completedExecutionsRef.current} out of ${totalExecutions} executions`,
          );
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

        {selectedTag && (
          <div className="max-w-xs">
            <label htmlFor="bulk-llm-parallel-runs" className="block text-sm font-medium text-gray-700 mb-1">
              Parallel runs
            </label>
            <input
              id="bulk-llm-parallel-runs"
              type="number"
              min={MIN_PARALLEL_RUNS}
              max={MAX_PARALLEL_RUNS}
              value={Number.isFinite(parallelRuns) ? parallelRuns : ''}
              onChange={(e) => setParallelRuns(e.target.valueAsNumber)}
              onBlur={handleParallelRunsCommit}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleParallelRunsCommit();
              }}
              disabled={disabled || isExecuting || isAnalyzing}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
            <p className="text-xs text-gray-500 mt-1">
              Max parallel LLM requests ({MIN_PARALLEL_RUNS}–{MAX_PARALLEL_RUNS}, default{' '}
              {DEFAULT_PARALLEL_RUNS}).
            </p>
          </div>
        )}

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