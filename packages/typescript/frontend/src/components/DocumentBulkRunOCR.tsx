import {
  forwardRef,
  useImperativeHandle,
  useState,
  useEffect,
  useCallback,
  useRef,
  useMemo,
} from 'react';
import type { BulkAnalyzeOCRResponse, Tag } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';
import { toast } from 'react-hot-toast';
import SingleTagSelector from './SingleTagSelector';

const DEFAULT_PARALLEL_RUNS = 3;
const MIN_PARALLEL_RUNS = 1;
const MAX_PARALLEL_RUNS = 10;
const BULK_OCR_PARALLEL_RUNS_KEY = 'docrouter.bulkOcrParallelRuns';

function clampParallelRuns(value: number): number {
  const n = Math.floor(value);
  if (!Number.isFinite(n)) return DEFAULT_PARALLEL_RUNS;
  return Math.min(MAX_PARALLEL_RUNS, Math.max(MIN_PARALLEL_RUNS, n));
}

function readParallelRunsFromSession(): number {
  if (typeof window === 'undefined') return DEFAULT_PARALLEL_RUNS;
  try {
    const raw = sessionStorage.getItem(BULK_OCR_PARALLEL_RUNS_KEY);
    if (raw === null) return DEFAULT_PARALLEL_RUNS;
    return clampParallelRuns(parseInt(raw, 10));
  } catch {
    return DEFAULT_PARALLEL_RUNS;
  }
}

function persistParallelRunsToSession(value: number): void {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(BULK_OCR_PARALLEL_RUNS_KEY, String(value));
  } catch {
    // ignore
  }
}

function sleepMs(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runWithConcurrency<T>(
  items: T[],
  limit: number,
  worker: (item: T) => Promise<void>,
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

type ExecutionMode = 'all' | 'missing' | 'outdated';

interface OcrExecution {
  documentId: string;
  documentName: string;
  reason?: string;
  status: 'pending' | 'running' | 'completed' | 'error' | 'cancelled';
  error?: string;
}

interface DocumentBulkRunOCRProps {
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

export interface DocumentBulkRunOCRRef {
  executeRunOCR: () => Promise<void>;
  cancelRunOCR: () => void;
  cancelAnalysis: (options?: { notify?: boolean }) => void;
  resetRunOCR: () => void;
}

async function readBaselineOcrDate(
  api: DocRouterOrgApi,
  documentId: string,
): Promise<string | null> {
  try {
    const meta = await api.getOCRMetadata({ documentId });
    return meta.ocr_date ?? null;
  } catch {
    return null;
  }
}

function isOcrRunComplete(
  docState: string,
  sawProcessing: boolean,
  baselineOcrDate: string | null,
  currentOcrDate: string | null | undefined,
): boolean {
  if (docState !== 'ocr_completed') {
    return false;
  }
  if (sawProcessing) {
    return true;
  }
  // First-time OCR: accept once metadata exists.
  if (baselineOcrDate === null) {
    return currentOcrDate != null;
  }
  // Force/outdated re-run: stale metadata must not count as done.
  return currentOcrDate != null && currentOcrDate !== baselineOcrDate;
}

async function waitForOcrCompletion(
  api: DocRouterOrgApi,
  documentId: string,
  shouldStop: () => boolean,
  baselineOcrDate: string | null,
): Promise<void> {
  const POLL_MS = 1500;
  const MAX_WAIT_MS = 600_000;
  const deadline = Date.now() + MAX_WAIT_MS;
  let sawProcessing = false;

  while (Date.now() < deadline) {
    if (shouldStop()) {
      throw new Error('cancelled');
    }
    const doc = await api.getDocument({
      documentId,
      fileType: 'pdf',
      includeContent: false,
    });
    if (doc.state === 'ocr_failed') {
      throw new Error('OCR failed');
    }
    if (doc.state === 'ocr_processing') {
      sawProcessing = true;
    }
    if (doc.state === 'ocr_completed') {
      let currentOcrDate: string | null | undefined;
      try {
        const meta = await api.getOCRMetadata({ documentId });
        currentOcrDate = meta.ocr_date;
      } catch {
        currentOcrDate = undefined;
      }
      if (isOcrRunComplete(doc.state, sawProcessing, baselineOcrDate, currentOcrDate)) {
        return;
      }
    }
    await sleepMs(POLL_MS);
  }
  throw new Error('OCR timed out');
}

export const DocumentBulkRunOCR = forwardRef<DocumentBulkRunOCRRef, DocumentBulkRunOCRProps>(
  ({ organizationId, searchParameters, disabled, onProgress, onComplete, availableTags, onDataChange }, ref) => {
    const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
    const [selectedTag, setSelectedTag] = useState<Tag | null>(null);
    const [executionMode, setExecutionMode] = useState<ExecutionMode>('outdated');
    const [parallelRuns, setParallelRuns] = useState(readParallelRunsFromSession);
    const [executions, setExecutions] = useState<OcrExecution[]>([]);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isExecuting, setIsExecuting] = useState(false);
    const [isCancelling, setIsCancelling] = useState(false);
    const [isCancelled, setIsCancelled] = useState(false);
    const [isCompleted, setIsCompleted] = useState(false);
    const [totalExecutions, setTotalExecutions] = useState(0);
    const [completedExecutions, setCompletedExecutions] = useState(0);
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
        isCancelledRef.current = true;
        analysisAbortController.current?.abort();
      };
    }, []);

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

    const notifyComplete = useCallback(() => {
      queueMicrotask(() => {
        if (isMountedRef.current) {
          onCompleteRef.current?.();
        }
      });
    }, []);

    const handleParallelRunsCommit = useCallback(() => {
      const clamped = clampParallelRuns(parallelRuns);
      setParallelRuns(clamped);
      persistParallelRunsToSession(clamped);
    }, [parallelRuns]);

    const parseMetadataSearch = (searchStr: string): Record<string, string> | undefined => {
      if (!searchStr.trim()) return undefined;
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
    }, [selectedTag, searchParameters.searchTerm, searchParameters.selectedTagFilters, searchParameters.metadataSearch]);

    const analyzeExecutions = useCallback(async () => {
      const generation = ++analyzeGenerationRef.current;
      isCancelledRef.current = false;
      analysisAbortController.current?.abort();
      analysisAbortController.current = new AbortController();
      const signal = analysisAbortController.current.signal;

      setIsAnalyzing(true);
      setIsAnalysisCancelled(false);

      try {
        const response: BulkAnalyzeOCRResponse = await docRouterOrgApi.bulkAnalyzeOCR({
          tagId: selectedTag?.id,
          mode: executionMode,
          documentFilters: buildDocumentFilters(),
        });

        if (signal.aborted || !isMountedRef.current || generation !== analyzeGenerationRef.current) {
          return;
        }

        const rows: OcrExecution[] = response.executions.map((exec) => ({
          documentId: exec.document_id,
          documentName: exec.document_name,
          reason: exec.reason,
          status: 'pending',
        }));
        setExecutions(rows);
        setTotalExecutions(response.total_executions);
      } catch (error) {
        if (signal.aborted || !isMountedRef.current || generation !== analyzeGenerationRef.current) {
          if (signal.aborted && isMountedRef.current) {
            setExecutions([]);
            setTotalExecutions(0);
            setIsAnalysisCancelled(true);
          }
          return;
        }
        console.error('Error analyzing OCR executions:', error);
        toast.error('Failed to analyze required OCR executions');
      } finally {
        if (isMountedRef.current && generation === analyzeGenerationRef.current) {
          setIsAnalyzing(false);
          analysisAbortController.current = null;
        }
      }
    }, [selectedTag, executionMode, buildDocumentFilters, docRouterOrgApi]);

    useEffect(() => {
      void analyzeExecutions();

      return () => {
        analysisAbortController.current?.abort();
      };
    }, [
      selectedTag,
      executionMode,
      searchParameters.searchTerm,
      searchParameters.selectedTagFilters,
      searchParameters.metadataSearch,
      analyzeExecutions,
    ]);

    const cancelAnalysis = useCallback((options?: { notify?: boolean }) => {
      analysisAbortController.current?.abort();
      isCancelledRef.current = true;
      setIsAnalysisCancelled(true);
      setExecutions([]);
      setTotalExecutions(0);
      if (options?.notify !== false) {
        toast('OCR analysis cancelled');
      }
    }, []);

    const cancelRunOCR = useCallback(() => {
      isCancelledRef.current = true;
      setIsCancelling(true);
      setIsCancelled(true);
    }, []);

    const resetRunOCR = useCallback(() => {
      isCancelledRef.current = false;
      setIsCancelling(false);
      setIsCancelled(false);
      setIsCompleted(false);
      setCompletedExecutions(0);
      completedExecutionsRef.current = 0;
      setExecutions((prev) => prev.map((e) => ({ ...e, status: 'pending', error: undefined })));
      void analyzeExecutions();
    }, [analyzeExecutions]);

    const executeRunOCR = async () => {
      if (executions.length === 0) return;

      isCancelledRef.current = false;
      setIsCancelling(false);
      setIsCancelled(false);
      setIsCompleted(false);
      setIsExecuting(true);
      completedExecutionsRef.current = 0;
      setCompletedExecutions(0);

      const concurrencyLimit = clampParallelRuns(parallelRuns);

      const markStatus = (
        documentId: string,
        update: Partial<OcrExecution> & { status: OcrExecution['status'] },
      ) => {
        if (!isMountedRef.current) return;
        setExecutions((prev) =>
          prev.map((e) => (e.documentId === documentId ? { ...e, ...update } : e)),
        );
      };

      const recordProgress = () => {
        if (!isMountedRef.current) return;
        completedExecutionsRef.current += 1;
        setCompletedExecutions(completedExecutionsRef.current);
        notifyExecutionProgress(completedExecutionsRef.current);
      };

      try {
        await runWithConcurrency(
          executions,
          concurrencyLimit,
          async (execution) => {
            if (isCancelledRef.current) {
              markStatus(execution.documentId, { status: 'cancelled' });
              return;
            }

            markStatus(execution.documentId, { status: 'running' });

            try {
              const baselineOcrDate = await readBaselineOcrDate(
                docRouterOrgApi,
                execution.documentId,
              );
              await docRouterOrgApi.runOCR({
                documentId: execution.documentId,
                force: executionMode !== 'missing',
                ocrOnly: true,
              });
              await waitForOcrCompletion(
                docRouterOrgApi,
                execution.documentId,
                () => isCancelledRef.current,
                baselineOcrDate,
              );
              markStatus(execution.documentId, { status: 'completed' });
              recordProgress();
            } catch (error) {
              markStatus(execution.documentId, {
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
            `OCR execution cancelled - completed ${completedExecutionsRef.current} of ${totalExecutions}`,
          );
        } else if (isMountedRef.current) {
          toast.success(`Completed OCR on ${totalExecutions} document(s)`);
          setIsCompleted(true);
        }
        notifyComplete();
      } catch (error) {
        console.error('Error during bulk OCR execution:', error);
        toast.error('Failed to complete bulk OCR execution');
      } finally {
        if (isMountedRef.current) {
          setIsExecuting(false);
          setIsCancelling(false);
        }
      }
    };

    useImperativeHandle(ref, () => ({
      executeRunOCR,
      cancelRunOCR,
      cancelAnalysis,
      resetRunOCR,
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
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <SingleTagSelector
              availableTags={availableTags}
              selectedTag={selectedTag}
              onChange={setSelectedTag}
              disabled={disabled || isExecuting}
              placeholder="Optional anchor tag for document filter..."
              label="Optional anchor tag"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">Execution Strategy</label>
            <div className="space-y-2">
              {(
                [
                  ['outdated', 'Run when missing or outdated', 'Queue when OCR is absent or org OCR settings changed since the stored run'],
                  ['missing', 'Run only when completely missing', 'Queue only when no OCR result exists'],
                  ['all', 'Run on all matching documents', 'Re-run OCR on every matching document (force)'],
                ] as const
              ).map(([mode, title, desc]) => (
                <div key={mode} className="flex items-start">
                  <input
                    id={`ocr-mode-${mode}`}
                    name="ocrExecutionMode"
                    type="radio"
                    value={mode}
                    checked={executionMode === mode}
                    onChange={(e) => setExecutionMode(e.target.value as ExecutionMode)}
                    disabled={disabled || isExecuting || isAnalyzing}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 mt-0.5"
                  />
                  <label htmlFor={`ocr-mode-${mode}`} className="ml-2 block text-sm text-gray-900">
                    <span className="font-medium">{title}</span>
                    <span className="block text-xs text-gray-500 mt-0.5">{desc}</span>
                  </label>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="max-w-xs">
          <label htmlFor="bulk-ocr-parallel-runs" className="block text-sm font-medium text-gray-700 mb-1">
            Parallel runs
          </label>
          <input
            id="bulk-ocr-parallel-runs"
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
            Max parallel OCR jobs ({MIN_PARALLEL_RUNS}–{MAX_PARALLEL_RUNS}, default {DEFAULT_PARALLEL_RUNS}).
          </p>
        </div>

        {isAnalyzing && (
          <div className="bg-blue-50 border border-blue-200 rounded-md p-4 text-sm text-blue-900">
            Analyzing required OCR executions...
          </div>
        )}

        {!isAnalyzing && (
          <div className="bg-gray-50 rounded-md p-3 text-sm text-gray-700">
            <div className="flex items-center justify-between">
              <span className="font-medium">{totalExecutions} OCR execution(s) needed</span>
              {isExecuting && (
                <span>
                  {completedExecutions} / {totalExecutions}
                </span>
              )}
            </div>
          </div>
        )}

        {executions.length > 0 && (
          <div className="max-h-64 overflow-y-auto space-y-1 border border-gray-200 rounded-md p-3">
            {executions.map((execution) => (
              <div key={execution.documentId} className="flex items-center justify-between text-xs">
                <span className="text-gray-700 truncate max-w-[240px]">{execution.documentName}</span>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {getStatusIcon(execution.status)}
                  <span className="capitalize text-gray-600">{execution.status}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {!isAnalyzing && executions.length === 0 && totalExecutions === 0 && (
          <div className="text-sm text-center py-4 text-gray-500">
            {isAnalysisCancelled
              ? 'Analysis cancelled'
              : 'No OCR executions needed for the current filters and mode.'}
          </div>
        )}
      </div>
    );
  },
);

DocumentBulkRunOCR.displayName = 'DocumentBulkRunOCR';
