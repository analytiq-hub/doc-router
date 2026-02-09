'use client';

import React, { useState } from 'react';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';

interface ExtractionPanelProps {
  extraction: Record<string, unknown> | null;
  /** Optional title override */
  title?: string;
}

export default function ExtractionPanel({ extraction, title = 'Current extraction' }: ExtractionPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (extraction == null || Object.keys(extraction).length === 0) {
    return (
      <div className="border-t border-gray-200 bg-gray-50/50 px-3 py-2 text-xs text-gray-500">
        No extraction yet. Ask the agent to run extraction.
      </div>
    );
  }

  return (
    <div className="border-t border-gray-200 bg-gray-50/50">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between px-3 py-2 text-left text-sm font-medium text-gray-700 hover:bg-gray-100/80"
      >
        <span>{title}</span>
        {collapsed ? (
          <ExpandMoreIcon fontSize="small" />
        ) : (
          <ExpandLessIcon fontSize="small" />
        )}
      </button>
      {!collapsed && (
        <div className="px-3 pb-3 pt-0">
          <pre className="text-xs bg-white border border-gray-200 rounded p-2 overflow-x-auto max-h-48 overflow-y-auto text-gray-800">
            {JSON.stringify(extraction, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
