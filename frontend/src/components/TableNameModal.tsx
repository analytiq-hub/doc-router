// frontend/src/components/TableNameModal.tsx
import React, { useEffect, useState } from 'react';
import { listTablesApi } from '@/utils/api';

interface TableNameModalProps {
  isOpen: boolean;
  onClose: () => void;
  tableName: string;
  onSubmit: (newName: string) => Promise<void>;
  isCloning?: boolean;
  organizationId: string;
}

const TableNameModal: React.FC<TableNameModalProps> = ({
  isOpen,
  onClose,
  tableName,
  onSubmit,
  isCloning = false,
  organizationId
}) => {
  const [newName, setNewName] = useState(tableName);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [existingNames, setExistingNames] = useState<string[]>([]);

  useEffect(() => {
    setNewName(tableName);
  }, [tableName]);

  useEffect(() => {
    if (!isOpen) return;
    (async () => {
      try {
        const resp = await listTablesApi({ organizationId, skip: 0, limit: 1000 });
        setExistingNames(resp.tables.map(t => t.name.toLowerCase()));
      } catch {}
    })();
  }, [isOpen, organizationId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!newName.trim()) {
      setError('Table name cannot be empty');
      return;
    }
    if (newName.trim().toLowerCase() !== tableName.toLowerCase() && existingNames.includes(newName.trim().toLowerCase())) {
      setError('A table with this name already exists');
      return;
    }
    try {
      setIsSubmitting(true);
      await onSubmit(newName.trim());
      onClose();
    } catch {
      setError(`Failed to ${isCloning ? 'clone' : 'rename'} table`);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-md w-full">
        <h3 className="text-lg font-medium mb-4">{isCloning ? 'Clone Table' : 'Rename Table'}</h3>
        {error && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoFocus
          />
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50" disabled={isSubmitting}>
              Cancel
            </button>
            <button
              type="submit"
              className={`px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 ${isSubmitting || !newName.trim() || (!isCloning && newName === tableName) ? 'opacity-50 cursor-not-allowed' : ''}`}
              disabled={isSubmitting || !newName.trim() || (!isCloning && newName === tableName)}
            >
              {isSubmitting ? 'Saving...' : isCloning ? 'Clone' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default TableNameModal;