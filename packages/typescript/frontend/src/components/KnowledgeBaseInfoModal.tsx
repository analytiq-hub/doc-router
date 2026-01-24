import React from 'react';
import { KnowledgeBase } from '@docrouter/sdk';
import BadgeIcon from '@mui/icons-material/Badge';
import { Chip } from '@mui/material';

interface KnowledgeBaseInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
  kb: KnowledgeBase;
}

const KnowledgeBaseInfoModal: React.FC<KnowledgeBaseInfoModalProps> = ({ 
  isOpen, 
  onClose, 
  kb 
}) => {
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'indexing':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white p-6 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-4">
          <BadgeIcon className="text-blue-600" />
          <h3 className="text-lg font-medium">Knowledge Base Properties</h3>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Name</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">{kb.name}</div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Status</label>
            <div className="pt-2">
              <Chip 
                label={kb.status} 
                color={getStatusColor(kb.status) as any}
                size="small"
              />
            </div>
          </div>
          
          <div className="col-span-2">
            <label className="text-sm font-semibold text-gray-700 block mb-1">Description</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {kb.description || <span className="text-gray-500 italic">No description</span>}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">KB ID</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
              {kb.kb_id}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Embedding Model</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm">
              {kb.embedding_model}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Embedding Dimensions</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {kb.embedding_dimensions}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Chunker Type</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {kb.chunker_type}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Chunk Size</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {kb.chunk_size} tokens
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Chunk Overlap</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {kb.chunk_overlap} tokens
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Coalesce Neighbors</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {kb.coalesce_neighbors || 0}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Document Count</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {kb.document_count.toLocaleString()}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Chunk Count</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {kb.chunk_count.toLocaleString()}
            </div>
          </div>
          
          <div className="col-span-2">
            <label className="text-sm font-semibold text-gray-700 block mb-1">Tag IDs</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {kb.tag_ids && kb.tag_ids.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {kb.tag_ids.map((tagId, index) => (
                    <span key={index} className="font-mono text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                      {tagId}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-gray-500 italic">No tags</span>
              )}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Created At</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {formatDate(kb.created_at)}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-semibold text-gray-700 block mb-1">Updated At</label>
            <div className="text-gray-900 bg-gray-50 p-2 rounded border">
              {formatDate(kb.updated_at)}
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

export default KnowledgeBaseInfoModal;
