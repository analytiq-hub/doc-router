import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';

interface SchemaNameModalProps {
  isOpen: boolean;
  onClose: () => void;
  schemaName: string;
  onSubmit: (newName: string) => Promise<void>;
  isCloning?: boolean;
  organizationId: string;
}

const SchemaNameModal: React.FC<SchemaNameModalProps> = ({ 
  isOpen, 
  onClose, 
  schemaName, 
  onSubmit,
  isCloning = false,
  organizationId
}) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [newName, setNewName] = useState(schemaName);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [existingNames, setExistingNames] = useState<string[]>([]);

  // When schemaName prop changes, update the newName state
  useEffect(() => {
    setNewName(schemaName);
  }, [schemaName]);

  // Fetch existing schema names for uniqueness check
  useEffect(() => {
    if (isOpen) {
      const fetchSchemaNames = async () => {
        try {
          const response = await docRouterOrgApi.listSchemas({
            limit: 100
          });
          
          setExistingNames(response.schemas.map(schema => schema.name.toLowerCase()));
        } catch (err) {
          console.error("Failed to fetch schema names:", err);
        }
      };
      
      fetchSchemaNames();
    }
  }, [isOpen, docRouterOrgApi]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    // Validate the input
    if (!newName.trim()) {
      setError('Schema name cannot be empty');
      return;
    }

    // Check for uniqueness
    if (newName.trim().toLowerCase() !== schemaName.toLowerCase() && 
        existingNames.includes(newName.trim().toLowerCase())) {
      setError('A schema with this name already exists');
      return;
    }

    try {
      setIsSubmitting(true);
      await onSubmit(newName.trim());
      onClose();
    } catch (err) {
      console.error(`Failed to ${isCloning ? 'clone' : 'rename'} schema:`, err);
      setError(`Failed to ${isCloning ? 'clone' : 'rename'} schema`);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-md w-full">
        <h3 className="text-lg font-medium mb-4">
          {isCloning ? 'Clone Schema' : 'Rename Schema'}
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
                isSubmitting || !newName.trim() || (!isCloning && newName === schemaName)
                  ? 'opacity-50 cursor-not-allowed'
                  : ''
              }`}
              disabled={isSubmitting || !newName.trim() || (!isCloning && newName === schemaName)}
            >
              {isSubmitting ? 'Saving...' : (isCloning ? 'Clone' : 'Save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default SchemaNameModal; 