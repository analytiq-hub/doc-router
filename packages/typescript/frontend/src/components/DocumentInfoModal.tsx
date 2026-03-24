import React, { useState, useEffect } from 'react';
import { Document, Tag } from '@docrouter/sdk';
import BadgeIcon from '@mui/icons-material/Badge';
import { DocRouterAccountApi } from '@/utils/api';
import { isColorLight } from '@/utils/colors';
import DraggablePanel from '@/components/DraggablePanel';
import { formatLocalDateWithTZ } from '@/utils/date';

interface DocumentInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: Document;
  availableTags?: Tag[];
}

const DocumentInfoModal: React.FC<DocumentInfoModalProps> = ({ 
  isOpen, 
  onClose, 
  document,
  availableTags = []
}) => {
  const [uploadedByUserId, setUploadedByUserId] = useState<string | null>(null);
  const [isLoadingUserId, setIsLoadingUserId] = useState(false);
  const docRouterAccountApi = React.useMemo(() => new DocRouterAccountApi(), []);

  useEffect(() => {
    // document.uploaded_by contains the user's name, not ID
    // We need to search for the user by name to get their ID
    if (isOpen && document.uploaded_by) {
      setIsLoadingUserId(true);
      docRouterAccountApi.listUsers({ search_name: document.uploaded_by, limit: 1 })
        .then(response => {
          // Find exact match by name (case-insensitive)
          const user = response.users.find(u => 
            u.name?.toLowerCase() === document.uploaded_by.toLowerCase()
          );
          if (user) {
            setUploadedByUserId(user.id);
          } else {
            setUploadedByUserId(null);
          }
        })
        .catch(error => {
          console.error('Error fetching user ID:', error);
          setUploadedByUserId(null);
        })
        .finally(() => {
          setIsLoadingUserId(false);
        });
    } else {
      setUploadedByUserId(null);
    }
  }, [isOpen, document.uploaded_by, docRouterAccountApi]);

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
        resetToken={document.id}
        anchorPercent={{ x: 50, y: 45 }}
        width="min(100vw - 32px, 42rem)"
        height="min(90vh, 820px)"
        zIndex={71}
        ariaLabel="Document properties"
        title={
          <>
            <BadgeIcon className="shrink-0 text-blue-600" fontSize="small" />
            <span className="truncate">Document Properties</span>
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
            <label className="text-sm font-semibold text-gray-700 block mb-1">Document Name</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">{document.document_name}</div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">State</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">{document.state}</div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Document ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {document.id}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">PDF ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {document.pdf_id}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Type</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {document.type || <span className="text-gray-500 italic">Not specified</span>}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Upload Date</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {formatLocalDateWithTZ(document.upload_date)}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Uploaded By Name</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {document.uploaded_by || <span className="text-gray-500 italic">Not available</span>}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Uploaded By ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {isLoadingUserId ? (
                <span className="text-gray-500 italic">Loading...</span>
              ) : uploadedByUserId ? (
                uploadedByUserId
              ) : (
                <span className="text-gray-500 italic">Not available</span>
              )}
            </div>
          </div>
          
          <div className="col-span-2">
            <label className="text-sm font-semibold text-gray-700 block mb-1">Tags</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {document.tag_ids && document.tag_ids.length > 0 ? (
                <div className="space-y-2">
                  {document.tag_ids.map((tagId) => {
                    const tag = availableTags.find(t => t.id === tagId);
                    if (tag) {
                      const bgColor = tag.color;
                      const textColor = isColorLight(bgColor) ? 'text-gray-800' : 'text-white';
                      return (
                        <div key={tagId} className="flex items-center gap-2 border-b border-gray-200 pb-2 last:border-b-0 last:pb-0">
                          <div className="text-gray-600 font-mono text-xs">
                            {tagId}
                          </div>
                          <div 
                            className={`px-2 py-1 leading-none rounded shadow-sm ${textColor} inline-flex items-center`}
                            style={{ backgroundColor: bgColor }}
                          >
                            {tag.name}
                          </div>
                        </div>
                      );
                    } else {
                      return (
                        <div key={tagId} className="flex items-center gap-2 text-sm border-b border-gray-200 pb-2 last:border-b-0 last:pb-0">
                          <div className="text-gray-600 font-mono text-xs">
                            {tagId}
                          </div>
                          <div className="font-medium text-gray-500 italic">
                            Unknown tag
                          </div>
                        </div>
                      );
                    }
                  })}
                </div>
              ) : (
                <span className="text-gray-500 italic">No tags</span>
              )}
            </div>
          </div>
          
          <div className="col-span-2">
            <label className="text-sm font-semibold text-gray-700 block mb-1">Metadata</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {document.metadata && Object.keys(document.metadata).length > 0 ? (
                <div className="space-y-1">
                  {Object.entries(document.metadata).map(([key, value]) => (
                    <div key={key} className="text-sm">
                      <span className="font-medium">{key}:</span> <span>{value}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <span className="text-gray-500 italic">No metadata</span>
              )}
            </div>
          </div>
        </div>
          </div>
        </div>
      </DraggablePanel>
    </>
  );
};

export default DocumentInfoModal;
