"use client";

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { Case, Tag } from '@docrouter/sdk';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { toast } from 'react-toastify';
import DocumentList from './DocumentList';
import { isColorLight } from '@/utils/colors';
import { formatLocalDate } from '@/utils/date';
import { caseDisplayName } from '@/utils/caseDisplayName';
import { useOrganization } from '@/contexts/OrganizationContext';
import { useSession } from 'next-auth/react';
import { isOrgAdmin } from '@/utils/roles';

type CaseDetailViewProps = {
  organizationId: string;
  caseId: string;
};

const CaseDetailView: React.FC<CaseDetailViewProps> = ({ organizationId, caseId }) => {
  const decodedCaseId = decodeURIComponent(caseId);
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const router = useRouter();
  const { currentOrganization } = useOrganization();
  const { data: session } = useSession();
  const canCascadeDelete = currentOrganization
    ? isOrgAdmin(currentOrganization, session)
    : false;

  const [caseRow, setCaseRow] = useState<Case | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [cascadeDelete, setCascadeDelete] = useState(false);

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
        toast.error(`Failed to load case: ${message}`);
      }
    } finally {
      setLoading(false);
    }
  }, [docRouterOrgApi, decodedCaseId]);

  useEffect(() => {
    void loadCase();
    void docRouterOrgApi.listTags({ limit: 200 }).then((r) => setTags(r.tags)).catch(() => {});
  }, [loadCase, docRouterOrgApi]);

  const tagById = useMemo(() => new Map(tags.map((t) => [t.id, t])), [tags]);

  const handleDelete = async () => {
    if (deleteConfirm !== decodedCaseId) {
      toast.error('Type the case ID exactly to confirm');
      return;
    }
    try {
      await docRouterOrgApi.deleteCase({ caseId: decodedCaseId, cascade: cascadeDelete });
      if (cascadeDelete) {
        toast.success('Case delete started (documents removed in background)');
        router.push(`/orgs/${organizationId}/cases`);
        return;
      }
      toast.success('Case deleted');
      router.push(`/orgs/${organizationId}/cases`);
    } catch (error) {
      toast.error(getApiErrorMsg(error) || 'Delete failed');
    }
  };

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
        <div className="flex gap-2">
          <Link
            href={`/orgs/${organizationId}/cases/${encodeURIComponent(decodedCaseId)}/edit`}
            className="px-3 py-2 border rounded text-sm hover:bg-gray-50"
          >
            Edit case
          </Link>
        </div>
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

      <div className="border rounded p-4 bg-white">
        <h2 className="text-lg font-semibold mb-3">Documents in this case</h2>
        <DocumentList organizationId={organizationId} fixedCaseId={decodedCaseId} hideCaseFilter />
      </div>

      <div className="border border-red-200 rounded p-4 bg-red-50 max-w-xl">
        <h3 className="font-semibold text-red-800 mb-2">Delete case</h3>
        <p className="text-sm text-red-700 mb-3">
          Default: documents are kept and removed from this case. Org admins may also delete all
          member documents (background job, returns 202).
        </p>
        {canCascadeDelete && (
          <label className="flex items-center gap-2 text-sm mb-3">
            <input
              type="checkbox"
              checked={cascadeDelete}
              onChange={(e) => setCascadeDelete(e.target.checked)}
            />
            Delete all documents in this case
          </label>
        )}
        <input
          type="text"
          className="w-full p-2 border rounded mb-2 text-sm"
          placeholder={`Type ${decodedCaseId} to confirm`}
          value={deleteConfirm}
          onChange={(e) => setDeleteConfirm(e.target.value)}
        />
        <button
          type="button"
          onClick={() => void handleDelete()}
          className="px-3 py-2 bg-red-600 text-white rounded text-sm hover:bg-red-700"
        >
          Delete case
        </button>
      </div>
    </div>
  );
};

export default CaseDetailView;
