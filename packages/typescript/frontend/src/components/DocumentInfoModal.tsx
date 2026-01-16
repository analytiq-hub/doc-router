import React, { useState, useEffect } from 'react';
import { Document } from '@docrouter/sdk';
import BadgeIcon from '@mui/icons-material/Badge';
import { DocRouterAccountApi } from '@/utils/api';

interface DocumentInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: Document;
}

const DocumentInfoModal: React.FC<DocumentInfoModalProps> = ({ 
  isOpen, 
  onClose, 
  document 
}) => {
  const [uploadedByName, setUploadedByName] = useState<string | null>(null);
  const [isLoadingName, setIsLoadingName] = useState(false);
  const docRouterAccountApi = React.useMemo(() => new DocRouterAccountApi(), []);

  useEffect(() => {
    if (isOpen && document.uploaded_by) {
      setIsLoadingName(true);
      docRouterAccountApi.getUser(document.uploaded_by)
        .then(user => {
          setUploadedByName(user.name || null);
        })
        .catch(error => {
          console.error('Error fetching user name:', error);
          setUploadedByName(null);
        })
        .finally(() => {
          setIsLoadingName(false);
        });
    } else {
      setUploadedByName(null);
    }
  }, [isOpen, document.uploaded_by, docRouterAccountApi]);

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

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-lg w-full mx-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-4">
          <BadgeIcon className="text-blue-600" />
          <h3 className="text-lg font-medium">Document Properties</h3>
        </div>
        
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
              {formatDate(document.upload_date)}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Uploaded By Name</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {isLoadingName ? (
                <span className="text-gray-500 italic">Loading...</span>
              ) : uploadedByName ? (
                uploadedByName
              ) : (
                <span className="text-gray-500 italic">Not available</span>
              )}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Uploaded By ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {document.uploaded_by}
            </div>
          </div>
          
          <div className="col-span-2">
            <label className="text-sm font-semibold text-gray-700 block mb-1">Tag IDs</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {document.tag_ids && document.tag_ids.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {document.tag_ids.map((tagId, index) => (
                    <span key={tagId} className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-mono">
                      {tagId}
                    </span>
                  ))}
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

        <div className="flex justify-end mt-6 pt-4 border-t">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default DocumentInfoModal;
