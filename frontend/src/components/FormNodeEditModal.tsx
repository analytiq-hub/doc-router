import React, { useState, useEffect } from 'react';
import { FormNodeData } from '@/types/forms';

interface FormNodeEditModalProps {
  node: FormNodeData | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (updated: FormNodeData) => void;
}

const FormNodeEditModal: React.FC<FormNodeEditModalProps> = ({ node, isOpen, onClose, onSave }) => {
  const [form, setForm] = useState<FormNodeData | null>(node);

  useEffect(() => {
    setForm(node);
  }, [node]);

  if (!isOpen || !form) return null;

  // Render fields based on node type
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-30">
      <div className="bg-white rounded-lg shadow-lg p-6 min-w-[320px]">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-bold text-lg">Edit {form.type === 'note' ? 'Sticky Note' : 'Field'}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800 text-xl">&times;</button>
        </div>
        <form
          onSubmit={e => {
            e.preventDefault();
            if (form) onSave(form);
          }}
        >
          <div className="space-y-4">
            <div>
              <label className="block font-semibold mb-1">Label/Title</label>
              <input
                className="w-full border rounded px-2 py-1"
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
              />
            </div>
            {form.type === 'note' && (
              <div>
                <label className="block font-semibold mb-1">Note Content</label>
                <textarea
                  className="w-full border rounded px-2 py-1"
                  value={form.noteContent || ''}
                  onChange={e => setForm({ ...form, noteContent: e.target.value })}
                  rows={4}
                />
              </div>
            )}
            {form.type === 'text' && (
              <>
                <div>
                  <label className="block font-semibold mb-1">Placeholder</label>
                  <input
                    className="w-full border rounded px-2 py-1"
                    value={form.placeholder || ''}
                    onChange={e => setForm({ ...form, placeholder: e.target.value })}
                  />
                </div>
                <div>
                  <label className="inline-flex items-center">
                    <input
                      type="checkbox"
                      className="mr-2"
                      checked={!!form.required}
                      onChange={e => setForm({ ...form, required: e.target.checked })}
                    />
                    Required
                  </label>
                </div>
              </>
            )}
          </div>
          <div className="flex justify-end mt-6">
            <button
              type="button"
              onClick={onClose}
              className="mr-2 px-4 py-1 rounded border border-gray-300 bg-gray-100 hover:bg-gray-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1 rounded bg-blue-600 text-white hover:bg-blue-700"
            >
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default FormNodeEditModal;
