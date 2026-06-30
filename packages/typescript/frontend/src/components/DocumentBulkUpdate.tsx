import { Fragment, useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { XMarkIcon, BoltIcon, PlusIcon, MinusIcon, DocumentArrowDownIcon, TrashIcon, CpuChipIcon, DocumentTextIcon } from '@heroicons/react/24/outline'
import { Document, Tag } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';

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

type OperationData = TagsOperationData | MetadataOperationData | MetadataKeysOperationData | LLMOperationData | OCROperationData | null;

type PendingOperation = {
  operation: string;
  data: OperationData;
};

// Type guard functions
const isLLMOperationData = (data: OperationData): data is LLMOperationData => {
  return data !== null && typeof data === 'object' && 'selectedTag' in data;
};

const isOCROperationData = (data: OperationData): data is OCROperationData => {
  return data !== null && typeof data === 'object' && 'selectedTag' in data;
};
import { isColorLight } from '@/utils/colors';
import { toast } from 'react-hot-toast';
import { DocumentBulkUpdateTags, DocumentBulkUpdateTagsRef } from './DocumentBulkUpdateTags';
import { DocumentBulkUpdateMetadata, DocumentBulkUpdateMetadataRef } from './DocumentBulkUpdateMetadata';
import { DocumentBulkDownload, DocumentBulkDownloadRef } from './DocumentBulkDownload';
import { DocumentBulkDelete, DocumentBulkDeleteRef } from './DocumentBulkDelete';
import { DocumentBulkRunLLM, DocumentBulkRunLLMRef } from './DocumentBulkRunLLM';
import { DocumentBulkRunOCR, DocumentBulkRunOCRRef } from './DocumentBulkRunOCR';

interface DocumentBulkUpdateProps {
  isOpen: boolean
  onClose: () => void
  organizationId: string
  availableTags: Tag[]
  searchParameters: {
    searchTerm: string
    selectedTagFilters: Tag[]
    metadataSearch: string
    paginationModel: { page: number; pageSize: number }
  }
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

  // Operation definitions with icons and grouping
  const operationGroups = [
    {
      title: 'Tags',
      operations: [
        { value: 'addTags', label: 'Add', icon: PlusIcon, description: 'Add tags to documents' },
        { value: 'removeTags', label: 'Remove', icon: MinusIcon, description: 'Remove tags from documents' }
      ]
    },
    {
      title: 'Metadata',
      operations: [
        { value: 'addMetadata', label: 'Add', icon: PlusIcon, description: 'Add metadata fields' },
        { value: 'removeMetadata', label: 'Remove', icon: MinusIcon, description: 'Remove metadata fields' },
        { value: 'clearMetadata', label: 'Clear All', icon: TrashIcon, description: 'Clear all metadata' }
      ]
    },
    {
      title: 'Documents',
      operations: [
        { value: 'downloadDocuments', label: 'Download', icon: DocumentArrowDownIcon, description: 'Download documents' },
        { value: 'deleteDocuments', label: 'Delete', icon: TrashIcon, description: 'Delete documents' }
      ]
    },
    {
      title: 'LLM',
      operations: [
        { value: 'runLLMOperations', label: 'Run LLM', icon: CpuChipIcon, description: 'Run all LLM operations for tag' }
      ]
    },
    {
      title: 'OCR',
      operations: [
        { value: 'runOCROperations', label: 'Run OCR', icon: DocumentTextIcon, description: 'Run OCR on matching documents' }
      ]
    }
  ]

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

      const response = await docRouterOrgApi.listDocuments({
        skip: 0,
        limit: 3,
        nameSearch: searchParameters.searchTerm.trim() || undefined,
        tagIds: searchParameters.selectedTagFilters.length > 0 ? searchParameters.selectedTagFilters.map(tag => tag.id).join(',') : undefined,
        metadataSearch: searchParameters.metadataSearch.trim() ? parseAndEncodeMetadataSearch(searchParameters.metadataSearch.trim()) || undefined : undefined,
      })
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
      const response = await docRouterOrgApi.listDocuments({
        skip: 0,
        limit: 1, // We only need the count, not the documents
        nameSearch: searchParameters.searchTerm.trim() || undefined,
        tagIds: searchParameters.selectedTagFilters.length > 0 ? searchParameters.selectedTagFilters.map(tag => tag.id).join(',') : undefined,
        metadataSearch: searchParameters.metadataSearch.trim() ? parseAndEncodeMetadataSearch(searchParameters.metadataSearch.trim()) || undefined : undefined,
      });
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

      if (operation === 'runLLMOperations') {
        await runLLMRef.current?.executeRunLLM();
        return;
      }

      if (operation === 'runOCROperations') {
        await runOCRRef.current?.executeRunOCR();
        return;
      }

      // This should not happen since all operations are now handled by components
      console.warn('Unknown operation:', operation);
    } catch (error) {
      console.error('Bulk update error:', error);
      toast.error('Failed to perform bulk update');
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
        return true; // These operations are always available when there are documents
      case 'runLLMOperations':
        return isLLMOperationData(operationData) ? operationData.selectedTag !== null : false;
      case 'runOCROperations':
        return isOCROperationData(operationData) ? (operationData.executionCount ?? 0) > 0 : false;
      default:
        return false;
    }
  }

  return (
    <>
    <Transition show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={handleClose}>
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />

        <div className="fixed inset-0 overflow-hidden">
          <div className="absolute inset-0 overflow-hidden">
            <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
              <div className="pointer-events-auto w-screen max-w-4xl">
                <div className="flex h-full flex-col bg-white shadow-xl">
                  <div className="px-4 py-6 sm:px-6">
                    <div className="flex items-start justify-between">
                      <h2 className="text-base font-semibold leading-6 text-gray-900">
                        Bulk Document Actions
                      </h2>
                      <button
                        type="button"
                        className="rounded-md text-gray-400 hover:text-gray-500"
                        onClick={handleClose}
                      >
                        <XMarkIcon className="h-6 w-6" />
                      </button>
                    </div>
                    <span className="text-sm text-gray-500">Perform actions on filtered documents</span>
                  </div>
                  <div className="flex-1 overflow-y-auto px-4 sm:px-6 space-y-6">
                    {/* Current Filters Display */}
                    <div>
                      <h3 className="text-sm font-medium text-gray-900 mb-3">Current Filters</h3>
                      <div className="p-3 bg-gray-50 rounded border text-sm text-gray-600">
                        <div className="flex flex-wrap items-center gap-4">
                          {/* Search Term */}
                          {searchParameters.searchTerm && (
                            <div className="flex items-center gap-1">
                              <span className="font-medium text-gray-700">Search:</span>
                              <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs">
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

                          {/* Show "(none)" if no filters */}
                          {!searchParameters.searchTerm &&
                           searchParameters.selectedTagFilters.length === 0 &&
                           !searchParameters.metadataSearch && (
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
                                    className={`flex flex-col items-center px-2 py-1.5 rounded-md border transition-all duration-200 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:ring-offset-1 min-w-0 ${
                                      isDisabled
                                        ? 'text-gray-300 bg-gray-100 border-gray-200 cursor-not-allowed'
                                        : isSelected
                                        ? 'text-blue-700 bg-blue-50 border-blue-300 shadow-sm'
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
                      </div>

                      {/* Execute Button */}
                      <div className="flex justify-center pt-4">
                        {(selectedOperation === 'runLLMOperations' && isLLMOperationData(operationData) && operationData.isCompleted) ||
                        (selectedOperation === 'runOCROperations' && isOCROperationData(operationData) && operationData.isCompleted) ? (
                          <button
                            onClick={() => {
                              if (selectedOperation === 'runLLMOperations' && runLLMRef.current) {
                                runLLMRef.current.resetRunLLM();
                              }
                              if (selectedOperation === 'runOCROperations' && runOCRRef.current) {
                                runOCRRef.current.resetRunOCR();
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
                            className={`inline-flex items-center gap-2 px-6 py-2.5 text-sm font-medium rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors duration-200 ${
                              totalDocuments === 0 || !canApplyOperation()
                                ? 'text-gray-400 bg-gray-200 cursor-not-allowed'
                                : 'text-white bg-blue-600 hover:bg-blue-700'
                            }`}
                          >
                            <BoltIcon className="h-5 w-5" />
                            {selectedOperation === 'addTags' && 'Add Tags'}
                            {selectedOperation === 'removeTags' && 'Remove Tags'}
                            {selectedOperation === 'addMetadata' && 'Add Metadata'}
                            {selectedOperation === 'removeMetadata' && 'Remove Metadata'}
                            {selectedOperation === 'clearMetadata' && 'Clear All Metadata'}
                            {selectedOperation === 'downloadDocuments' && 'Download Documents'}
                            {selectedOperation === 'deleteDocuments' && 'Delete Documents'}
                            {selectedOperation === 'runLLMOperations' && 'Run LLM Operations'}
                            {selectedOperation === 'runOCROperations' && 'Run OCR'}
                          </button>
                        )}
                      </div>
                    </div>

                  </div>

                  <div className="flex flex-shrink-0 justify-end gap-3 px-4 py-4">
                    <button
                      type="button"
                      className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                      onClick={handleClose}
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Dialog>
    </Transition>

    {/* Confirmation Modal */}
    <Transition show={showConfirmation} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={handleCancelOperation}>
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0">
                  <svg className="h-6 w-6 text-yellow-600" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.345 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="flex-1">
                  <Dialog.Title as="h3" className="text-lg font-medium leading-6 text-gray-900">
                    Confirm Bulk Operation
                  </Dialog.Title>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500">
                      {pendingOperation?.operation === 'runLLMOperations' ? (
                        <>This will run <strong>{totalDocuments}</strong> LLM execution{totalDocuments !== 1 ? 's' : ''} (document-prompt combinations). This operation cannot be undone.</>
                      ) : pendingOperation?.operation === 'runOCROperations' ? (
                        <>This will queue <strong>{totalDocuments}</strong> OCR job{totalDocuments !== 1 ? 's' : ''} on matching documents.</>
                      ) : pendingOperation?.operation === 'downloadDocuments' ? (
                        <>This will download <strong>{totalDocuments}</strong> document{totalDocuments !== 1 ? 's' : ''}.</>
                      ) : pendingOperation?.operation === 'deleteDocuments' ? (
                        <>This will delete <strong>{totalDocuments}</strong> document{totalDocuments !== 1 ? 's' : ''}. This operation cannot be undone.</>
                      ) : (
                        <>This will {pendingOperation?.operation.replace(/([A-Z])/g, ' $1').toLowerCase()} on <strong>{totalDocuments}</strong> document{totalDocuments !== 1 ? 's' : ''}. This operation cannot be undone.</>
                      )}
                    </p>
                  </div>
                  <div className="mt-4 flex gap-3">
                    <button
                      type="button"
                      className="inline-flex justify-center rounded-md border border-transparent bg-yellow-600 px-4 py-2 text-sm font-medium text-white hover:bg-yellow-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-yellow-500 focus-visible:ring-offset-2"
                      onClick={handleConfirmOperation}
                    >
                      Continue
                    </button>
                    <button
                      type="button"
                      className="inline-flex justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
                      onClick={handleCancelOperation}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            </Dialog.Panel>
          </div>
        </div>
      </Dialog>
    </Transition>

    {/* Progress Modal */}
    <Transition show={isOperationLoading && totalDocuments > 0} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={() => {}}>
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
              <div className="flex items-center space-x-3">
                <div className="flex-shrink-0">
                  <svg className="animate-spin h-6 w-6 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </div>
                <div className="flex-1">
                  <Dialog.Title as="h3" className="text-lg font-medium leading-6 text-gray-900">
                    Processing Documents
                  </Dialog.Title>
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700">
                        Progress
                      </span>
                      <span className="text-sm text-gray-600">
                        {processedDocuments} / {totalDocuments}
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-3">
                      <div
                        className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                        style={{ width: `${totalDocuments > 0 ? (processedDocuments / totalDocuments) * 100 : 0}%` }}
                      ></div>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      {pendingOperation?.operation === 'runLLMOperations' ? (
                        isLLMOperationData(operationData) && operationData.isCancelling
                          ? 'Cancelling - waiting for running operations to complete...'
                          : isLLMOperationData(operationData) && operationData.isCancelled
                          ? 'Cancelled'
                          : processedDocuments === totalDocuments && processedDocuments > 0
                          ? 'Finalizing...'
                          : 'Please wait while we run LLM operations'
                      ) : pendingOperation?.operation === 'runOCROperations' ? (
                        isOCROperationData(operationData) && operationData.isCancelling
                          ? 'Cancelling - waiting for running OCR jobs to complete...'
                          : isOCROperationData(operationData) && operationData.isCancelled
                          ? 'Cancelled'
                          : processedDocuments === totalDocuments && processedDocuments > 0
                          ? 'Finalizing...'
                          : 'Please wait while we run OCR on documents'
                      ) : (
                        processedDocuments === totalDocuments && processedDocuments > 0
                          ? 'Finalizing...'
                          : 'Please wait while we update all documents'
                      )}
                    </p>
                  </div>
                  {/* Cancel button for LLM / OCR operations */}
                  {(pendingOperation?.operation === 'runLLMOperations' ||
                    pendingOperation?.operation === 'runOCROperations') && (
                    <div className="mt-4">
                      <button
                        type="button"
                        className="w-full inline-flex justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
                        onClick={() => {
                          if (pendingOperation?.operation === 'runLLMOperations' && runLLMRef.current) {
                            runLLMRef.current.cancelRunLLM();
                          }
                          if (pendingOperation?.operation === 'runOCROperations' && runOCRRef.current) {
                            runOCRRef.current.cancelRunOCR();
                          }
                        }}
                      >
                        Cancel Remaining Operations
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </Dialog.Panel>
          </div>
        </div>
      </Dialog>
    </Transition>
    </>
  )
}