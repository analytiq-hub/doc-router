import React, { useState, useMemo } from "react";
import { KnowledgeBase } from "@docrouter/sdk";
import BadgeIcon from "@mui/icons-material/Badge";
import SyncIcon from "@mui/icons-material/Sync";
import { Chip, Button } from "@mui/material";
import { toast } from "react-toastify";
import { DocRouterOrgApi, getApiErrorMsg } from "@/utils/api";
import DraggablePanel from "@/components/DraggablePanel";

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
  onReconcile,
}) => {
  const [isReconciling, setIsReconciling] = useState(false);
  const docRouterOrgApi = useMemo(
    () => new DocRouterOrgApi(organizationId),
    [organizationId],
  );

  if (!isOpen) return null;

  const handleReconcile = async () => {
    setIsReconciling(true);
    try {
      const result = await docRouterOrgApi.reconcileKnowledgeBase({
        kbId: kb.kb_id,
        dry_run: false,
      });
      toast.success(
        `Reconciliation complete: ${result.missing_documents.length} missing, ` +
          `${result.stale_documents.length} stale, ${result.orphaned_vectors} orphaned vectors`,
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
    if (!seconds) return "N/A";
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
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short", // Shows timezone abbreviation (e.g., PST, EST)
      });
    } catch {
      return dateString;
    }
  };

  const getStatusColor = (
    status: string,
  ): "success" | "warning" | "error" | "default" => {
    switch (status) {
      case "active":
        return "success";
      case "indexing":
        return "warning";
      case "error":
        return "error";
      default:
        return "default";
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 z-[70] bg-black bg-opacity-50"
        onClick={onClose}
        role="presentation"
      />
      <DraggablePanel
        open
        resetToken={kb.kb_id}
        anchorPercent={{ x: 50, y: 45 }}
        width="min(100vw - 32px, 42rem)"
        height="min(90vh, 820px)"
        zIndex={71}
        ariaLabel="Knowledge base properties"
        title={
          <>
            <BadgeIcon className="shrink-0 text-blue-600" fontSize="small" />
            <span className="truncate">Knowledge Base Properties</span>
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
          <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-4 pt-2">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Name
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {kb.name}
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Status
                </label>
                <div className="pt-2">
                  <Chip
                    label={kb.status}
                    color={getStatusColor(kb.status)}
                    size="small"
                  />
                </div>
              </div>

              <div className="col-span-2">
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Description
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {kb.description || (
                    <span className="text-gray-500 italic">No description</span>
                  )}
                </div>
              </div>

              <div className="col-span-2">
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  System Prompt
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm whitespace-pre-wrap">
                  {kb.system_prompt || (
                    <span className="text-gray-500 italic">
                      No system prompt
                    </span>
                  )}
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  KB ID
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm break-all">
                  {kb.kb_id}
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Embedding Model
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border font-mono text-sm">
                  {kb.embedding_model}
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Embedding Dimensions
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {kb.embedding_dimensions}
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Chunker Type
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {kb.chunker_type}
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Chunk Size
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {kb.chunk_size} tokens
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Chunk Overlap
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {kb.chunk_overlap} tokens
                </div>
              </div>

              <div className="col-span-2">
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Chunking preprocessing
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border text-sm space-y-1">
                  <div>
                    <span className="text-gray-500">Preset: </span>
                    {kb.chunking_preset != null ? (
                      kb.chunking_preset
                    ) : (
                      <span className="text-gray-500 italic">(legacy default)</span>
                    )}
                  </div>
                  {kb.chunking_preprocess ? (
                    <ul className="list-disc list-inside text-xs text-gray-700 mt-1">
                      <li>prefer_markdown: {String(kb.chunking_preprocess.prefer_markdown)}</li>
                      <li>strip_page_numbers: {String(kb.chunking_preprocess.strip_page_numbers)}</li>
                      <li>strip_page_breaks: {String(kb.chunking_preprocess.strip_page_breaks)}</li>
                      <li>prepend_heading_path: {String(kb.chunking_preprocess.prepend_heading_path)}</li>
                      <li>heading_split_depth: {kb.chunking_preprocess.heading_split_depth}</li>
                      <li>
                        strip_patterns:{' '}
                        {kb.chunking_preprocess.strip_patterns?.length
                          ? `${kb.chunking_preprocess.strip_patterns.length} regex(es)`
                          : 'none'}
                      </li>
                    </ul>
                  ) : (
                    <span className="text-gray-500 text-xs">No custom preprocess stored (legacy KB).</span>
                  )}
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Coalesce Neighbors
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {kb.coalesce_neighbors || 0}
                </div>
              </div>

              <div className="col-span-2 border-t border-gray-100 pt-3 mt-1">
                <label className="text-sm font-semibold text-gray-700 block mb-2">
                  Search &amp; retrieval
                </label>
                <div>
                  <span className="text-xs text-gray-500 block mb-1">
                    Min vector score (vector-only fallback)
                  </span>
                  <div className="text-gray-900 bg-gray-50 p-2 rounded border text-sm">
                    {kb.min_vector_score != null ? (
                      kb.min_vector_score
                    ) : (
                      <span className="text-gray-600">None (no cutoff)</span>
                    )}
                  </div>
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Document Count
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {kb.document_count.toLocaleString()}
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Chunk Count
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {kb.chunk_count.toLocaleString()}
                </div>
              </div>

              <div className="col-span-2">
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Tag IDs
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {kb.tag_ids && kb.tag_ids.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {kb.tag_ids.map((tagId, index) => (
                        <span
                          key={index}
                          className="font-mono text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded"
                        >
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
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Created At
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {formatDate(kb.created_at)}
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold text-gray-700 block mb-1">
                  Updated At
                </label>
                <div className="text-gray-900 bg-gray-50 p-2 rounded border">
                  {formatDate(kb.updated_at)}
                </div>
              </div>

              <div className="col-span-2 border-t pt-4 mt-2">
                <label className="text-sm font-semibold text-gray-700 block mb-2">
                  Reconciliation
                </label>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-gray-600">
                      Periodic Reconciliation:
                    </label>
                    <Chip
                      label={kb.reconcile_enabled ? "Enabled" : "Disabled"}
                      color={kb.reconcile_enabled ? "success" : "default"}
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
          </div>

          <div className="flex shrink-0 items-center border-t border-gray-200 px-6 py-3">
            <Button
              variant="outlined"
              startIcon={<SyncIcon />}
              onClick={handleReconcile}
              disabled={isReconciling}
              className="text-blue-600 border-blue-600 hover:bg-blue-50"
            >
              {isReconciling ? "Reconciling..." : "Reconcile Now"}
            </Button>
          </div>
        </div>
      </DraggablePanel>
    </>
  );
};

export default KnowledgeBaseInfoModal;
