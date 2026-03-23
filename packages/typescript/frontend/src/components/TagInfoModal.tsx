import React, { useState, useEffect } from 'react';
import { Tag } from '@docrouter/sdk';
import BadgeIcon from '@mui/icons-material/Badge';
import { DocRouterAccountApi } from '@/utils/api';
import { isColorLight } from '@/utils/colors';
import DraggablePanel from '@/components/DraggablePanel';

// Extended Tag type that includes optional fields that may be present in API responses
// created_by is not in the TypeScript Tag interface but may be returned by the API
// updated_at is required in Tag but may be missing in some responses
interface TagWithOptionalFields extends Omit<Tag, 'updated_at'> {
  created_by?: string;
  updated_at?: string;
}

interface TagInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
  tag: TagWithOptionalFields;
}

const TagInfoModal: React.FC<TagInfoModalProps> = ({ 
  isOpen, 
  onClose, 
  tag 
}) => {
  const [createdByName, setCreatedByName] = useState<string | null>(null);
  const [isLoadingName, setIsLoadingName] = useState(false);
  const docRouterAccountApi = React.useMemo(() => new DocRouterAccountApi(), []);

  // Check if tag has created_by field (it might not be in the TypeScript interface but could be in the response)
  const createdBy = tag.created_by;

  useEffect(() => {
    if (isOpen && createdBy) {
      setIsLoadingName(true);
      docRouterAccountApi.getUser(createdBy)
        .then(user => {
          setCreatedByName(user.name || null);
        })
        .catch(error => {
          console.error('Error fetching user name:', error);
          setCreatedByName(null);
        })
        .finally(() => {
          setIsLoadingName(false);
        });
    } else {
      setCreatedByName(null);
    }
  }, [isOpen, createdBy, docRouterAccountApi]);

  if (!isOpen) return null;

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateString;
    }
  };

  const bgColor = tag.color;
  const textColor = isColorLight(bgColor) ? 'text-gray-800' : 'text-white';

  return (
    <>
      <div
        className="fixed inset-0 z-[70] bg-black bg-opacity-50"
        onClick={onClose}
        role="presentation"
      />
      <DraggablePanel
        open
        resetToken={tag.id}
        anchorPercent={{ x: 50, y: 45 }}
        width="min(100vw - 32px, 42rem)"
        height="min(90vh, 820px)"
        zIndex={71}
        ariaLabel="Tag properties"
        title={
          <>
            <BadgeIcon className="shrink-0 text-blue-600" fontSize="small" />
            <span className="truncate">Tag Properties</span>
          </>
        }
        headerActions={
          <button
            type="button"
            onClick={onClose}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs text-white hover:bg-blue-700"
          >
            Close
          </button>
        }
      >
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-6 pt-2">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Tag Name</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">{tag.name}</div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Color</label>
            <div className="flex items-center gap-2">
              <div 
                className={`px-3 py-1 rounded shadow-sm ${textColor} font-medium`}
                style={{ backgroundColor: bgColor }}
              >
                {tag.name}
              </div>
              <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm">
                {tag.color}
              </div>
            </div>
          </div>
          
          <div className="col-span-2">
            <label className="text-sm font-semibold text-gray-700 block mb-1">Description</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {tag.description || <span className="text-gray-500 italic">No description</span>}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Tag ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {tag.id}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Created At</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {formatDate(tag.created_at)}
            </div>
          </div>
          
          {createdBy && (
            <>
              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">Created By Name</label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {isLoadingName ? (
                    <span className="text-gray-500 italic">Loading...</span>
                  ) : createdByName ? (
                    createdByName
                  ) : (
                    <span className="text-gray-500 italic">Not available</span>
                  )}
                </div>
              </div>
              
              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">Created By ID</label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
                  {createdBy}
                </div>
              </div>
            </>
          )}
          
          {tag.updated_at && (
            <div>
              <label className="text-sm font-semibold text-gray-700 block mb-1">Updated At</label>
              <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                {formatDate(tag.updated_at)}
              </div>
            </div>
          )}
        </div>
          </div>
        </div>
      </DraggablePanel>
    </>
  );
};

export default TagInfoModal;
