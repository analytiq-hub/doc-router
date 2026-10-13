import { forwardRef, useImperativeHandle, useMemo, useState } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { toast } from 'react-hot-toast';
import { CaseAssignmentFields } from './CaseAssignmentFields';
import { buildListDocumentsQuery, DocumentListSearchParameters } from '@/utils/documentListQuery';

// Matches the server's per-transaction assign limit.
const ASSIGN_BATCH_SIZE = 1000;
// Removal has no batch endpoint; send this many PUTs at a time.
const REMOVE_CONCURRENCY = 8;

export interface DocumentBulkUpdateCaseRef {
  executeCase: (operation: string) => Promise<void>;
}

type DocumentBulkUpdateCaseProps = {
  organizationId: string;
  searchParameters: DocumentListSearchParameters;
  totalDocuments: number;
  selectedOperation: string;
  onDataChange: (data: { caseId: string; createCaseIfMissing: boolean } | null) => void;
  onProgress?: (processed: number, total: number) => void;
  onComplete?: () => void;
  disabled?: boolean;
};

export const DocumentBulkUpdateCase = forwardRef<DocumentBulkUpdateCaseRef, DocumentBulkUpdateCaseProps>(
  (
    {
      organizationId,
      searchParameters,
      totalDocuments,
      selectedOperation,
      onDataChange,
      onProgress,
      onComplete,
      disabled = false,
    },
    ref
  ) => {
    const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
    const [caseId, setCaseId] = useState('');
    const [createCaseIfMissing, setCreateCaseIfMissing] = useState(false);

    const handleCaseChange = (value: string) => {
      setCaseId(value);
      onDataChange(
        selectedOperation === 'removeFromCase'
          ? null
          : { caseId: value, createCaseIfMissing }
      );
    };

    const handleCreateChange = (value: boolean) => {
      setCreateCaseIfMissing(value);
      onDataChange({ caseId, createCaseIfMissing: value });
    };

    // Collect every matching id before changing anything. Assign and remove change
    // case_id, which the filter may use, so paging while updating would skip documents.
    const collectDocumentIds = async (): Promise<string[]> => {
      const ids: string[] = [];
      const limit = 1000;
      for (let skip = 0; ; skip += limit) {
        const batchResponse = await docRouterOrgApi.listDocuments(
          buildListDocumentsQuery(searchParameters, skip, limit)
        );
        ids.push(...batchResponse.documents.map((doc) => doc.id));
        if (batchResponse.documents.length < limit) break;
      }
      return ids;
    };

    const runBulk = async (operation: string) => {
      const targetCaseId = caseId.trim();
      if (operation === 'assignToCase' && !targetCaseId) {
        toast.error('Case ID is required');
        return;
      }

      let documentIds: string[];
      try {
        documentIds = await collectDocumentIds();
      } catch (error) {
        toast.error(`Failed to list documents: ${getApiErrorMsg(error)}`);
        return;
      }

      let processed = 0;
      let failed = 0;
      let firstError: string | null = null;
      const recordFailure = (error: unknown, count: number) => {
        failed += count;
        firstError ??= getApiErrorMsg(error);
      };

      if (operation === 'assignToCase') {
        // One request per 1000 documents; the server assigns each batch in one transaction.
        for (let start = 0; start < documentIds.length; start += ASSIGN_BATCH_SIZE) {
          const batch = documentIds.slice(start, start + ASSIGN_BATCH_SIZE);
          try {
            await docRouterOrgApi.assignDocumentsToCase({
              caseId: targetCaseId,
              documentIds: batch,
              createCaseIfMissing,
            });
            processed += batch.length;
          } catch (error) {
            recordFailure(error, batch.length);
            // Unknown or deleting case fails every batch the same way.
            break;
          }
          onProgress?.(processed, totalDocuments);
        }
      } else if (operation === 'removeFromCase') {
        for (let start = 0; start < documentIds.length; start += REMOVE_CONCURRENCY) {
          const batch = documentIds.slice(start, start + REMOVE_CONCURRENCY);
          const results = await Promise.allSettled(
            batch.map((documentId) => docRouterOrgApi.updateDocument({ documentId, caseId: null }))
          );
          for (const result of results) {
            if (result.status === 'fulfilled') processed += 1;
            else recordFailure(result.reason, 1);
          }
          onProgress?.(processed, totalDocuments);
        }
      }

      if (failed > 0) {
        toast.error(
          `Updated case membership for ${processed} document(s); ${failed} failed: ${firstError}`
        );
      } else {
        toast.success(`Updated case membership for ${processed} document(s)`);
      }
      onComplete?.();
    };

    useImperativeHandle(ref, () => ({
      executeCase: runBulk,
    }));

    if (selectedOperation === 'removeFromCase') {
      return (
        <p className="text-sm text-gray-600">
          Remove all filtered documents from their cases. Documents are not deleted.
        </p>
      );
    }

    return (
      <CaseAssignmentFields
        caseId={caseId}
        onCaseIdChange={handleCaseChange}
        createCaseIfMissing={createCaseIfMissing}
        onCreateCaseIfMissingChange={handleCreateChange}
        disabled={disabled}
      />
    );
  }
);

DocumentBulkUpdateCase.displayName = 'DocumentBulkUpdateCase';
