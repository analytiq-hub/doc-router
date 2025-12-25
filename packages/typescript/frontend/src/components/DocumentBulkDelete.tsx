import { useState, forwardRef, useImperativeHandle, useMemo } from 'react'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import { DocRouterOrgApi } from '@/utils/api'
import { toast } from 'react-hot-toast'
import { Document, Tag } from '@docrouter/sdk';

interface DocumentBulkDeleteProps {
  organizationId: string
  searchParameters: {
    searchTerm: string
    selectedTagFilters: Tag[]
    metadataSearch: string
    paginationModel: { page: number; pageSize: number }
  }
  totalDocuments: number
  disabled?: boolean
  onProgress?: (processed: number, total: number) => void
  onComplete?: () => void
}

export interface DocumentBulkDeleteRef {
  executeDelete: () => Promise<void>
}

export const DocumentBulkDelete = forwardRef<DocumentBulkDeleteRef, DocumentBulkDeleteProps>(({
  organizationId,
  searchParameters,
  totalDocuments,
  onProgress,
  onComplete
}, ref) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [isDeleting, setIsDeleting] = useState(false)
  const [deletedCount, setDeletedCount] = useState(0)

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

  const handleBulkDelete = async () => {
    if (totalDocuments === 0) {
      toast.error('No documents to delete');
      return;
    }

    setIsDeleting(true);
    setDeletedCount(0);

    try {
      let successCount = 0;
      let failureCount = 0;
      const limit = 100;
      const BATCH_SIZE = 10; // Maximum concurrent deletions

      // Always fetch from skip=0 since documents shift as they're deleted
      // This ensures we process all remaining documents that match the filter
      while (true) {
        // Fetch next batch of documents (always from the beginning)
        const batchResponse = await docRouterOrgApi.listDocuments({
          skip: 0,
          limit,
          nameSearch: searchParameters.searchTerm.trim() || undefined,
          tagIds: searchParameters.selectedTagFilters.length > 0
            ? searchParameters.selectedTagFilters.map(tag => tag.id).join(',')
            : undefined,
          metadataSearch: searchParameters.metadataSearch.trim()
            ? parseAndEncodeMetadataSearch(searchParameters.metadataSearch.trim()) || undefined
            : undefined,
        });

        const documentsInBatch = batchResponse.documents;

        // If no documents are returned, we're done
        if (documentsInBatch.length === 0) {
          break;
        }

        // Process documents in batches of BATCH_SIZE
        for (let i = 0; i < documentsInBatch.length; i += BATCH_SIZE) {
          const batch = documentsInBatch.slice(i, i + BATCH_SIZE);

          const deletePromises = batch.map(async (doc: Document) => {
            try {
              await docRouterOrgApi.deleteDocument({
                documentId: doc.id
              });
              return { success: true, name: doc.document_name };
            } catch (error) {
              console.error(`Failed to delete document ${doc.document_name}:`, error);
              return { success: false, name: doc.document_name };
            }
          });

          const results = await Promise.all(deletePromises);

          // Count successes and failures
          results.forEach(result => {
            if (result.success) {
              successCount++;
            } else {
              failureCount++;
            }
          });

          const newTotal = successCount + failureCount;
          setDeletedCount(newTotal);
          if (onProgress) {
            onProgress(newTotal, totalDocuments);
          }

          // Add a small delay between batches to prevent overwhelming the server
          if (i + BATCH_SIZE < documentsInBatch.length) {
            await new Promise(resolve => setTimeout(resolve, 100));
          }
        }

        // Continue fetching from skip=0 until no more documents are returned
        // As documents are deleted, remaining documents shift to fill the gaps
      }

      if (successCount > 0) {
        toast.success(`Successfully deleted ${successCount} document${successCount !== 1 ? 's' : ''}`);
      }

      if (failureCount > 0) {
        toast.error(`Failed to delete ${failureCount} document${failureCount !== 1 ? 's' : ''}`);
      }

      if (onComplete) {
        onComplete();
      }

    } catch (error) {
      console.error('Bulk delete error:', error);
      toast.error('Failed to perform bulk delete');
    } finally {
      setIsDeleting(false);
      setDeletedCount(0);
    }
  }

  useImperativeHandle(ref, () => ({
    executeDelete: handleBulkDelete
  }));

  return (
    <div>
      <div className="flex items-start gap-3 mb-4">
        <div className="flex-shrink-0 mt-1">
          <ExclamationTriangleIcon className="h-6 w-6 text-red-500" />
        </div>
        <div className="flex-1">
          <p className="text-sm text-red-700 font-medium">
            This will <strong>permanently delete</strong> all matching documents.
          </p>
          <p className="text-xs text-red-500 mt-2">
            ⚠️ Warning: This action cannot be undone. All document data, metadata, and associated files will be permanently removed from the system.
          </p>
          <p className="text-xs text-gray-500 mt-2">
            Deletions are processed in batches of 10 for optimal performance.
          </p>
        </div>
      </div>

      {isDeleting && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-red-700">
              Deleting Documents...
            </span>
            <span className="text-sm text-red-600">
              {deletedCount} / {totalDocuments}
            </span>
          </div>
          <div className="w-full bg-red-200 rounded-full h-2">
            <div
              className="bg-red-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${totalDocuments > 0 ? (deletedCount / totalDocuments) * 100 : 0}%` }}
            ></div>
          </div>
          <p className="text-xs text-red-500 mt-2">
            {deletedCount === totalDocuments && deletedCount > 0
              ? 'Finalizing deletion...'
              : 'Please wait while documents are being deleted'}
          </p>
        </div>
      )}

    </div>
  )
});

DocumentBulkDelete.displayName = 'DocumentBulkDelete';