"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { Tag } from '@docrouter/sdk';
import TagSelector from './TagSelector';
import { useRouter } from 'next/navigation';
import { toast } from 'react-toastify';
import InfoTooltip from '@/components/InfoTooltip';

const CaseCreate: React.FC<{ organizationId: string; caseId?: string }> = ({
  organizationId,
  caseId: editCaseId,
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [caseIdInput, setCaseIdInput] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [metadataFields, setMetadataFields] = useState<Array<{ id: string; key: string; value: string }>>([]);

  useEffect(() => {
    void docRouterOrgApi
      .listTags({ limit: 100 })
      .then((r) => setAvailableTags(r.tags))
      .catch((error) => {
        toast.error(getApiErrorMsg(error) || 'Failed to load tags');
      });
  }, [docRouterOrgApi]);

  useEffect(() => {
    async function load() {
      if (!editCaseId) return;
      setIsLoading(true);
      try {
        const c = await docRouterOrgApi.getCase({ caseId: decodeURIComponent(editCaseId) });
        setCaseIdInput(c.case_id);
        setDisplayName(c.display_name);
        setSelectedTagIds(c.tag_ids || []);
        setMetadataFields(
          Object.entries(c.metadata || {}).map(([key, value], index) => ({
            id: `field_${index}`,
            key,
            value,
          }))
        );
      } catch (error) {
        toast.error(getApiErrorMsg(error) || 'Error loading case');
      } finally {
        setIsLoading(false);
      }
    }
    void load();
  }, [editCaseId, docRouterOrgApi]);

  const metadataObject = () => {
    const out: Record<string, string> = {};
    for (const field of metadataFields) {
      const k = field.key.trim();
      const v = field.value.trim();
      if (k && v) out[k] = v;
    }
    return out;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const metadata = metadataObject();
      if (editCaseId) {
        await docRouterOrgApi.updateCase({
          caseId: decodeURIComponent(editCaseId),
          body: {
            display_name: displayName.trim() || undefined,
            tag_ids: selectedTagIds,
            metadata,
          },
        });
        toast.success('Case updated');
        router.push(`/orgs/${organizationId}/cases/${encodeURIComponent(decodeURIComponent(editCaseId))}`);
      } else {
        const created = await docRouterOrgApi.createCase({
          body: {
            case_id: caseIdInput.trim() || undefined,
            display_name: displayName.trim() || undefined,
            tag_ids: selectedTagIds,
            metadata,
          },
        });
        toast.success('Case created');
        router.push(`/orgs/${organizationId}/cases/${encodeURIComponent(created.case_id)}`);
      }
    } catch (error) {
      toast.error(getApiErrorMsg(error) || 'Error saving case');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow max-w-3xl">
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-xl font-bold">{editCaseId ? 'Edit case' : 'Create case'}</h2>
        <InfoTooltip
          title="About cases"
          content={
            <p>
              Cases group documents under a stable Case ID (similar to case collation in capture
              products). Assign documents on upload or from the document list.
            </p>
          }
        />
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Case ID</label>
          <input
            type="text"
            className="w-full p-2 border rounded disabled:bg-gray-100"
            value={caseIdInput}
            onChange={(e) => setCaseIdInput(e.target.value)}
            disabled={isLoading || Boolean(editCaseId)}
            placeholder="CLM-123"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Case Name</label>
          <input
            type="text"
            className="w-full p-2 border rounded"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            disabled={isLoading}
            placeholder="Optional; lists use Case ID when empty"
          />
        </div>
        <div>
          <h3 className="text-sm font-medium text-gray-900 mb-2">Tags</h3>
          <TagSelector
            availableTags={availableTags}
            selectedTagIds={selectedTagIds}
            onChange={setSelectedTagIds}
          />
        </div>
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-gray-900">Metadata</h3>
            <button
              type="button"
              className="text-sm text-blue-600"
              onClick={() =>
                setMetadataFields((prev) => [...prev, { id: `field_${Date.now()}`, key: '', value: '' }])
              }
            >
              Add field
            </button>
          </div>
          {metadataFields.map((field) => (
            <div key={field.id} className="flex gap-2 mb-2">
              <input
                className="flex-1 p-2 border rounded text-sm"
                placeholder="Key"
                value={field.key}
                onChange={(e) =>
                  setMetadataFields((prev) =>
                    prev.map((f) => (f.id === field.id ? { ...f, key: e.target.value } : f))
                  )
                }
              />
              <input
                className="flex-1 p-2 border rounded text-sm"
                placeholder="Value"
                value={field.value}
                onChange={(e) =>
                  setMetadataFields((prev) =>
                    prev.map((f) => (f.id === field.id ? { ...f, value: e.target.value } : f))
                  )
                }
              />
              <button
                type="button"
                className="text-red-600 text-sm px-2"
                onClick={() => setMetadataFields((prev) => prev.filter((f) => f.id !== field.id))}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          disabled={isLoading}
        >
          {editCaseId ? 'Save changes' : 'Create case'}
        </button>
      </form>
    </div>
  );
};

export default CaseCreate;
