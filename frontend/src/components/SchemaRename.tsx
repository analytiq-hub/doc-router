import React, { useState } from 'react';

interface SchemaRenameModalProps {
  isOpen: boolean;
  onClose: () => void;
  schemaName: string;
  onSubmit: (newName: string) => Promise<void>;
}

const SchemaRenameModal: React.FC<SchemaRenameModalProps> = ({ 
  isOpen, 
  onClose, 
  schemaName, 
  onSubmit 
}) => {
  const [newName, setNewName] = useState(schemaName);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!newName.trim()) {
      setError('Schema name cannot be empty');
      return;
    }

    setIsSubmitting(true);
    try {
      await onSubmit(newName);
      onClose();
    } catch (error) {
      console.error('Schema rename failed:', error);
      setError('Failed to rename schema');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-md w-full">
        <h3 className="text-lg font-medium mb-4">Rename Schema</h3>
        
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
                isSubmitting || !newName.trim() || newName === schemaName
                  ? 'opacity-50 cursor-not-allowed'
                  : ''
              }`}
              disabled={isSubmitting || !newName.trim() || newName === schemaName}
            >
              {isSubmitting ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default SchemaRenameModal; 