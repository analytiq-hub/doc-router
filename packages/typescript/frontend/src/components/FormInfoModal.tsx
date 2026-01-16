import React, { useState, useEffect } from 'react';
import { Form } from '@docrouter/sdk';
import BadgeIcon from '@mui/icons-material/Badge';
import { DocRouterAccountApi } from '@/utils/api';

interface FormInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
  form: Form;
}

const FormInfoModal: React.FC<FormInfoModalProps> = ({ 
  isOpen, 
  onClose, 
  form 
}) => {
  const [createdByName, setCreatedByName] = useState<string | null>(null);
  const [isLoadingName, setIsLoadingName] = useState(false);
  const docRouterAccountApi = React.useMemo(() => new DocRouterAccountApi(), []);

  useEffect(() => {
    if (isOpen && form.created_by) {
      setIsLoadingName(true);
      docRouterAccountApi.getUser(form.created_by)
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
  }, [isOpen, form.created_by, docRouterAccountApi]);

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
          <h3 className="text-lg font-medium">Form Properties</h3>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Form Name</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">{form.name}</div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Version</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              v{form.form_version}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Form ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {form.form_id}
            </div>
            <p className="text-xs text-gray-500 mt-1">Stable identifier for this form</p>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Form Revision ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {form.form_revid}
            </div>
            <p className="text-xs text-gray-500 mt-1">Unique identifier for this version</p>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Created At</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {formatDate(form.created_at)}
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
              {form.created_by}
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

export default FormInfoModal;
