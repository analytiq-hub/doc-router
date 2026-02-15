'use client';

import React from 'react';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import { DocRouterOrgApi } from '@/utils/api';

interface AutoCreateReviewProps {
  organizationId: string;
  documentId: string;
  schemaRevId: string;
  promptRevId: string;
  onAccept: () => void;
  onReject: () => void;
}

/**
 * Banner shown in Agent tab when document has auto_create_status: "proposed".
 * User can Accept or Reject the auto-created schema and prompt.
 * "Refine via chat" is handled by continuing to chat (no special UI).
 */
export default function AutoCreateReview({
  organizationId,
  documentId,
  schemaRevId,
  promptRevId,
  onAccept,
  onReject,
}: AutoCreateReviewProps) {
  const docRouterOrgApi = React.useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleAccept = async () => {
    setLoading(true);
    setError(null);
    try {
      await docRouterOrgApi.acceptAutoCreate({ documentId });
      onAccept();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to accept');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setLoading(true);
    setError(null);
    try {
      await docRouterOrgApi.rejectAutoCreate({ documentId });
      onReject();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to reject');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="shrink-0 px-3 py-2 bg-blue-50 border-b border-blue-200">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-blue-800">
          Auto-create proposed a schema and prompt for this document. Review the extraction in the left panel, then accept or reject.
        </p>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleAccept}
            disabled={loading}
            className="inline-flex items-center gap-1 px-2.5 py-1 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            <CheckCircleIcon sx={{ fontSize: 18 }} />
            Accept
          </button>
          <button
            type="button"
            onClick={handleReject}
            disabled={loading}
            className="inline-flex items-center gap-1 px-2.5 py-1 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
          >
            <CancelIcon sx={{ fontSize: 18 }} />
            Reject
          </button>
        </div>
      </div>
      {error && (
        <p className="mt-1 text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}
