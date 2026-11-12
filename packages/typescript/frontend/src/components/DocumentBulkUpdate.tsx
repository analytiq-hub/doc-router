import { toastActionError } from '@/utils/toastActionError';
import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  RefreshCw,
  Bolt,
  Cpu,
  Download,
  FileText,
  Minus,
  Plus,
  Trash2,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Document, Tag } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from 'cn'
// Operation data types
type TagsOperationData = Tag[];
type MetadataOperationData = Record<string, string>;
type MetadataKeysOperationData = string[];
type LLMOperationData = {
  selectedTag: Tag | null;
  executionCount?: number;
  isCompleted?: boolean;
  isCancelling?: boolean;
  isCancelled?: boolean;
  isAnalyzing?: boolean;
};

type OCROperationData = {
  selectedTag: Tag | null;
  executionCount?: number;
  isCompleted?: boolean;
  isCancelling?: boolean;
  isCancelled?: boolean;
  isAnalyzing?: boolean;
};

type FlowsOperationData = {
  selectedTag: Tag | null;
  selectedFlowIds: string[];
  executionCount?: number;
  isCompleted?: boolean;
  isCancelling?: boolean;
  isCancelled?: boolean;
  isAnalyzing?: boolean;
};

type CaseOperationData = { caseId: string; createCaseIfMissing: boolean };

type OperationData =
  | TagsOperationData
  | MetadataOperationData
  | MetadataKeysOperationData
  | LLMOperationData
  | OCROperationData
  | FlowsOperationData
  | CaseOperationData
  | null;

type PendingOperation = {
  operation: string;
  data: OperationData;
};

// Type guard functions
const isLLMOperationData = (data: OperationData): data is LLMOperationData => {
  return data !== null && typeof data === 'object' && 'selectedTag' in data;
};

const isOCROperationData = (data: OperationData): data is OCROperationData => {
  return data !== null && typeof data === 'object' && 'selectedTag' in data && !('selectedFlowIds' in data);
};

const isFlowsOperationData = (data: OperationData): data is FlowsOperationData => {
  return data !== null && typeof data === 'object' && 'selectedFlowIds' in data;
};
import { isColorLight } from '@/utils/colors';
import { toast } from 'react-hot-toast';
import { DocumentBulkUpdateTags, DocumentBulkUpdateTagsRef } from './DocumentBulkUpdateTags';
import { DocumentBulkUpdateMetadata, DocumentBulkUpdateMetadataRef } from './DocumentBulkUpdateMetadata';
import { DocumentBulkDownload, DocumentBulkDownloadRef } from './DocumentBulkDownload';
import { DocumentBulkDelete, DocumentBulkDeleteRef } from './DocumentBulkDelete';
import { DocumentBulkRunLLM, DocumentBulkRunLLMRef } from './DocumentBulkRunLLM';
import { DocumentBulkRunOCR, DocumentBulkRunOCRRef } from './DocumentBulkRunOCR';
import { DocumentBulkRunFlows, DocumentBulkRunFlowsRef } from './DocumentBulkRunFlows';
import { DocumentBulkUpdateCase, DocumentBulkUpdateCaseRef } from './DocumentBulkUpdateCase';
import { buildListDocumentsQuery, DocumentListSearchParameters } from '@/utils/documentListQuery';

function activeFilterSummary(filtersJson?: string): string | null {
  if (!filtersJson?.trim()) return null
  try {
    const parsed = JSON.parse(filtersJson) as {
      items?: { field: string; operator?: string; value?: unknown }[]
    }
    const items = parsed.items ?? []
    if (!items.length) return null
    return items
      .map((item) => {
        const v = item.value
        const value = v === null || v === undefined ? '' : String(v)
        return `${item.field} ${item.operator ?? 'is'} ${value}`.trim()
      })
      .join('; ')
  } catch {
    return null
  }
}

interface DocumentBulkUpdateProps {
  isOpen: boolean
  onClose: () => void
  organizationId: string
  availableTags: Tag[]
  searchParameters: DocumentListSearchParameters
  onRefresh?: () => void
}

export function DocumentBulkUpdate({
  isOpen,
  onClose,
  organizationId,
  availableTags,
  searchParameters,
  onRefresh
}: DocumentBulkUpdateProps) {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [previewDocuments, setPreviewDocuments] = useState<Document[]>([])
  // Remove individual state - now handled by sub-components
  const [isLoading, setIsLoading] = useState(false)
  const [isOperationLoading, setIsOperationLoading] = useState(false)
  const [totalDocuments, setTotalDocuments] = useState<number>(0)
  const [processedDocuments, setProcessedDocuments] = useState<number>(0)
  const [showConfirmation, setShowConfirmation] = useState(false)
  const [pendingOperation, setPendingOperation] = useState<PendingOperation | null>(null)
  const [selectedOperation, setSelectedOperation] = useState<string>('addTags')
  const [operationData, setOperationData] = useState<OperationData>(null)

  // Refs for all components
  const tagsRef = useRef<DocumentBulkUpdateTagsRef>(null)
  const metadataRef = useRef<DocumentBulkUpdateMetadataRef>(null)
  const downloadRef = useRef<DocumentBulkDownloadRef>(null)
  const deleteRef = useRef<DocumentBulkDeleteRef>(null)
  const runLLMRef = useRef<DocumentBulkRunLLMRef>(null)
  const runOCRRef = useRef<DocumentBulkRunOCRRef>(null)
  const runFlowsRef = useRef<DocumentBulkRunFlowsRef>(null)
  const caseRef = useRef<DocumentBulkUpdateCaseRef>(null)

  // Operation definitions with icons and grouping
  const operationGroups: {
    title: string
    operations: { value: string; label: string; icon: LucideIcon; description: string }[]
  }[] = [
    {
      title: 'Case',
      operations: [
        { value: 'assignToCase', label: 'Assign', icon: Plus, description: 'Assign filtered documents to a case' },
        { value: 'removeFromCase', label: 'Remove', icon: Minus, description: 'Clear case_id on filtered documents' },
      ],
    },
    {
      title: 'Tags',
      operations: [
        { value: 'addTags', label: 'Add', icon: Plus, description: 'Add tags to documents' },
        { value: 'removeTags', label: 'Remove', icon: Minus, description: 'Remove tags from documents' },
      ],
    },
    {
      title: 'Metadata',
      operations: [
        { value: 'addMetadata', label: 'Add', icon: Plus, description: 'Add metadata fields' },
        { value: 'removeMetadata', label: 'Remove', icon: Minus, description: 'Remove metadata fields' },
        { value: 'clearMetadata', label: 'Clear All', icon: Trash2, description: 'Clear all metadata' },
      ],
    },
    {
      title: 'Documents',
      operations: [
        { value: 'downloadDocuments', label: 'Download', icon: Download, description: 'Download documents' },
        { value: 'deleteDocuments', label: 'Delete', icon: Trash2, description: 'Delete documents' },
      ],
    },
    {
      title: 'LLM',
      operations: [
        { value: 'runLLMOperations', label: 'Run LLM', icon: Cpu, description: 'Run all LLM operations for tag' },
      ],
    },
    {
      title: 'OCR',
      operations: [
        { value: 'runOCROperations', label: 'Run OCR', icon: FileText, description: 'Run OCR on matching documents' },
      ],
    },
    {
      title: 'Flows',
      operations: [
        { value: 'runFlowsOperations', label: 'Run Flows', icon: RefreshCw, description: 'Re-run document event flows' },
      ],
    },
  ]

  const gridFilterSummary = activeFilterSummary(searchParameters.filters)

  const fetchPreviewDocuments = useCallback(async () => {
    try {
      setIsLoading(true)

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

      const response = await docRouterOrgApi.listDocuments(
        buildListDocumentsQuery(searchParameters, 0, 3)
      )
      setPreviewDocuments(response.documents)
      setTotalDocuments(response.total_count)
    } catch (error) {
      console.error('Error fetching preview documents:', error)
      setPreviewDocuments([])
    } finally {
      setIsLoading(false)
    }
  }, [searchParameters, docRouterOrgApi])

  useEffect(() => {
    if (isOpen) {
      // Reset all state when modal opens to avoid carrying over from previous operations
      // Sub-components handle their own state reset
      setTotalDocuments(0)
      setProcessedDocuments(0)
      setShowConfirmation(false)
      setPendingOperation(null)
      fetchPreviewDocuments()
    }
  }, [isOpen, searchParameters, organizationId, fetchPreviewDocuments])

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

  const countTotalMatchingDocuments = async (): Promise<number> => {
    try {
      const response = await docRouterOrgApi.listDocuments(
        buildListDocumentsQuery(searchParameters, 0, 1)
      );
      return response.total_count;
    } catch (error) {
      console.error('Error counting documents:', error);
      return 0;
    }
  };

  const handleBulkUpdate = async (operation: string) => {
    try {
      // Handle all operations via component refs
      if (operation === 'addTags' || operation === 'removeTags') {
        await tagsRef.current?.executeTags(operation);
        return;
      }

      if (operation === 'addMetadata' || operation === 'removeMetadata' || operation === 'clearMetadata') {
        await metadataRef.current?.executeMetadata(operation);
        return;
      }

      if (operation === 'downloadDocuments') {
        await downloadRef.current?.executeDownload();
        return;
      }

      if (operation === 'deleteDocuments') {
        await deleteRef.current?.executeDelete();
        return;
      }

      if (operation === 'assignToCase' || operation === 'removeFromCase') {
        await caseRef.current?.executeCase(operation);
        return;
      }

      if (operation === 'runLLMOperations') {
        await runLLMRef.current?.executeRunLLM();
        return;
      }

      if (operation === 'runOCROperations') {
        await runOCRRef.current?.executeRunOCR();
        return;
      }

      if (operation === 'runFlowsOperations') {
        await runFlowsRef.current?.executeRunFlows();
        return;
      }

      // This should not happen since all operations are now handled by components
      console.warn('Unknown operation:', operation);
    } catch (error) {
      console.error('Bulk update error:', error);
      toastActionError('Failed to perform bulk update', error);
    }
  };

  const handleApplyOperation = async (operation: string, data: OperationData) => {
    // For LLM operations, use execution count instead of document count
    if (operation === 'runLLMOperations') {
      const executionCount = (isLLMOperationData(data) ? data.executionCount : 0) || 0;
      if (executionCount === 0) {
        toast('No executions needed - all documents already have the latest prompt results');
        return;
      }
      setTotalDocuments(executionCount);
      setPendingOperation({ operation, data });
      setShowConfirmation(true);
      return;
    }

    if (operation === 'runOCROperations') {
      const executionCount = (isOCROperationData(data) ? data.executionCount : 0) || 0;
      if (executionCount === 0) {
        toast('No OCR executions needed for the current filters and mode');
        return;
      }
      setTotalDocuments(executionCount);
      setPendingOperation({ operation, data });
      setShowConfirmation(true);
      return;
    }

    if (operation === 'runFlowsOperations') {
      const executionCount = (isFlowsOperationData(data) ? data.executionCount : 0) || 0;
      if (executionCount === 0) {
        toast('No flow executions needed for the current selection and mode');
        return;
      }
      setTotalDocuments(executionCount);
      setPendingOperation({ operation, data });
      setShowConfirmation(true);
      return;
    }

    // For other operations, count total documents and show confirmation
    const total = await countTotalMatchingDocuments();
    if (total === 0) {
      toast('No documents match the current filters');
      return;
    }

    setTotalDocuments(total);
    setPendingOperation({ operation, data });
    setShowConfirmation(true);
  }

  const handleConfirmOperation = async () => {
    if (!pendingOperation) return;

    try {
      setIsOperationLoading(true);
      setShowConfirmation(false);

      await handleBulkUpdate(pendingOperation.operation);

      // Sub-components handle their own state clearing

      // Refresh preview documents
      await fetchPreviewDocuments();

      // Keep the modal open after operations complete so user can see results
    } finally {
      setIsOperationLoading(false);
      setPendingOperation(null);
      setProcessedDocuments(0);
    }
  }

  const handleCancelOperation = () => {
    setShowConfirmation(false);
    setPendingOperation(null);
    setTotalDocuments(0);
    setProcessedDocuments(0);
    onClose();
  }

  const handleClose = () => {
    if (selectedOperation === 'runLLMOperations') {
      const analyzing =
        isLLMOperationData(operationData) && operationData.isAnalyzing === true;
      if (isOperationLoading && !analyzing) {
        runLLMRef.current?.cancelRunLLM();
      } else if (analyzing) {
        runLLMRef.current?.cancelAnalysis({ notify: false });
      }
    }
    if (selectedOperation === 'runOCROperations') {
      const analyzing =
        isOCROperationData(operationData) && operationData.isAnalyzing === true;
      if (isOperationLoading && !analyzing) {
        runOCRRef.current?.cancelRunOCR();
      } else if (analyzing) {
        runOCRRef.current?.cancelAnalysis({ notify: false });
      }
    }
    if (selectedOperation === 'runFlowsOperations') {
      const analyzing =
        isFlowsOperationData(operationData) && operationData.isAnalyzing === true;
      if (isOperationLoading && !analyzing) {
        runFlowsRef.current?.cancelRunFlows();
      } else if (analyzing) {
        runFlowsRef.current?.cancelAnalysis({ notify: false });
      }
    }
    onClose();
  }

  const getOperationData = () => {
    return operationData;
  }

  const canApplyOperation = () => {
    if (totalDocuments === 0) return false;
    
    switch (selectedOperation) {
      case 'addTags':
      case 'removeTags':
        return operationData && Array.isArray(operationData) && operationData.length > 0;
      case 'addMetadata':
        return operationData && typeof operationData === 'object' && Object.keys(operationData).length > 0;
      case 'removeMetadata':
        return operationData && Array.isArray(operationData) && operationData.length > 0;
      case 'clearMetadata':
      case 'downloadDocuments':
      case 'deleteDocuments':
      case 'removeFromCase':
        return true; // These operations are always available when there are documents
      case 'assignToCase':
        return (
          operationData !== null &&
          typeof operationData === 'object' &&
          'caseId' in operationData &&
          Boolean((operationData as { caseId: string }).caseId?.trim())
        );
      case 'runLLMOperations':
        return isLLMOperationData(operationData) ? operationData.selectedTag !== null : false;
      case 'runOCROperations':
        return isOCROperationData(operationData) ? (operationData.executionCount ?? 0) > 0 : false;
      case 'runFlowsOperations':
        return isFlowsOperationData(operationData) ? (operationData.executionCount ?? 0) > 0 : false;
      default:
        return false;
    }
  }

  const confirmDescription = (() => {
    if (!pendingOperation) return ''
    const n = totalDocuments
    const plural = n !== 1 ? 's' : ''
    switch (pendingOperation.operation) {
      case 'runLLMOperations':
        return `This will run ${n} LLM execution${plural} (document-prompt combinations). This operation cannot be undone.`
      case 'runOCROperations':
        return `This will queue ${n} OCR job${plural} on matching documents.`
      case 'runFlowsOperations':
        return `This will run ${n} flow execution${plural} (document-flow combinations).`
      case 'downloadDocuments':
        return `This will download ${n} document${plural}.`
      case 'deleteDocuments':
        return `This will delete ${n} document${plural}. This operation cannot be undone.`
      default:
        return `This will ${pendingOperation.operation.replace(/([A-Z])/g, ' $1').toLowerCase()} on ${n} document${plural}. This operation cannot be undone.`
    }
  })()

  return (
    <>
      <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
        <DialogContent
          showCloseButton
          className={cn(
            'top-4 right-4 bottom-4 left-auto flex w-[min(calc(100vw-2rem),42rem)] max-w-none translate-x-0 translate-y-0 flex-col gap-0 rounded-xl p-0 sm:max-w-none',
          )}
        >
          <DialogHeader className="border-b px-4 py-4 sm:px-6">
            <DialogTitle>Bulk document actions</DialogTitle>
            <DialogDescription>Perform actions on filtered documents</DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 space-y-6">
                    {/* Current Filters Display */}
                    <div>
                      <h3 className="text-sm font-medium text-gray-900 mb-3">Current Filters</h3>
                      <div className="p-3 bg-gray-50 rounded border text-sm text-gray-600">
                        <div className="flex flex-wrap items-center gap-4">
                          {/* Search Term */}
                          {searchParameters.searchTerm && (
                            <div className="flex items-center gap-1">
                              <span className="font-medium text-gray-700">Search:</span>
                              <span className="px-2 py-0.5 bg-primary-100 text-primary-800 rounded text-xs">
                                &quot;{searchParameters.searchTerm}&quot;
                              </span>
                            </div>
                          )}

                          {/* Tag Filters */}
                          {searchParameters.selectedTagFilters.length > 0 && (
                            <div className="flex items-center gap-1">
                              <span className="font-medium text-gray-700">Tags:</span>
                              <div className="flex flex-wrap gap-1">
                                {searchParameters.selectedTagFilters.map(tag => (
                                  <span
                                    key={tag.id}
                                    className={`px-2 py-0.5 rounded text-xs ${
                                      isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
                                    }`}
                                    style={{ backgroundColor: tag.color }}
                                  >
                                    {tag.name}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Metadata Search */}
                          {searchParameters.metadataSearch && (
                            <div className="flex items-center gap-1">
                              <span className="font-medium text-gray-700">Metadata:</span>
                              <span className="px-2 py-0.5 bg-green-100 text-green-800 rounded text-xs">
                                {searchParameters.metadataSearch}
                              </span>
                            </div>
                          )}

                          {searchParameters.caseIdFilter && (
                            <div className="flex items-center gap-1">
                              <span className="font-medium text-gray-700">Case:</span>
                              <span className="px-2 py-0.5 bg-purple-100 text-purple-800 rounded text-xs">
                                {searchParameters.caseIdFilter}
                              </span>
                            </div>
                          )}

                          {gridFilterSummary && (
                            <div className="flex items-center gap-1 min-w-0">
                              <span className="font-medium text-gray-700 shrink-0">Column filters:</span>
                              <span className="px-2 py-0.5 bg-muted text-foreground rounded text-xs truncate max-w-md" title={gridFilterSummary}>
                                {gridFilterSummary}
                              </span>
                            </div>
                          )}

                          {/* Show "(none)" if no filters */}
                          {!searchParameters.searchTerm &&
                           searchParameters.selectedTagFilters.length === 0 &&
                           !searchParameters.metadataSearch &&
                           !searchParameters.caseIdFilter &&
                           !gridFilterSummary && (
                            <span className="text-gray-500 italic">(no active filters)</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Preview Documents */}
                    <div>
                      {isLoading ? (
                        <div className="text-sm text-gray-600">
                          <span className="font-medium">Matching Documents:</span> Loading preview...
                        </div>
                      ) : previewDocuments.length > 0 ? (
                        <div className="text-sm text-gray-600">
                          <span className="font-medium text-gray-900">
                            Matching Documents ({totalDocuments} total):
                          </span>{' '}
                          {previewDocuments.slice(0, 2).map((doc, index) => (
                            <span key={doc.id}>
                              {index > 0 && ', '}
                              <span className="text-gray-800">{doc.document_name}</span>
                            </span>
                          ))}
                          {totalDocuments > 2 && (
                            <span className="text-gray-500">, ...</span>
                          )}
                        </div>
                      ) : (
                        <div className="text-sm text-gray-600">
                          <span className="font-medium text-gray-900">Matching Documents (0 total):</span> 0
                        </div>
                      )}
                    </div>

                    {/* Operations */}
                    <div className="border border-gray-200 rounded-lg bg-gray-50 p-4">
                      <h3 className="text-sm font-medium text-gray-900 mb-4">Operations</h3>

                      {/* Operation Grid */}
                      <div className="flex flex-wrap gap-3 mb-4">
                        {operationGroups.map((group) => (
                          <div key={group.title} className="border border-gray-200 rounded-lg p-3 bg-white">
                            <h4 className="text-xs font-medium text-gray-600 uppercase tracking-wider mb-2">
                              {group.title}
                            </h4>
                            <div className="flex flex-wrap gap-1.5">
                              {group.operations.map((operation) => {
                                const Icon = operation.icon
                                const isSelected = selectedOperation === operation.value
                                const isDisabled = totalDocuments === 0

                                return (
                                  <button
                                    key={operation.value}
                                    onClick={() => !isDisabled && setSelectedOperation(operation.value)}
                                    disabled={isDisabled}
                                    className={`flex flex-col items-center px-2 py-1.5 rounded-md border transition-all duration-200 focus:outline-none focus:ring-1 focus:ring-primary-500 focus:ring-offset-1 min-w-0 ${
                                      isDisabled
                                        ? 'text-gray-300 bg-gray-100 border-gray-200 cursor-not-allowed'
                                        : isSelected
                                        ? 'text-primary-700 bg-primary-50 border-primary-300 shadow-sm'
                                        : 'text-gray-600 bg-gray-50 border-gray-300 hover:bg-gray-100 hover:border-gray-400'
                                    }`}
                                    title={operation.description}
                                  >
                                    <Icon className="h-4 w-4 mb-0.5" />
                                    <span className="text-xs font-medium text-center leading-tight whitespace-nowrap">
                                      {operation.label}
                                    </span>
                                  </button>
                                )
                              })}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Dynamic Content Area */}
                      <div className="border border-gray-300 rounded-md bg-white p-3">
                        {(selectedOperation === 'assignToCase' || selectedOperation === 'removeFromCase') && (
                          <DocumentBulkUpdateCase
                            ref={caseRef}
                            organizationId={organizationId}
                            searchParameters={searchParameters}
                            totalDocuments={totalDocuments}
                            selectedOperation={selectedOperation}
                            onDataChange={setOperationData}
                            disabled={isOperationLoading}
                            onProgress={(processed) => setProcessedDocuments(processed)}
                            onComplete={() => {
                              if (onRefresh) onRefresh();
                              fetchPreviewDocuments();
                            }}
                          />
                        )}

                        {(selectedOperation === 'addTags' || selectedOperation === 'removeTags') && (
                          <DocumentBulkUpdateTags
                            ref={tagsRef}
                            availableTags={availableTags}
                            totalDocuments={totalDocuments}
                            onDataChange={setOperationData}
                            disabled={isOperationLoading}
                            selectedOperation={selectedOperation}
                            organizationId={organizationId}
                            searchParameters={searchParameters}
                            onProgress={(processed) => setProcessedDocuments(processed)}
                            onComplete={() => {
                              if (onRefresh) {
                                onRefresh();
                              }
                              fetchPreviewDocuments();
                            }}
                          />
                        )}
                        
                        {(selectedOperation === 'addMetadata' || selectedOperation === 'removeMetadata' || selectedOperation === 'clearMetadata') && (
                          <DocumentBulkUpdateMetadata
                            ref={metadataRef}
                            totalDocuments={totalDocuments}
                            onDataChange={setOperationData}
                            disabled={isOperationLoading}
                            selectedOperation={selectedOperation}
                            organizationId={organizationId}
                            searchParameters={searchParameters}
                            onProgress={(processed) => setProcessedDocuments(processed)}
                            onComplete={() => {
                              if (onRefresh) {
                                onRefresh();
                              }
                              fetchPreviewDocuments();
                            }}
                          />
                        )}

                        {selectedOperation === 'downloadDocuments' && (
                          <DocumentBulkDownload
                            ref={downloadRef}
                            organizationId={organizationId}
                            searchParameters={searchParameters}
                            totalDocuments={totalDocuments}
                            disabled={isOperationLoading}
                            onProgress={(processed) => setProcessedDocuments(processed)}
                          />
                        )}

                        {selectedOperation === 'deleteDocuments' && (
                          <DocumentBulkDelete
                            ref={deleteRef}
                            organizationId={organizationId}
                            searchParameters={searchParameters}
                            totalDocuments={totalDocuments}
                            disabled={isOperationLoading}
                            onProgress={(processed) => setProcessedDocuments(processed)}
                            onComplete={() => {
                              if (onRefresh) {
                                onRefresh();
                              }
                              fetchPreviewDocuments();
                            }}
                          />
                        )}

                        {selectedOperation === 'runLLMOperations' && (
                          <DocumentBulkRunLLM
                            ref={runLLMRef}
                            organizationId={organizationId}
                            searchParameters={searchParameters}
                            totalDocuments={totalDocuments}
                            disabled={isOperationLoading}
                            onProgress={(processed) => setProcessedDocuments(processed)}
                            onComplete={() => {
                              if (onRefresh) {
                                onRefresh();
                              }
                              fetchPreviewDocuments();
                            }}
                            availableTags={availableTags}
                            onDataChange={setOperationData}
                          />
                        )}

                        {selectedOperation === 'runOCROperations' && (
                          <DocumentBulkRunOCR
                            ref={runOCRRef}
                            organizationId={organizationId}
                            searchParameters={searchParameters}
                            totalDocuments={totalDocuments}
                            disabled={isOperationLoading}
                            onProgress={(processed) => setProcessedDocuments(processed)}
                            onComplete={() => {
                              if (onRefresh) {
                                onRefresh();
                              }
                              fetchPreviewDocuments();
                            }}
                            availableTags={availableTags}
                            onDataChange={setOperationData}
                          />
                        )}

                        {selectedOperation === 'runFlowsOperations' && (
                          <DocumentBulkRunFlows
                            ref={runFlowsRef}
                            organizationId={organizationId}
                            searchParameters={searchParameters}
                            totalDocuments={totalDocuments}
                            disabled={isOperationLoading}
                            onProgress={(processed) => setProcessedDocuments(processed)}
                            onComplete={() => {
                              if (onRefresh) {
                                onRefresh();
                              }
                              fetchPreviewDocuments();
                            }}
                            availableTags={availableTags}
                            onDataChange={setOperationData}
                          />
                        )}
                      </div>

                      {/* Execute Button */}
                      <div className="flex justify-center pt-4">
                        {(selectedOperation === 'runLLMOperations' && isLLMOperationData(operationData) && operationData.isCompleted) ||
                        (selectedOperation === 'runOCROperations' && isOCROperationData(operationData) && operationData.isCompleted) ||
                        (selectedOperation === 'runFlowsOperations' && isFlowsOperationData(operationData) && operationData.isCompleted) ? (
                          <button
                            onClick={() => {
                              if (selectedOperation === 'runLLMOperations' && runLLMRef.current) {
                                runLLMRef.current.resetRunLLM();
                              }
                              if (selectedOperation === 'runOCROperations' && runOCRRef.current) {
                                runOCRRef.current.resetRunOCR();
                              }
                              if (selectedOperation === 'runFlowsOperations' && runFlowsRef.current) {
                                runFlowsRef.current.resetRunFlows();
                              }
                            }}
                            className="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-medium rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-colors duration-200 text-white bg-green-600 hover:bg-green-700"
                          >
                            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            Reset for New Run
                          </button>
                        ) : (
                          <button
                            onClick={() => handleApplyOperation(selectedOperation, getOperationData())}
                            disabled={totalDocuments === 0 || !canApplyOperation()}
                            className={`inline-flex items-center gap-2 px-6 py-2.5 text-sm font-medium rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors duration-200 ${
                              totalDocuments === 0 || !canApplyOperation()
                                ? 'text-gray-400 bg-gray-200 cursor-not-allowed'
                                : 'text-white bg-primary-600 hover:bg-primary-700'
                            }`}
                          >
                            <Bolt className="h-5 w-5" />
                            {selectedOperation === 'addTags' && 'Add Tags'}
                            {selectedOperation === 'removeTags' && 'Remove Tags'}
                            {selectedOperation === 'addMetadata' && 'Add Metadata'}
                            {selectedOperation === 'removeMetadata' && 'Remove Metadata'}
                            {selectedOperation === 'clearMetadata' && 'Clear All Metadata'}
                            {selectedOperation === 'downloadDocuments' && 'Download Documents'}
                            {selectedOperation === 'deleteDocuments' && 'Delete Documents'}
                            {selectedOperation === 'runLLMOperations' && 'Run LLM Operations'}
                            {selectedOperation === 'runOCROperations' && 'Run OCR'}
                            {selectedOperation === 'runFlowsOperations' && 'Run Flows'}
                          </button>
                        )}
                      </div>
                    </div>

          </div>

          <div className="flex shrink-0 justify-end gap-3 border-t bg-muted/40 px-4 py-4">
            <Button variant="outline" onClick={handleClose}>
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={showConfirmation} onOpenChange={(open) => !open && handleCancelOperation()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm bulk operation</AlertDialogTitle>
            <AlertDialogDescription>{confirmDescription}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <Button onClick={handleConfirmOperation}>Continue</Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={isOperationLoading && totalDocuments > 0} onOpenChange={() => undefined}>
        <DialogContent showCloseButton={false} className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Processing documents</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">Progress</span>
              <span className="text-muted-foreground">
                {processedDocuments} / {totalDocuments}
              </span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{
                  width: `${totalDocuments > 0 ? (processedDocuments / totalDocuments) * 100 : 0}%`,
                }}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {pendingOperation?.operation === 'runLLMOperations'
                ? isLLMOperationData(operationData) && operationData.isCancelling
                  ? 'Cancelling — waiting for running operations to complete…'
                  : isLLMOperationData(operationData) && operationData.isCancelled
                    ? 'Cancelled'
                    : processedDocuments === totalDocuments && processedDocuments > 0
                      ? 'Finalizing…'
                      : 'Please wait while we run LLM operations'
                : pendingOperation?.operation === 'runOCROperations'
                  ? isOCROperationData(operationData) && operationData.isCancelling
                    ? 'Cancelling — waiting for running OCR jobs to complete…'
                    : isOCROperationData(operationData) && operationData.isCancelled
                      ? 'Cancelled'
                      : processedDocuments === totalDocuments && processedDocuments > 0
                        ? 'Finalizing…'
                        : 'Please wait while we run OCR on documents'
                  : pendingOperation?.operation === 'runFlowsOperations'
                    ? isFlowsOperationData(operationData) && operationData.isCancelling
                      ? 'Cancelling — waiting for running flow executions to complete…'
                      : isFlowsOperationData(operationData) && operationData.isCancelled
                        ? 'Cancelled'
                        : processedDocuments === totalDocuments && processedDocuments > 0
                          ? 'Finalizing…'
                          : 'Please wait while we run flows on documents'
                    : processedDocuments === totalDocuments && processedDocuments > 0
                      ? 'Finalizing…'
                      : 'Please wait while we update all documents'}
            </p>
            {(pendingOperation?.operation === 'runLLMOperations' ||
              pendingOperation?.operation === 'runOCROperations' ||
              pendingOperation?.operation === 'runFlowsOperations') && (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  if (pendingOperation?.operation === 'runLLMOperations' && runLLMRef.current) {
                    runLLMRef.current.cancelRunLLM()
                  }
                  if (pendingOperation?.operation === 'runOCROperations' && runOCRRef.current) {
                    runOCRRef.current.cancelRunOCR()
                  }
                  if (pendingOperation?.operation === 'runFlowsOperations' && runFlowsRef.current) {
                    runFlowsRef.current.cancelRunFlows()
                  }
                }}
              >
                Cancel remaining operations
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}