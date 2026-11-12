"use client";

import { toastActionError } from '@/utils/toastActionError';
import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { Tag } from '@docrouter/sdk';

// Type alias for tag creation/update (without id and timestamps)
type TagConfig = Omit<Tag, 'id' | 'created_at' | 'updated_at'>;
import { designTokens } from '@/lib/designTokens';
import InfoTooltip from '@/components/InfoTooltip';
import { useRouter } from '@/utils/appRouter';
import { toast } from 'react-toastify';
import { IdCard } from 'lucide-react';
import TagInfoModal from '@/components/TagInfoModal';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldContent, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';

const TagCreate: React.FC<{ organizationId: string, tagId?: string }> = ({ organizationId, tagId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [currentTag, setCurrentTag] = useState<{id?: string; name: string; color: string; description?: string}>({
    name: '',
    color: designTokens.brand, // default blue color
    description: ''
  });

  const [isLoading, setIsLoading] = useState(false);
  const [currentTagFull, setCurrentTagFull] = useState<Tag | null>(null);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const router = useRouter();

  // Load editing tag if available
  useEffect(() => {
    async function loadTag() {
      if (tagId) {
        setIsLoading(true);
        try {
          const tag = await docRouterOrgApi.getTag({ tagId });
          setCurrentTagFull(tag);
          setCurrentTag({
            id: tag.id,
            name: tag.name,
            color: tag.color,
            description: tag.description || ''
          });
        } catch (error) {
          // setMessage(`Error loading tag: ${getApiErrorMsg(error)}`);
          toastActionError('Failed to load tag', error);
        } finally {
          setIsLoading(false);
        }
      } else {
        setCurrentTagFull(null);
        setCurrentTag({ name: '', color: designTokens.brand, description: '' });
      }
    }
    loadTag();
  }, [tagId, docRouterOrgApi]);

  const saveTag = async (tag: TagConfig) => {
    try {
      setIsLoading(true);
      
      if (currentTag.id) {
        // Update existing tag
        await docRouterOrgApi.updateTag({
          tagId: currentTag.id,
          tag: tag
        });
      } else {
        // Create new tag
        await docRouterOrgApi.createTag({ 
          tag: tag
        });
      }
      
      // Reset form only after successful save
      setCurrentTag({ name: '', color: designTokens.brand, description: '' });

      // Redirect to tags list page
      router.push(`/orgs/${organizationId}/tags`);
    } catch (error) {
      toastActionError('Failed to save tag', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentTag.name) {
      toast.error('Please fill in the tag name');
      return;
    }

    saveTag(currentTag);
  };

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <Card className="mb-6">
        <CardHeader className="hidden flex-row items-center gap-2 space-y-0 md:flex">
          <CardTitle>{currentTag.id ? 'Edit tag' : 'Create tag'}</CardTitle>
          {currentTagFull && (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => setIsInfoModalOpen(true)}
              title="Tag properties"
            >
              <IdCard className="size-5" />
            </Button>
          )}
          <InfoTooltip 
            title="About Tags"
            content={
              <>
                <p className="mb-2">
                  Tags can be assigned to documents and prompts.
                </p>
                <ul className="list-disc list-inside space-y-1 mb-2">
                  <li>Create tags for different types of documents, or different types of data you want to extract.</li>
                  <li>Assign tags to prompts to control which documents they process.</li>
                  <li>Assign tags when uploading documents.</li>
                </ul>
              </>
            }
          />
        </CardHeader>
        <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex flex-wrap items-end gap-4">
            <Field className="min-w-[200px] flex-1">
              <FieldLabel htmlFor="tag-name">Tag name</FieldLabel>
              <FieldContent className="flex gap-2">
                <Input
                  id="tag-name"
                  value={currentTag.name}
                  onChange={(e) => setCurrentTag({ ...currentTag, name: e.target.value })}
                  placeholder="Tag name"
                  disabled={isLoading}
                />
                <Input
                  type="color"
                  className="h-9 w-14 shrink-0 cursor-pointer p-1"
                  value={currentTag.color}
                  onChange={(e) => setCurrentTag({ ...currentTag, color: e.target.value })}
                  disabled={isLoading}
                  aria-label="Tag color"
                />
              </FieldContent>
            </Field>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setCurrentTag({ name: '', color: designTokens.brand, description: '' })}
                disabled={isLoading}
              >
                Clear
              </Button>
              <Button type="submit" disabled={isLoading}>
                {currentTag.id ? 'Update tag' : 'Save tag'}
              </Button>
            </div>
          </div>

          <Field>
            <FieldLabel htmlFor="tag-description">Description</FieldLabel>
            <FieldContent>
              <Input
                id="tag-description"
                value={currentTag.description}
                onChange={(e) => setCurrentTag({ ...currentTag, description: e.target.value })}
                placeholder="Description (optional)"
                disabled={isLoading}
              />
            </FieldContent>
          </Field>
        </form>
        </CardContent>
      </Card>
      
      {/* Info Modal */}
      {currentTagFull && (
        <TagInfoModal
          isOpen={isInfoModalOpen}
          onClose={() => setIsInfoModalOpen(false)}
          tag={currentTagFull}
        />
      )}
    </div>
  );
};

export default TagCreate; 