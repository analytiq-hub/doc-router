import React, { useState, useEffect } from 'react';
import { Schema } from '@docrouter/sdk';
import BadgeIcon from '@mui/icons-material/Badge';
import { DocRouterAccountApi } from '@/utils/api';

interface SchemaInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
  schema: Schema;
}

const SchemaInfoModal: React.FC<SchemaInfoModalProps> = ({ 
  isOpen, 
  onClose, 
  schema 
}) => {
  const [createdByName, setCreatedByName] = useState<string | null>(null);
  const [isLoadingName, setIsLoadingName] = useState(false);
  const docRouterAccountApi = React.useMemo(() => new DocRouterAccountApi(), []);

  useEffect(() => {
    if (isOpen && schema.created_by) {
      setIsLoadingName(true);
      docRouterAccountApi.getUser(schema.created_by)
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
  }, [isOpen, schema.created_by, docRouterAccountApi]);

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
          <h3 className="text-lg font-medium">Schema Properties</h3>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Schema Name</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">{schema.name}</div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Version</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              v{schema.schema_version}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Schema ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {schema.schema_id}
            </div>
            <p className="text-xs text-gray-500 mt-1">Stable identifier for this schema</p>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Schema Revision ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {schema.schema_revid}
            </div>
            <p className="text-xs text-gray-500 mt-1">Unique identifier for this version</p>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Created At</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {formatDate(schema.created_at)}
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
              {schema.created_by}
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

export default SchemaInfoModal;
