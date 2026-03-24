import React, { useState, useEffect } from 'react';
import { Schema } from '@docrouter/sdk';
import BadgeIcon from '@mui/icons-material/Badge';
import { DocRouterAccountApi } from '@/utils/api';
import DraggablePanel from '@/components/DraggablePanel';
import { formatLocalDateWithTZ } from '@/utils/date';

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

  return (
    <>
      <div
        className="fixed inset-0 z-[70] bg-black bg-opacity-50"
        onClick={onClose}
        role="presentation"
      />
      <DraggablePanel
        open
        resetToken={schema.schema_revid}
        anchorPercent={{ x: 50, y: 45 }}
        width="min(100vw - 32px, 42rem)"
        height="min(90vh, 820px)"
        zIndex={71}
        ariaLabel="Schema properties"
        title={
          <>
            <BadgeIcon className="shrink-0 text-blue-600" fontSize="small" />
            <span className="truncate">Schema Properties</span>
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
              {formatLocalDateWithTZ(schema.created_at)}
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
          </div>
        </div>
      </DraggablePanel>
    </>
  );
};

export default SchemaInfoModal;
