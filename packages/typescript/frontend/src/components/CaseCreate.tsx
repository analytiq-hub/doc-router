"use client";

import { toastActionError } from '@/utils/toastActionError';
import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { useRouter } from '@/utils/appRouter';
import { toast } from 'react-toastify';
import InfoTooltip from '@/components/InfoTooltip';
import { useOrgAllTags } from '@/api/orgQueries';
import { TagCheckboxList } from '@/components/TagCheckboxList';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldContent, FieldDescription, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';

const CaseCreate: React.FC<{ organizationId: string; caseId?: string }> = ({
  organizationId,
  caseId: editCaseId,
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const { data: availableTags = [] } = useOrgAllTags(organizationId);
  const [caseIdInput, setCaseIdInput] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [metadataFields, setMetadataFields] = useState<Array<{ id: string; key: string; value: string }>>([]);

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
        toastActionError('Failed to load case', error);
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
      toastActionError('Failed to save case', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="max-w-3xl">
      <CardHeader className="flex flex-row items-center gap-2 space-y-0">
        <CardTitle>{editCaseId ? 'Edit case' : 'Create case'}</CardTitle>
        <InfoTooltip
          title="About cases"
          content={
            <p>
              Cases group documents under a stable Case ID (similar to case collation in capture
              products). Assign documents on upload or from the document list.
            </p>
          }
        />
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          <Field>
            <FieldLabel htmlFor="case-id">Case ID</FieldLabel>
            <FieldContent>
              <Input
                id="case-id"
                value={caseIdInput}
                onChange={(e) => setCaseIdInput(e.target.value)}
                disabled={isLoading || Boolean(editCaseId)}
                placeholder="CLM-123"
              />
            </FieldContent>
          </Field>
          <Field>
            <FieldLabel htmlFor="case-name">Case name</FieldLabel>
            <FieldContent>
              <Input
                id="case-name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                disabled={isLoading}
                placeholder="Optional; lists use Case ID when empty"
              />
            </FieldContent>
          </Field>
          <Field>
            <FieldLabel>Tags</FieldLabel>
            <FieldContent>
              <TagCheckboxList
                tags={availableTags}
                selectedIds={selectedTagIds}
                onChange={setSelectedTagIds}
                disabled={isLoading}
              />
            </FieldContent>
          </Field>
          <Field>
            <div className="flex items-center justify-between">
              <FieldLabel>Metadata</FieldLabel>
              <Button
                type="button"
                variant="link"
                size="sm"
                className="h-auto px-0"
                onClick={() =>
                  setMetadataFields((prev) => [...prev, { id: `field_${Date.now()}`, key: '', value: '' }])
                }
              >
                Add field
              </Button>
            </div>
            <FieldContent className="space-y-2">
              {metadataFields.map((field) => (
                <div key={field.id} className="flex gap-2">
                  <Input
                    className="flex-1"
                    placeholder="Key"
                    value={field.key}
                    onChange={(e) =>
                      setMetadataFields((prev) =>
                        prev.map((f) => (f.id === field.id ? { ...f, key: e.target.value } : f))
                      )
                    }
                    disabled={isLoading}
                  />
                  <Input
                    className="flex-1"
                    placeholder="Value"
                    value={field.value}
                    onChange={(e) =>
                      setMetadataFields((prev) =>
                        prev.map((f) => (f.id === field.id ? { ...f, value: e.target.value } : f))
                      )
                    }
                    disabled={isLoading}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-destructive shrink-0"
                    onClick={() => setMetadataFields((prev) => prev.filter((f) => f.id !== field.id))}
                  >
                    Remove
                  </Button>
                </div>
              ))}
              {!metadataFields.length ? (
                <FieldDescription>No metadata fields yet.</FieldDescription>
              ) : null}
            </FieldContent>
          </Field>
          <Button type="submit" disabled={isLoading}>
            {editCaseId ? 'Save changes' : 'Create case'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};

export default CaseCreate;
