import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';

interface FormNameModalProps {
  isOpen: boolean;
  onClose: () => void;
  formName: string;
  onSubmit: (newName: string) => Promise<void>;
  isCloning?: boolean;
  organizationId: string;
}

const FormNameModal: React.FC<FormNameModalProps> = ({ 
  isOpen, 
  onClose, 
  formName, 
  onSubmit,
  isCloning = false,
  organizationId
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [newName, setNewName] = useState(formName);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [existingNames, setExistingNames] = useState<string[]>([]);

  // When formName prop changes, update the newName state
  useEffect(() => {
    setNewName(formName);
  }, [formName]);

  // Fetch existing form names for uniqueness check
  useEffect(() => {
    if (isOpen) {
      const fetchFormNames = async () => {
        try {
          const response = await docRouterOrgApi.listForms({
            skip: 0,
            limit: 100
          });
          
          setExistingNames(response.forms.map(form => form.name.toLowerCase()));
        } catch (err) {
          console.error("Failed to fetch form names:", err);
        }
      };
      
      fetchFormNames();
    }
  }, [isOpen, docRouterOrgApi]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    // Validate the input
    if (!newName.trim()) {
      setError('Form name cannot be empty');
      return;
    }

    // Check for uniqueness
    if (newName.trim().toLowerCase() !== formName.toLowerCase() && 
        existingNames.includes(newName.trim().toLowerCase())) {
      setError('A form with this name already exists');
      return;
    }

    try {
      setIsSubmitting(true);
      await onSubmit(newName.trim());
      onClose();
    } catch (err) {
      console.error(`Failed to ${isCloning ? 'clone' : 'rename'} form:`, err);
      setError(`Failed to ${isCloning ? 'clone' : 'rename'} form`);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-md w-full">
        <h3 className="text-lg font-medium mb-4">
          {isCloning ? 'Clone Form' : 'Rename Form'}
        </h3>
        
        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={`px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 ${
                isSubmitting || !newName.trim() || (!isCloning && newName === formName)
                  ? 'opacity-50 cursor-not-allowed'
                  : ''
              }`}
              disabled={isSubmitting || !newName.trim() || (!isCloning && newName === formName)}
            >
              {isSubmitting ? 'Saving...' : (isCloning ? 'Clone' : 'Save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default FormNameModal; 