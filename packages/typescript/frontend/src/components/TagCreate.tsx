"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { Tag } from '@docrouter/sdk';

// Type alias for tag creation/update (without id and timestamps)
type TagConfig = Omit<Tag, 'id' | 'created_at' | 'updated_at'>;
import colors from 'tailwindcss/colors';
import InfoTooltip from '@/components/InfoTooltip';
import { useRouter } from 'next/navigation';
import { toast } from 'react-toastify';
import BadgeIcon from '@mui/icons-material/Badge';
import TagInfoModal from '@/components/TagInfoModal';

const TagCreate: React.FC<{ organizationId: string, tagId?: string }> = ({ organizationId, tagId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [currentTag, setCurrentTag] = useState<{id?: string; name: string; color: string; description?: string}>({
    name: '',
    color: colors.blue[500], // default blue color
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
          toast.error(`Error loading tag: ${getApiErrorMsg(error)}`);
        } finally {
          setIsLoading(false);
        }
      } else {
        setCurrentTagFull(null);
        setCurrentTag({ name: '', color: colors.blue[500], description: '' });
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
      setCurrentTag({ name: '', color: colors.blue[500], description: '' });

      // Redirect to tags list page
      router.push(`/orgs/${organizationId}/tags`);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error saving tag';
      toast.error('Error: ' + errorMsg);
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
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <div className="hidden md:flex items-center gap-2 mb-4">
          <h2 className="text-xl font-bold">
            {currentTag.id ? 'Edit Tag' : 'Create Tag'}
          </h2>
          {currentTagFull && (
            <button
              onClick={() => setIsInfoModalOpen(true)}
              className="h-8 w-8 mb-2 flex items-center justify-center text-gray-600 hover:bg-gray-50 rounded-md transition-colors"
              title="Tag Properties"
            >
              <BadgeIcon className="text-lg" />
            </button>
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
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex flex-1 min-w-[300px] gap-2 items-center">
              {/* Tag Name label to the left */}
              <label htmlFor="tag-name" className="w-28 text-sm font-medium text-gray-700">
                Tag Name
              </label>
              <input
                id="tag-name"
                type="text"
                className="flex-1 p-2 border rounded disabled:bg-gray-100"
                value={currentTag.name}
                onChange={e => setCurrentTag({ ...currentTag, name: e.target.value })}
                placeholder="Tag Name"
                disabled={isLoading}
              />
              <div className="w-20 flex flex-col justify-end">
                <input
                  type="color"
                  className="w-full h-10 p-1 border rounded cursor-pointer"
                  value={currentTag.color}
                  onChange={e => setCurrentTag({ ...currentTag, color: e.target.value })}
                  disabled={isLoading}
                />
              </div>
            </div>
            <div className="flex gap-2 ml-auto">
              <button
                type="button"
                onClick={() => {
                  setCurrentTag({ name: '', color: colors.blue[500], description: '' });
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
                disabled={isLoading}
              >
                Clear
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={isLoading}
              >
                {currentTag.id ? 'Update Tag' : 'Save Tag'}
              </button>
            </div>
          </div>

          {/* Description label to the left */}
          <div className="flex items-center gap-2">
            <label htmlFor="tag-description" className="w-28 text-sm font-medium text-gray-700">
              Description
            </label>
            <input
              id="tag-description"
              type="text"
              className="flex-1 p-2 border rounded"
              value={currentTag.description}
              onChange={e => setCurrentTag({ ...currentTag, description: e.target.value })}
              placeholder="Description (optional)"
              disabled={isLoading}
            />
          </div>
        </form>
      </div>
      
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