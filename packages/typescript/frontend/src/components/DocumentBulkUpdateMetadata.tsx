import { useState, useEffect, forwardRef, useImperativeHandle, useCallback, useMemo } from 'react'
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline'
import { Tag } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api'
import { toast } from 'react-hot-toast'

// Type definitions for metadata operations
type MetadataOperationData = Record<string, string> | string[] | null;

interface DocumentBulkUpdateMetadataProps {
  totalDocuments: number
  onDataChange: (data: MetadataOperationData) => void
  disabled?: boolean
  selectedOperation?: string
  organizationId: string
  searchParameters: {
    searchTerm: string
    selectedTagFilters: Tag[]
    metadataSearch: string
    paginationModel: { page: number; pageSize: number }
  }
  onProgress?: (processed: number, total: number) => void
  onComplete?: () => void
}

export interface DocumentBulkUpdateMetadataRef {
  executeMetadata: (operation: string) => Promise<void>
}

export const DocumentBulkUpdateMetadata = forwardRef<DocumentBulkUpdateMetadataRef, DocumentBulkUpdateMetadataProps>(({
  totalDocuments,
  onDataChange,
  disabled = false,
  selectedOperation = 'addMetadata',
  organizationId,
  searchParameters,
  onProgress,
  onComplete
}, ref) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [metadataFields, setMetadataFields] = useState<Array<{id: string, key: string, value: string}>>([])
  const [metadataKeysToRemove, setMetadataKeysToRemove] = useState<string>('')

  const updateData = useCallback(() => {
    let data: MetadataOperationData = null

    switch (selectedOperation) {
      case 'addMetadata':
        const validFields = metadataFields.filter(field => field.key.trim() !== '' && field.value.trim() !== '')
        if (validFields.length > 0) {
          // Check for duplicate keys
          const keys = validFields.map(field => field.key.trim())
          const duplicateKeys = keys.filter((key, index) => keys.indexOf(key) !== index)
          if (duplicateKeys.length > 0) {
            alert(`Duplicate keys found: ${duplicateKeys.join(', ')}. Please remove or rename duplicate keys.`)
            return
          }
          data = validFields.reduce((acc, field) => {
            acc[field.key.trim()] = field.value.trim()
            return acc
          }, {} as Record<string, string>)
        }
        break
      case 'removeMetadata':
        const keysToRemove = metadataKeysToRemove
          .split(',')
          .map(key => key.trim())
          .filter(key => key !== '')
        if (keysToRemove.length > 0) {
          data = keysToRemove
        }
        break
      case 'clearMetadata':
        data = null // Clear all metadata
        break
    }

    onDataChange(data)
  }, [selectedOperation, metadataFields, metadataKeysToRemove, onDataChange])

  const handleAddMetadataField = () => {
    const newId = `field_${Date.now()}`
    setMetadataFields(prev => {
      const newFields = [...prev, { id: newId, key: '', value: '' }]
      setTimeout(() => updateData(), 0) // Update data after state change
      return newFields
    })
  }

  const handleRemoveMetadataField = (id: string) => {
    setMetadataFields(prev => {
      const newFields = prev.filter(field => field.id !== id)
      setTimeout(() => updateData(), 0) // Update data after state change
      return newFields
    })
  }

  const handleMetadataKeyChange = (id: string, newKey: string) => {
    setMetadataFields(prev => {
      const newFields = prev.map(field =>
        field.id === id ? { ...field, key: newKey } : field
      )
      setTimeout(() => updateData(), 0) // Update data after state change
      return newFields
    })
  }

  const handleMetadataValueChange = (id: string, newValue: string) => {
    setMetadataFields(prev => {
      const newFields = prev.map(field =>
        field.id === id ? { ...field, value: newValue } : field
      )
      setTimeout(() => updateData(), 0) // Update data after state change
      return newFields
    })
  }

  const handleKeysToRemoveChange = (value: string) => {
    setMetadataKeysToRemove(value)
    // Call updateData with the new value directly instead of waiting for state
    const keysToRemove = value
      .split(',')
      .map(key => key.trim())
      .filter(key => key !== '')

    let data: MetadataOperationData = null
    if (keysToRemove.length > 0) {
      data = keysToRemove
    }
    onDataChange(data)
  }

  // Update data when operation changes
  useEffect(() => {
    updateData()
  }, [selectedOperation, updateData])

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

  const handleBulkMetadataUpdate = async (operation: string) => {
    try {
      let successCount = 0;
      let failureCount = 0;
      let skip = 0;
      const limit = 1000; // Maximum allowed by API

      while (true) {
        // Fetch next batch of documents
        const batchResponse = await docRouterOrgApi.listDocuments({
          skip,
          limit,
          nameSearch: searchParameters.searchTerm.trim() || undefined,
          tagIds: searchParameters.selectedTagFilters.length > 0 ? searchParameters.selectedTagFilters.map(tag => tag.id).join(',') : undefined,
          metadataSearch: searchParameters.metadataSearch.trim() ? parseAndEncodeMetadataSearch(searchParameters.metadataSearch.trim()) || undefined : undefined,
        });

        const documentsInBatch = batchResponse.documents;

        if (documentsInBatch.length === 0) {
          break; // No more documents
        }

        // Update each document in the current batch
        for (const doc of documentsInBatch) {
          try {
            let updatedMetadata;

            if (operation === 'addMetadata') {
              const validFields = metadataFields.filter(field => field.key.trim() !== '' && field.value.trim() !== '');
              const newMetadata = validFields.reduce((acc, field) => {
                acc[field.key.trim()] = field.value.trim();
                return acc;
              }, {} as Record<string, string>);
              updatedMetadata = { ...(doc.metadata || {}), ...newMetadata };
            } else if (operation === 'removeMetadata') {
              const originalMetadata = doc.metadata || {};
              const keysToRemove = metadataKeysToRemove
                .split(',')
                .map(key => key.trim())
                .filter(key => key !== '');

              // Create new object without the specified keys
              const filteredMetadata: Record<string, string> = {};
              for (const [key, value] of Object.entries(originalMetadata)) {
                if (!keysToRemove.includes(key)) {
                  filteredMetadata[key] = String(value);
                }
              }
              updatedMetadata = filteredMetadata;
            } else if (operation === 'clearMetadata') {
              updatedMetadata = {};
            }

            await docRouterOrgApi.updateDocument({
              documentId: doc.id,
              tagIds: doc.tag_ids,
              metadata: updatedMetadata
            });

            successCount++;
          } catch (error) {
            console.error(`Failed to update document ${doc.document_name}:`, error);
            failureCount++;
          }

          // Update progress
          if (onProgress) {
            onProgress(successCount + failureCount, totalDocuments);
          }
        }

        // If we got less than the limit, we've reached the end
        if (documentsInBatch.length < limit) {
          break;
        }

        // Move to next batch
        skip += limit;
      }

      // Show results
      if (successCount > 0) {
        let message = '';
        switch (operation) {
          case 'addMetadata':
            message = `Metadata added to ${successCount} document${successCount !== 1 ? 's' : ''}`;
            break;
          case 'removeMetadata':
            message = `Metadata removed from ${successCount} document${successCount !== 1 ? 's' : ''}`;
            break;
          case 'clearMetadata':
            message = `All metadata cleared from ${successCount} document${successCount !== 1 ? 's' : ''}`;
            break;
          default:
            message = `Operation completed on ${successCount} document${successCount !== 1 ? 's' : ''}`;
        }
        toast.success(message);
      }

      if (failureCount > 0) {
        toast.error(`Failed to update ${failureCount} document${failureCount !== 1 ? 's' : ''}`);
      }

      if (onComplete) {
        onComplete();
      }
    } catch (error) {
      console.error('Bulk metadata update error:', error);
      toast.error('Failed to perform bulk metadata update');
    }
  };

  useImperativeHandle(ref, () => ({
    executeMetadata: handleBulkMetadataUpdate
  }));

  return (
    <div>
      {/* Dynamic Content Area */}
      {selectedOperation === 'addMetadata' && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-gray-600">Configure metadata fields to add:</span>
            <button
              type="button"
              onClick={handleAddMetadataField}
              disabled={disabled || totalDocuments === 0}
              className="inline-flex items-center px-2 py-1 text-xs font-medium text-blue-600 hover:text-blue-500 disabled:text-gray-400"
            >
              <PlusIcon className="h-4 w-4 mr-1" />
              Add Field
            </button>
          </div>

            <div className="space-y-2">
              {metadataFields.map((field) => (
                <div key={field.id} className="flex gap-2 items-center">
                  <input
                    type="text"
                    placeholder="Key"
                    value={field.key}
                    onChange={(e) => handleMetadataKeyChange(field.id, e.target.value)}
                    disabled={disabled || totalDocuments === 0}
                    className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm disabled:bg-gray-100"
                  />
                  <input
                    type="text"
                    placeholder="Value"
                    value={field.value}
                    onChange={(e) => handleMetadataValueChange(field.id, e.target.value)}
                    disabled={disabled || totalDocuments === 0}
                    className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm disabled:bg-gray-100"
                  />
                  <button
                    type="button"
                    onClick={() => handleRemoveMetadataField(field.id)}
                    disabled={disabled || totalDocuments === 0}
                    className="text-red-500 hover:text-red-700 disabled:text-gray-400"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              ))}
              {metadataFields.length === 0 && (
                <p className="text-sm text-gray-500 italic">No metadata fields. Click &quot;Add Field&quot; to add some.</p>
              )}
            </div>
          </div>
        )}

      {selectedOperation === 'removeMetadata' && (
        <div>
          <span className="text-sm text-gray-600 mb-2 block">
            Metadata keys to remove (comma-separated):
          </span>
            <input
              type="text"
              placeholder="author,type,category"
              value={metadataKeysToRemove}
              onChange={(e) => handleKeysToRemoveChange(e.target.value)}
              disabled={disabled || totalDocuments === 0}
              className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm disabled:bg-gray-100"
            />
          <p className="text-xs text-gray-500 mt-1">
            Enter the metadata field names you want to remove, separated by commas.
          </p>
        </div>
      )}

      {selectedOperation === 'clearMetadata' && (
        <div>
          <p className="text-sm text-gray-700">
            This will remove <strong>all metadata</strong> from the selected documents.
          </p>
          <p className="text-xs text-gray-500 mt-2">
            Warning: This action cannot be undone. All custom metadata fields will be permanently removed.
          </p>
        </div>
      )}
    </div>
  )
});

DocumentBulkUpdateMetadata.displayName = 'DocumentBulkUpdateMetadata';