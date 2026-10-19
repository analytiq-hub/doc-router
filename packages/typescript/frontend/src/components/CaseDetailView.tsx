"use client";

import { toastActionError } from '@/utils/toastActionError';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { Case, Tag } from '@docrouter/sdk';
import Link from 'next/link';
import { toast } from 'react-toastify';
import DocumentList from './DocumentList';
import CaseResultsSidebar from './CaseResultsSidebar';
import { isColorLight } from '@/utils/colors';
import { formatLocalDate } from '@/utils/date';
import { caseDisplayName } from '@/utils/caseDisplayName';
import { fetchAllOrgTags } from '@/utils/fetchAllOrgTags';
import { useOrgCapability } from '@/hooks/useOrgPermissions';
import { CAP_DOCUMENTS_WRITE } from '@/utils/orgCapabilities';
import CaseDeleteDialog from '@/components/CaseDeleteDialog';
import { useRouter } from 'next/navigation';

type CaseDetailViewProps = {
  organizationId: string;
  caseId: string;
};

const CaseDetailView: React.FC<CaseDetailViewProps> = ({ organizationId, caseId }) => {
  const decodedCaseId = decodeURIComponent(caseId);
  const router = useRouter();
  const { hasCapability: canWriteDocuments } = useOrgCapability(
    organizationId,
    CAP_DOCUMENTS_WRITE,
  );
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const [caseRow, setCaseRow] = useState<Case | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'documents' | 'results'>('documents');

  const loadCase = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const c = await docRouterOrgApi.getCase({ caseId: decodedCaseId });
      setCaseRow(c);
    } catch (error) {
      setCaseRow(null);
      // 404 means no such case (or it is being deleted); anything else is a real error.
      if ((error as { status?: number }).status !== 404) {
        const message = getApiErrorMsg(error);
        setLoadError(message);
        toastActionError('Failed to load case', error);
      }
    } finally {
      setLoading(false);
    }
  }, [docRouterOrgApi, decodedCaseId]);

  useEffect(() => {
    void loadCase();
    void fetchAllOrgTags(docRouterOrgApi)
      .then(setTags)
      .catch((error) => toastActionError('Failed to load tags', error));
  }, [loadCase, docRouterOrgApi]);

  const tagById = useMemo(() => new Map(tags.map((t) => [t.id, t])), [tags]);

  if (loading) {
    return <p className="p-4">Loading case…</p>;
  }

  if (!caseRow) {
    return (
      <div className="p-4">
        <p className="text-gray-600">
          {loadError
            ? `Could not load this case: ${loadError}`
            : 'Case not found or still being deleted.'}
        </p>
        <Link href={`/orgs/${organizationId}/cases`} className="text-blue-600 underline">
          Back to cases
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href={`/orgs/${organizationId}/cases`} className="text-sm text-blue-600 underline">
            ← Cases
          </Link>
          <h1 className="text-2xl font-bold mt-1">{caseDisplayName(caseRow)}</h1>
          {caseDisplayName(caseRow) !== caseRow.case_id && (
            <p className="text-sm text-gray-600 font-mono">{caseRow.case_id}</p>
          )}
          <p className="text-sm text-gray-500 mt-1">
            {caseRow.document_count} document(s) · Updated {formatLocalDate(caseRow.updated_at)}
          </p>
        </div>
        {canWriteDocuments && (
          <div className="flex gap-2">
            <Link
              href={`/orgs/${organizationId}/cases/${encodeURIComponent(decodedCaseId)}/edit`}
              className="px-3 py-2 border rounded text-sm hover:bg-gray-50"
            >
              Edit case
            </Link>
            <button
              type="button"
              className="px-3 py-2 border border-red-200 text-red-700 rounded text-sm hover:bg-red-50"
              onClick={() => setDeleteDialogOpen(true)}
            >
              Delete case
            </button>
          </div>
        )}
      </div>

      {(caseRow.tag_ids?.length ?? 0) > 0 && (
        <div className="flex flex-wrap gap-2">
          {caseRow.tag_ids.map((tid) => {
            const tag = tagById.get(tid);
            if (!tag) return null;
            return (
              <span
                key={tid}
                className={`px-2 py-0.5 rounded text-sm ${
                  isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
                }`}
                style={{ backgroundColor: tag.color }}
              >
                {tag.name}
              </span>
            );
          })}
        </div>
      )}

      {Object.keys(caseRow.metadata || {}).length > 0 && (
        <div className="bg-gray-50 rounded p-3 text-sm">
          <h3 className="font-medium mb-2">Metadata</h3>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {Object.entries(caseRow.metadata).map(([k, v]) => (
              <div key={k}>
                <dt className="text-gray-500">{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      <div className="border-b flex gap-4 text-sm">
        <button
          type="button"
          className={`pb-2 border-b-2 ${
            activeTab === 'documents'
              ? 'border-blue-600 text-blue-700 font-medium'
              : 'border-transparent text-gray-600'
          }`}
          onClick={() => setActiveTab('documents')}
        >
          Documents
        </button>
        <button
          type="button"
          className={`pb-2 border-b-2 ${
            activeTab === 'results'
              ? 'border-blue-600 text-blue-700 font-medium'
              : 'border-transparent text-gray-600'
          }`}
          onClick={() => setActiveTab('results')}
        >
          Results
        </button>
      </div>

      {activeTab === 'documents' ? (
        <div className="border rounded p-4 bg-white">
          <h2 className="text-lg font-semibold mb-3">Documents in this case</h2>
          <DocumentList organizationId={organizationId} fixedCaseId={decodedCaseId} hideCaseFilter />
        </div>
      ) : (
        <div className="border rounded bg-white overflow-hidden min-h-[32rem] flex flex-col md:flex-row">
          <div className="w-full md:w-[min(100%,28rem)] md:max-w-md flex-shrink-0 min-h-[32rem]">
            <CaseResultsSidebar
              organizationId={organizationId}
              caseId={decodedCaseId}
              caseTagIds={caseRow.tag_ids ?? []}
            />
          </div>
          <div className="hidden md:flex flex-1 items-center justify-center bg-gray-50/80 text-sm text-gray-500 border-t md:border-t-0 md:border-l border-black/10 p-8 text-center">
            Expand a prompt to view case-level extraction fields (same layout as document Extraction).
          </div>
        </div>
      )}

      {caseRow && (
        <CaseDeleteDialog
          open={deleteDialogOpen}
          organizationId={organizationId}
          caseRow={caseRow}
          canCascadeDelete={canWriteDocuments}
          onClose={() => setDeleteDialogOpen(false)}
          onDeleted={() => {
            router.push(`/orgs/${organizationId}/cases`);
          }}
        />
      )}
    </div>
  );
};

export default CaseDetailView;
