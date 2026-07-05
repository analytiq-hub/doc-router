import {
  forwardRef,
  useImperativeHandle,
  useState,
  useEffect,
  useCallback,
  useRef,
  useMemo,
} from 'react';
import type { BulkAnalyzeFlowsResponse, FlowListItem, Tag } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';
import { pollFlowRerunUntilDone } from '@/utils/flowRerunPoll';
import {
  persistBulkFlowRerunModeToSession,
  readBulkFlowRerunModeFromSession,
  type BulkFlowRerunMode,
} from '@/utils/bulkFlowRerunMode';
import { toast } from 'react-hot-toast';
import Link from 'next/link';
import { ChevronRightIcon } from '@heroicons/react/24/outline';
import SingleTagSelector from './SingleTagSelector';

const DEFAULT_PARALLEL_RUNS = 2;
const MIN_PARALLEL_RUNS = 1;
const MAX_PARALLEL_RUNS = 50;
const BULK_FLOW_PARALLEL_RUNS_KEY = 'docrouter.bulkFlowParallelRuns';

function clampParallelRuns(value: number): number {
  const n = Math.floor(value);
  if (!Number.isFinite(n)) return DEFAULT_PARALLEL_RUNS;
  return Math.min(MAX_PARALLEL_RUNS, Math.max(MIN_PARALLEL_RUNS, n));
}

function readParallelRunsFromSession(): number {
  if (typeof window === 'undefined') return DEFAULT_PARALLEL_RUNS;
  try {
    const raw = sessionStorage.getItem(BULK_FLOW_PARALLEL_RUNS_KEY);
    if (raw === null) return DEFAULT_PARALLEL_RUNS;
    return clampParallelRuns(parseInt(raw, 10));
  } catch {
    return DEFAULT_PARALLEL_RUNS;
  }
}

function persistParallelRunsToSession(value: number): void {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(BULK_FLOW_PARALLEL_RUNS_KEY, String(value));
  } catch {
    // ignore
  }
}

type ExecutionMode = 'all' | 'missing' | 'outdated';

interface FlowExecution {
  flowId: string;
  flowName: string;
  flowVersion: number;
  documentId: string;
  documentName: string;
  reason?: string;
  status: 'pending' | 'running' | 'completed' | 'error' | 'cancelled';
  error?: string;
}

interface FlowExecutionGroup {
  flowId: string;
  flowName: string;
  flowVersion: number;
  executions: FlowExecution[];
  totalExecutions: number;
  completedExecutions: number;
}

type WorkItem = {
  group: FlowExecutionGroup;
  execution: FlowExecution;
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

interface DocumentBulkRunFlowsProps {
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
    selectedFlowIds: string[];
    executionCount: number;
    isCancelling: boolean;
    isCancelled: boolean;
    isCompleted: boolean;
    isAnalyzing: boolean;
  }) => void;
}

export interface DocumentBulkRunFlowsRef {
  executeRunFlows: () => Promise<void>;
  cancelRunFlows: () => void;
  cancelAnalysis: (options?: { notify?: boolean }) => void;
  resetRunFlows: () => void;
}

export const DocumentBulkRunFlows = forwardRef<DocumentBulkRunFlowsRef, DocumentBulkRunFlowsProps>(
  ({ organizationId, searchParameters, disabled, onProgress, onComplete, availableTags, onDataChange }, ref) => {
    const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
    const [selectedTag, setSelectedTag] = useState<Tag | null>(null);
    const [selectedFlowIds, setSelectedFlowIds] = useState<string[]>([]);
    const [orgFlows, setOrgFlows] = useState<FlowListItem[]>([]);
    const [flowsLoading, setFlowsLoading] = useState(false);
    const [executionMode, setExecutionMode] = useState<ExecutionMode>('outdated');
    const [rerunMode, setRerunMode] = useState<BulkFlowRerunMode>(readBulkFlowRerunModeFromSession);
    const [parallelRuns, setParallelRuns] = useState(readParallelRunsFromSession);
    const [flowGroups, setFlowGroups] = useState<FlowExecutionGroup[]>([]);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isExecuting, setIsExecuting] = useState(false);
    const [isCancelling, setIsCancelling] = useState(false);
    const [isCancelled, setIsCancelled] = useState(false);
    const [isCompleted, setIsCompleted] = useState(false);
    const [totalExecutions, setTotalExecutions] = useState(0);
    const [completedExecutions, setCompletedExecutions] = useState(0);
    const [executionFailureCount, setExecutionFailureCount] = useState(0);
    const [isCancellingAnalysis, setIsCancellingAnalysis] = useState(false);
    const [isAnalysisCancelled, setIsAnalysisCancelled] = useState(false);

    const isCancelledRef = useRef(false);
    const analysisAbortController = useRef<AbortController | null>(null);
    const isMountedRef = useRef(false);
    const analyzeGenerationRef = useRef(0);
    const onDataChangeRef = useRef(onDataChange);
    onDataChangeRef.current = onDataChange;
    const onProgressRef = useRef(onProgress);
    onProgressRef.current = onProgress;
    const onCompleteRef = useRef(onComplete);
    onCompleteRef.current = onComplete;
    const completedExecutionsRef = useRef(0);

    const hasDiscoveryInput = selectedTag !== null || selectedFlowIds.length > 0;

    const activeFlows = useMemo(
      () => orgFlows.filter((item) => item.flow.active),
      [orgFlows],
    );

    const notifyExecutionProgress = useCallback((processed: number) => {
      queueMicrotask(() => {
        if (isMountedRef.current) {
          onProgressRef.current?.(processed);
        }
      });
    }, []);

    const notifyComplete = useCallback(() => {
      queueMicrotask(() => {
        if (isMountedRef.current) {
          onCompleteRef.current?.();
        }
      });
    }, []);

    useEffect(() => {
      isMountedRef.current = true;
      return () => {
        isMountedRef.current = false;
        isCancelledRef.current = true;
        analysisAbortController.current?.abort();
      };
    }, []);

    useEffect(() => {
      let cancelled = false;
      setFlowsLoading(true);
      void docRouterOrgApi
        .listFlows({ limit: 200 })
        .then((res) => {
          if (!cancelled) setOrgFlows(res.items);
        })
        .catch((err) => {
          console.error('Failed to load flows:', err);
        })
        .finally(() => {
          if (!cancelled) setFlowsLoading(false);
        });
      return () => {
        cancelled = true;
      };
    }, [docRouterOrgApi]);

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
          if (key && value) result[key] = value;
        }
        return Object.keys(result).length > 0 ? result : undefined;
      } catch {
        return undefined;
      }
    };

    const buildDocumentFilters = useCallback(() => {
      const tagFilters = searchParameters.selectedTagFilters.map((tag) => tag.id);
      if (selectedTag && !tagFilters.includes(selectedTag.id)) {
        tagFilters.push(selectedTag.id);
      }
      return {
        name_search: searchParameters.searchTerm.trim() || undefined,
        tag_ids: tagFilters.length > 0 ? tagFilters : undefined,
        metadata_search: parseMetadataSearch(searchParameters.metadataSearch.trim()),
      };
    }, [
      selectedTag,
      searchParameters.searchTerm,
      searchParameters.selectedTagFilters,
      searchParameters.metadataSearch,
    ]);

    const toggleFlowSelection = (flowId: string) => {
      setSelectedFlowIds((prev) =>
        prev.includes(flowId) ? prev.filter((id) => id !== flowId) : [...prev, flowId],
      );
    };

    const analyzeExecutions = useCallback(async () => {
      if (!hasDiscoveryInput) return;

      const generation = ++analyzeGenerationRef.current;
      isCancelledRef.current = false;
      analysisAbortController.current?.abort();
      analysisAbortController.current = new AbortController();
      const signal = analysisAbortController.current.signal;

      if (!isMountedRef.current) return;

      setIsAnalyzing(true);
      setIsCancellingAnalysis(false);
      setIsAnalysisCancelled(false);

      try {
        const response: BulkAnalyzeFlowsResponse = await docRouterOrgApi.bulkAnalyzeFlows({
          tagId: selectedTag?.id,
          flowIds: selectedFlowIds.length > 0 ? selectedFlowIds : undefined,
          mode: executionMode,
          documentFilters: buildDocumentFilters(),
        });

        if (signal.aborted || !isMountedRef.current || generation !== analyzeGenerationRef.current) {
          return;
        }

        const groups: FlowExecutionGroup[] = response.groups.map((group) => {
          const executions: FlowExecution[] = group.executions.map((exec) => ({
            flowId: group.flow_id,
            flowName: group.flow_name,
            flowVersion: group.flow_version,
            documentId: exec.document_id,
            documentName: exec.document_name,
            reason: exec.reason,
            status: 'pending' as const,
          }));
          return {
            flowId: group.flow_id,
            flowName: group.flow_name,
            flowVersion: group.flow_version,
            executions,
            totalExecutions: executions.length,
            completedExecutions: 0,
          };
        });

        setFlowGroups(groups);
        setTotalExecutions(response.total_executions);
      } catch (error) {
        if (signal.aborted || !isMountedRef.current || generation !== analyzeGenerationRef.current) {
          if (signal.aborted && isMountedRef.current) {
            setFlowGroups([]);
            setTotalExecutions(0);
            setIsAnalysisCancelled(true);
          }
          return;
        }
        console.error('Error analyzing flow executions:', error);
        toast.error('Failed to analyze required flow executions');
      } finally {
        if (isMountedRef.current && generation === analyzeGenerationRef.current) {
          setIsAnalyzing(false);
          setIsCancellingAnalysis(false);
          analysisAbortController.current = null;
        }
      }
    }, [
      hasDiscoveryInput,
      selectedTag,
      selectedFlowIds,
      executionMode,
      buildDocumentFilters,
      docRouterOrgApi,
    ]);

    useEffect(() => {
      if (!hasDiscoveryInput) {
        setFlowGroups([]);
        setTotalExecutions(0);
        return;
      }
      // Keep execution results visible after a run (onComplete refreshes parent state).
      if (isExecuting || isCompleted) {
        return;
      }
      void analyzeExecutions();
      return () => {
        analysisAbortController.current?.abort();
      };
    }, [
      hasDiscoveryInput,
      selectedTag,
      selectedFlowIds,
      executionMode,
      searchParameters.searchTerm,
      searchParameters.selectedTagFilters,
      searchParameters.metadataSearch,
      analyzeExecutions,
      isExecuting,
      isCompleted,
    ]);

    useEffect(() => {
      if (!isMountedRef.current) return;
      onDataChangeRef.current?.({
        selectedTag,
        selectedFlowIds,
        executionCount: totalExecutions,
        isCancelling,
        isCancelled,
        isCompleted,
        isAnalyzing,
      });
    }, [selectedTag, selectedFlowIds, totalExecutions, isCancelling, isCancelled, isCompleted, isAnalyzing]);

    const cancelAnalysis = (options?: { notify?: boolean }) => {
      isCancelledRef.current = true;
      setIsCancellingAnalysis(true);
      setIsAnalyzing(false);
      analysisAbortController.current?.abort();
      setFlowGroups([]);
      setTotalExecutions(0);
      setIsAnalysisCancelled(true);
      setIsCancellingAnalysis(false);
      if (options?.notify !== false) toast('Analysis cancelled');
    };

    const cancelRunFlows = () => {
      isCancelledRef.current = true;
      setIsCancelling(true);
      setIsCancelled(true);
      setFlowGroups((prev) =>
        prev.map((group) => ({
          ...group,
          executions: group.executions.map((exec) =>
            exec.status === 'pending' ? { ...exec, status: 'cancelled' as const } : exec,
          ),
        })),
      );
      toast('Flow execution cancelled - remaining operations will be skipped');
    };

    const resetRunFlows = () => {
      isCancelledRef.current = false;
      setIsCompleted(false);
      setIsCancelled(false);
      setIsCancelling(false);
      completedExecutionsRef.current = 0;
      setCompletedExecutions(0);
      setExecutionFailureCount(0);
      setFlowGroups([]);
      setTotalExecutions(0);
      if (hasDiscoveryInput) void analyzeExecutions();
      toast('Flow run state reset - ready for new execution');
    };

    const executeRunFlows = async () => {
      if (!hasDiscoveryInput || flowGroups.length === 0) {
        toast('Select a tag and/or flows and ensure there are executions to run');
        return;
      }
      if (isAnalyzing) {
        toast('Please wait for analysis to complete before starting execution');
        return;
      }

      isCancelledRef.current = false;
      setIsExecuting(true);
      setIsCancelling(false);
      setIsCancelled(false);
      setIsCompleted(false);
      completedExecutionsRef.current = 0;
      setCompletedExecutions(0);
      setExecutionFailureCount(0);

      const concurrencyLimit = clampParallelRuns(parallelRuns);
      const work: WorkItem[] = flowGroups.flatMap((group) =>
        group.executions.map((execution) => ({ group, execution })),
      );

      const markExecutionStatus = (
        group: FlowExecutionGroup,
        documentId: string,
        update: Partial<FlowExecution> & { status: FlowExecution['status'] },
        incrementGroupCompleted = false,
      ) => {
        setFlowGroups((prev) =>
          prev.map((g) =>
            g.flowId === group.flowId
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

      let failureCount = 0;

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
              const { execution_id: execId } = await docRouterOrgApi.rerunFlowForDocument(
                execution.flowId,
                execution.documentId,
                { mode: rerunMode },
              );
              if (!execId?.trim() || isCancelledRef.current) {
                markExecutionStatus(group, execution.documentId, {
                  status: 'error',
                  error: 'No execution id returned',
                });
                recordProgress();
                return;
              }

              await pollFlowRerunUntilDone(docRouterOrgApi, {
                flowId: execution.flowId,
                documentId: execution.documentId,
                execId,
                shouldContinue: () => !isCancelledRef.current,
              });

              markExecutionStatus(group, execution.documentId, { status: 'completed' }, true);
              recordProgress();
            } catch (error) {
              const message = error instanceof Error ? error.message : 'Unknown error';
              failureCount += 1;
              markExecutionStatus(group, execution.documentId, {
                status: 'error',
                error: message,
              });
              recordProgress();
            }
          },
          () => isCancelledRef.current,
        );

        if (isCancelledRef.current) {
          toast(
            `Flow execution cancelled - completed ${completedExecutionsRef.current} out of ${totalExecutions} executions`,
          );
        } else if (failureCount > 0) {
          setExecutionFailureCount(failureCount);
          toast.error(
            `Finished with ${failureCount} error${failureCount === 1 ? '' : 's'} — see execution details`,
          );
          setIsCompleted(true);
        } else {
          toast.success(`Completed flow execution on ${totalExecutions} document-flow combinations`);
          setIsCompleted(true);
        }

        notifyComplete();
      } catch (error) {
        console.error('Error during bulk flow execution:', error);
        toast.error('Failed to complete bulk flow execution');
      } finally {
        setIsExecuting(false);
        setIsCancelling(false);
      }
    };

    useImperativeHandle(ref, () => ({
      executeRunFlows,
      cancelRunFlows,
      cancelAnalysis,
      resetRunFlows,
    }));

    const getStatusIcon = (status: string) => {
      switch (status) {
        case 'running':
          return (
            <div className="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          );
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
        <p className="text-xs text-gray-500">
          Only active flows with result capture enabled. For flows on LLM events, run Bulk LLM first when needed.
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <SingleTagSelector
              availableTags={availableTags}
              selectedTag={selectedTag}
              onChange={setSelectedTag}
              disabled={disabled || isExecuting}
              placeholder="Optional anchor tag..."
              label="Anchor tag (optional)"
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Flows {selectedTag ? '(intersects with anchor tag when both set)' : ''}
              </label>
              {flowsLoading ? (
                <p className="text-sm text-gray-500">Loading flows…</p>
              ) : activeFlows.length === 0 ? (
                <p className="text-sm text-gray-500">No active flows in this organization.</p>
              ) : (
                <div className="max-h-40 overflow-y-auto border border-gray-200 rounded-md divide-y divide-gray-100">
                  {activeFlows.map((item) => (
                    <label
                      key={item.flow.flow_id}
                      className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedFlowIds.includes(item.flow.flow_id)}
                        onChange={() => toggleFlowSelection(item.flow.flow_id)}
                        disabled={disabled || isExecuting || isAnalyzing}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="text-gray-900 truncate">{item.flow.name}</span>
                      <span className="text-xs text-gray-400 ml-auto">
                        v{item.latest_revision?.flow_version ?? item.flow.flow_version}
                      </span>
                    </label>
                  ))}
                </div>
              )}
              <p className="text-xs text-gray-500 mt-1">
                Pick flows and/or an anchor tag to discover flows from triggers.
              </p>
            </div>
          </div>

          {hasDiscoveryInput && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">Execution Strategy</label>
              <div className="space-y-2">
                {(
                  [
                    {
                      id: 'flows-mode-outdated',
                      value: 'outdated' as const,
                      title: 'Run when missing or outdated',
                      hint: 'Re-run when no captured result exists, or when the flow revision is newer than the stored result',
                    },
                    {
                      id: 'flows-mode-missing',
                      value: 'missing' as const,
                      title: 'Run only when completely missing',
                      hint: 'Re-run only when no flow_results row exists (ignore version differences)',
                    },
                    {
                      id: 'flows-mode-all',
                      value: 'all' as const,
                      title: 'Run on all matching documents',
                      hint: 'Force re-run every eligible document-flow pair',
                    },
                  ] as const
                ).map((opt) => (
                  <div key={opt.id} className="flex items-start">
                    <input
                      id={opt.id}
                      name="flowExecutionMode"
                      type="radio"
                      value={opt.value}
                      checked={executionMode === opt.value}
                      onChange={(e) => setExecutionMode(e.target.value as ExecutionMode)}
                      disabled={disabled || isExecuting || isAnalyzing}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 mt-0.5"
                    />
                    <label htmlFor={opt.id} className="ml-2 block text-sm text-gray-900">
                      <span className="font-medium">{opt.title}</span>
                      <span className="block text-xs text-gray-500 mt-0.5">{opt.hint}</span>
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}

          {hasDiscoveryInput && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">Rerun mode</label>
              <div className="space-y-2">
                {(
                  [
                    {
                      id: 'flows-rerun-force',
                      value: 'force' as const,
                      title: 'Force rerun',
                      hint: 'Start a new execution from scratch',
                    },
                    {
                      id: 'flows-rerun-incomplete',
                      value: 'incomplete_only' as const,
                      title: 'Rerun incomplete only',
                      hint: 'Resume the latest partial or stopped batch run and skip completed items',
                    },
                  ] as const
                ).map((opt) => (
                  <div key={opt.id} className="flex items-start">
                    <input
                      id={opt.id}
                      name="flowRerunMode"
                      type="radio"
                      value={opt.value}
                      checked={rerunMode === opt.value}
                      onChange={(e) => {
                        const next = e.target.value as BulkFlowRerunMode;
                        setRerunMode(next);
                        persistBulkFlowRerunModeToSession(next);
                      }}
                      disabled={disabled || isExecuting || isAnalyzing}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 mt-0.5"
                    />
                    <label htmlFor={opt.id} className="ml-2 block text-sm text-gray-900">
                      <span className="font-medium">{opt.title}</span>
                      <span className="block text-xs text-gray-500 mt-0.5">{opt.hint}</span>
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {hasDiscoveryInput && (
          <div className="max-w-xs">
            <label htmlFor="bulk-flow-parallel-runs" className="block text-sm font-medium text-gray-700 mb-1">
              Parallel runs
            </label>
            <input
              id="bulk-flow-parallel-runs"
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
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
            />
            <p className="text-xs text-gray-500 mt-1">
              Default {DEFAULT_PARALLEL_RUNS} ({MIN_PARALLEL_RUNS}–{MAX_PARALLEL_RUNS}).
            </p>
          </div>
        )}

        {isAnalyzing && (
          <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm font-medium text-blue-900">Analyzing required executions…</span>
              </div>
              <button
                type="button"
                onClick={() => cancelAnalysis()}
                disabled={isCancellingAnalysis}
                className="px-3 py-1 text-xs font-medium text-red-700 bg-red-100 border border-red-300 rounded hover:bg-red-200"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {hasDiscoveryInput && !isAnalyzing && (
          <div className="bg-gray-50 rounded-md p-3 text-sm text-gray-700">
            <div className="flex items-center justify-between">
              <span className="font-medium">
                {isCompleted
                  ? executionFailureCount > 0
                    ? 'Finished with errors'
                    : 'Run complete'
                  : selectedFlowIds.length > 0
                    ? `${selectedFlowIds.length} flow(s) selected`
                    : 'Discovering flows from anchor tag'}
              </span>
              <span className="text-gray-500">
                {isCompleted || isExecuting
                  ? `${completedExecutions} / ${totalExecutions} processed`
                  : `${totalExecutions} executions needed`}
              </span>
            </div>
            {(isExecuting || isCompleted) && totalExecutions > 0 && (
              <div className="mt-2">
                <div className="flex justify-between text-xs">
                  <span>Progress</span>
                  <span>
                    {completedExecutions} / {totalExecutions}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${totalExecutions > 0 ? (completedExecutions / totalExecutions) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {flowGroups.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-gray-900">Execution Details</h4>
            <div className="max-h-64 overflow-y-auto space-y-2">
              {flowGroups.map((group) => (
                <div key={group.flowId} className="border border-gray-200 rounded-md">
                  <div className="bg-gray-50 px-3 py-2 border-b border-gray-200">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ChevronRightIcon className="h-4 w-4 text-gray-400" />
                        <span className="font-medium text-sm">{group.flowName}</span>
                        <span className="text-xs text-gray-500">v{group.flowVersion}</span>
                      </div>
                      <span className="text-xs text-gray-500">
                        {group.completedExecutions} / {group.totalExecutions}
                      </span>
                    </div>
                  </div>
                  <div className="p-3 space-y-1 max-h-32 overflow-y-auto">
                    {group.executions.map((execution) => (
                      <div
                        key={`${execution.flowId}-${execution.documentId}`}
                        className="flex items-center justify-between text-xs"
                      >
                        <Link
                          href={`/orgs/${organizationId}/docs/${execution.documentId}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="min-w-0 truncate max-w-[200px] text-gray-700 hover:text-blue-700 hover:underline"
                          title={execution.documentName}
                        >
                          {execution.documentName}
                          {execution.reason ? (
                            <span className="text-gray-400 ml-1">({execution.reason})</span>
                          ) : null}
                        </Link>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {getStatusIcon(execution.status)}
                          <span
                            className={`capitalize ${
                              execution.status === 'completed'
                                ? 'text-green-600'
                                : execution.status === 'error'
                                  ? 'text-red-600'
                                  : execution.status === 'running'
                                    ? 'text-blue-600'
                                    : execution.status === 'cancelled'
                                      ? 'text-orange-600'
                                      : 'text-gray-500'
                            }`}
                          >
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

        {hasDiscoveryInput && !isAnalyzing && flowGroups.length === 0 && totalExecutions === 0 && !isCompleted && (
          <div className="text-sm text-center py-4">
            {isAnalysisCancelled ? (
              <span className="text-orange-600">Analysis cancelled</span>
            ) : (
              <span className="text-gray-500">No document-flow executions needed for the current selection.</span>
            )}
          </div>
        )}
      </div>
    );
  },
);

DocumentBulkRunFlows.displayName = 'DocumentBulkRunFlows';
