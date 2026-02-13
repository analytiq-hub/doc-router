'use client';

import React, { useEffect, useState } from 'react';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';

/** Cursor-style collapsible thinking block. Live (loading) or completed (with content). */
export default function ThinkingBlock({
  content,
  /** When true, shows elapsed timer and "Processing..." placeholder. */
  live = false,
  /** When false (completed), default collapsed. */
  defaultExpanded = true,
}: {
  content?: string | null;
  live?: boolean;
  defaultExpanded?: boolean;
}) {
  const [elapsed, setElapsed] = useState(0);
  const [expanded, setExpanded] = useState(defaultExpanded);
  useEffect(() => {
    if (!live) return;
    const start = Date.now();
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [live]);
  const hasContent = content?.trim();
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50/80 overflow-hidden my-2">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-100/80 transition-colors"
      >
        <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${live ? 'bg-amber-500 animate-pulse' : 'bg-gray-400'}`} />
        <span className="text-xs font-medium text-gray-600">Thinking</span>
        {live && elapsed > 0 && (
          <span className="text-xs text-gray-400">{elapsed}s</span>
        )}
        {!live && hasContent && !expanded && (
          <span className="text-xs text-gray-400 truncate flex-1">
            {hasContent.length > 40 ? `${hasContent.slice(0, 40)}…` : hasContent}
          </span>
        )}
        <span className="flex-1" />
        {expanded ? (
          <ExpandLessIcon sx={{ fontSize: 18 }} className="text-gray-500 shrink-0" />
        ) : (
          <ExpandMoreIcon sx={{ fontSize: 18 }} className="text-gray-500 shrink-0" />
        )}
      </button>
      {expanded && (
        <div className="px-3 py-2 pt-0 border-t border-gray-100">
          <div className="text-xs text-gray-500 leading-relaxed whitespace-pre-wrap font-mono">
            {hasContent ? (
              content
            ) : live ? (
              <span className="inline-flex items-center gap-1">
                <span>Processing your request</span>
                <span className="animate-pulse">...</span>
              </span>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
