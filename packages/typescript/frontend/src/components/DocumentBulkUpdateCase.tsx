import { forwardRef, useImperativeHandle, useMemo, useState } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { toast } from 'react-hot-toast';
import { CaseAssignmentFields } from './CaseAssignmentFields';
import { buildListDocumentsQuery, DocumentListSearchParameters } from '@/utils/documentListQuery';

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

    const runBulk = async (operation: string) => {
      let processed = 0;
      let skip = 0;
      const limit = 1000;

      while (true) {
        const batchResponse = await docRouterOrgApi.listDocuments(
          buildListDocumentsQuery(searchParameters, skip, limit)
        );
        const batch = batchResponse.documents;
        if (batch.length === 0) break;

        for (const doc of batch) {
          try {
            if (operation === 'assignToCase') {
              const trimmed = caseId.trim();
              if (!trimmed) {
                toast.error('Case ID is required');
                return;
              }
              await docRouterOrgApi.updateDocument({
                documentId: doc.id,
                caseId: trimmed,
                createCaseIfMissing,
              });
            } else if (operation === 'removeFromCase') {
              await docRouterOrgApi.updateDocument({
                documentId: doc.id,
                caseId: null,
              });
            }
            processed += 1;
            onProgress?.(processed, totalDocuments);
          } catch {
            // continue with next doc
          }
        }

        skip += batch.length;
        if (batch.length < limit) break;
      }

      toast.success(`Updated case membership for ${processed} document(s)`);
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
