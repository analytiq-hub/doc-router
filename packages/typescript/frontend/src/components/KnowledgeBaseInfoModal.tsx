import React, { useState, useMemo } from 'react';
import { KnowledgeBase } from '@docrouter/sdk';
import BadgeIcon from '@mui/icons-material/Badge';
import SyncIcon from '@mui/icons-material/Sync';
import { Chip, Button } from '@mui/material';
import { toast } from 'react-toastify';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';

interface KnowledgeBaseInfoModalProps {
  isOpen: boolean;
  onClose: () => void;
  kb: KnowledgeBase;
  organizationId: string;
  onReconcile?: () => void;
}

const KnowledgeBaseInfoModal: React.FC<KnowledgeBaseInfoModalProps> = ({ 
  isOpen, 
  onClose, 
  kb,
  organizationId,
  onReconcile
}) => {
  const [isReconciling, setIsReconciling] = useState(false);
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  
  if (!isOpen) return null;
  
  const handleReconcile = async () => {
    setIsReconciling(true);
    try {
      const result = await docRouterOrgApi.reconcileKnowledgeBase({ 
        kbId: kb.kb_id,
        dry_run: false 
      });
      toast.success(
        `Reconciliation complete: ${result.missing_documents.length} missing, ` +
        `${result.stale_documents.length} stale, ${result.orphaned_vectors} orphaned vectors`
      );
      if (onReconcile) {
        onReconcile();
      }
    } catch (error) {
      toast.error(`Reconciliation failed: ${getApiErrorMsg(error)}`);
    } finally {
      setIsReconciling(false);
    }
  };
  
  const formatInterval = (seconds?: number) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds}s`;
    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  };

  const formatDate = (dateString: string) => {
    try {
      // Parse UTC timestamp from API (ISO 8601 format, e.g., "2026-01-24T21:12:34.738Z")
      // JavaScript Date automatically converts UTC to local timezone
      const date = new Date(dateString);
      
      // Verify it's a valid date
      if (isNaN(date.getTime())) {
        return dateString;
      }
      
      // Format in local timezone (converted from UTC)
      return date.toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short' // Shows timezone abbreviation (e.g., PST, EST)
      });
    } catch {
      return dateString;
    }
  };

  const getStatusColor = (status: string): 'success' | 'warning' | 'error' | 'default' => {
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
                color={getStatusColor(kb.status)}
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
          
          <div className="col-span-2 border-t pt-4 mt-2">
            <label className="text-sm font-semibold text-gray-700 block mb-2">Reconciliation</label>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-600">Periodic Reconciliation:</label>
                <Chip 
                  label={kb.reconcile_enabled ? 'Enabled' : 'Disabled'} 
                  color={kb.reconcile_enabled ? 'success' : 'default'}
                  size="small"
                />
              </div>
              {kb.reconcile_enabled && kb.reconcile_interval_seconds && (
                <div className="text-sm text-gray-600">
                  Interval: {formatInterval(kb.reconcile_interval_seconds)}
                </div>
              )}
              {kb.last_reconciled_at && (
                <div className="text-sm text-gray-600">
                  Last reconciled: {formatDate(kb.last_reconciled_at)}
                </div>
              )}
              {!kb.last_reconciled_at && (
                <div className="text-sm text-gray-500 italic">
                  Never reconciled
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex justify-between items-center mt-6 pt-4 border-t">
          <Button
            variant="outlined"
            startIcon={<SyncIcon />}
            onClick={handleReconcile}
            disabled={isReconciling}
            className="text-blue-600 border-blue-600 hover:bg-blue-50"
          >
            {isReconciling ? 'Reconciling...' : 'Reconcile Now'}
          </Button>
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
