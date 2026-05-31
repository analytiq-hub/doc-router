import { useState, forwardRef, useImperativeHandle, useMemo } from 'react'
import { Tag } from '@docrouter/sdk';
import TagSelector from './TagSelector';
import { DocRouterOrgApi } from '@/utils/api';
import { toast } from 'react-hot-toast';

interface DocumentBulkUpdateTagsProps {
  availableTags: Tag[]
  totalDocuments: number
  onDataChange: (data: string[]) => void
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

export interface DocumentBulkUpdateTagsRef {
  executeTags: (operation: string) => Promise<void>
}

export const DocumentBulkUpdateTags = forwardRef<DocumentBulkUpdateTagsRef, DocumentBulkUpdateTagsProps>(({
  availableTags,
  totalDocuments,
  onDataChange,
  disabled = false,
  selectedOperation = 'addTags',
  organizationId,
  searchParameters,
  onProgress,
  onComplete
}, ref) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([])

  const handleTagChange = (tagIds: string[]) => {
    setSelectedTagIds(tagIds)
    onDataChange(tagIds)
  }


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

  const handleBulkTagsUpdate = async (operation: string) => {
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
            let updatedTagIds = [...doc.tag_ids];

            if (operation === 'addTags') {
              // Add new tags (avoiding duplicates)
              for (const tagId of selectedTagIds) {
                if (!updatedTagIds.includes(tagId)) {
                  updatedTagIds.push(tagId);
                }
              }
            } else if (operation === 'removeTags') {
              // Remove specified tags
              updatedTagIds = doc.tag_ids.filter((tagId: string) => !selectedTagIds.includes(tagId));
            }

            await docRouterOrgApi.updateDocument({
              documentId: doc.id,
              tagIds: updatedTagIds,
              metadata: doc.metadata || {}
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
        const message = operation === 'addTags'
          ? `Tags added to ${successCount} document${successCount !== 1 ? 's' : ''}`
          : `Tags removed from ${successCount} document${successCount !== 1 ? 's' : ''}`;
        toast.success(message);
      }

      if (failureCount > 0) {
        toast.error(`Failed to update ${failureCount} document${failureCount !== 1 ? 's' : ''}`);
      }

      if (onComplete) {
        onComplete();
      }
    } catch (error) {
      console.error('Bulk tags update error:', error);
      toast.error('Failed to perform bulk tag update');
    }
  };

  useImperativeHandle(ref, () => ({
    executeTags: handleBulkTagsUpdate
  }));

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-2">
        {selectedOperation === 'addTags' ? 'Select tags to add:' : 'Select tags to remove:'}
      </label>
      <TagSelector
        availableTags={availableTags}
        selectedTagIds={selectedTagIds}
        onChange={handleTagChange}
        disabled={disabled || totalDocuments === 0}
      />
    </div>
  )
});

DocumentBulkUpdateTags.displayName = 'DocumentBulkUpdateTags';