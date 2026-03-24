import React, { useState, useEffect } from 'react';
import { Prompt } from '@docrouter/sdk';
import BadgeIcon from '@mui/icons-material/Badge';
import { DocRouterAccountApi } from '@/utils/api';
import DraggablePanel from '@/components/DraggablePanel';
import { formatLocalDateWithTZ } from '@/utils/date';

interface PromptInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
  prompt: Prompt;
}

const PromptInfoModal: React.FC<PromptInfoModalProps> = ({ 
  isOpen, 
  onClose, 
  prompt 
}) => {
  const [createdByName, setCreatedByName] = useState<string | null>(null);
  const [isLoadingName, setIsLoadingName] = useState(false);
  const docRouterAccountApi = React.useMemo(() => new DocRouterAccountApi(), []);

  useEffect(() => {
    if (isOpen && prompt.created_by) {
      setIsLoadingName(true);
      docRouterAccountApi.getUser(prompt.created_by)
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
  }, [isOpen, prompt.created_by, docRouterAccountApi]);

  if (!isOpen) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-[70] bg-black bg-opacity-50"
        onClick={onClose}
        role="presentation"
      />
      <DraggablePanel
        open
        resetToken={prompt.prompt_revid}
        anchorPercent={{ x: 50, y: 45 }}
        width="min(100vw - 32px, 42rem)"
        height="min(90vh, 820px)"
        zIndex={71}
        ariaLabel="Prompt properties"
        title={
          <>
            <BadgeIcon className="shrink-0 text-blue-600" fontSize="small" />
            <span className="truncate">Prompt Properties</span>
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
            <label className="text-sm font-semibold text-gray-700 block mb-1">Prompt Name</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">{prompt.name}</div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Version</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              v{prompt.prompt_version}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Prompt ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {prompt.prompt_id}
            </div>
            <p className="text-xs text-gray-500 mt-1">Stable identifier for this prompt</p>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Prompt Revision ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {prompt.prompt_revid}
            </div>
            <p className="text-xs text-gray-500 mt-1">Unique identifier for this version</p>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Created At</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {formatLocalDateWithTZ(prompt.created_at)}
            </div>
          </div>
          
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
          
          <div className="col-span-2">
            <label className="text-sm font-semibold text-gray-700 block mb-1">Created By ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {prompt.created_by}
            </div>
          </div>
        </div>
          </div>
        </div>
      </DraggablePanel>
    </>
  );
};

export default PromptInfoModal;
