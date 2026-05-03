'use client';

import React, { useEffect, useState } from 'react';
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline';
import type { DocRouterOrgApi } from '@/utils/api';

const DEBOUNCE_MS = 340;

export type ExpressionPreviewContext = {
  flowOrgApi: DocRouterOrgApi | null;
  runData: Record<string, unknown>;
  inputItems: Record<string, unknown>[];
  previewItemIndex: number;
  onPreviewItemIndexChange: (idx: number) => void;
  /** Match `flows.http_request`: executor binds expressions to inbound slot item 0 only. */
  forceFirstInputItem?: boolean;
  executionRefs?: Record<string, string | undefined>;
};

/** Debounced backend preview for `=` flow expressions (Python evaluator; matches runtime). */
export const FlowExpressionPreviewLine: React.FC<{
  expression: string;
  preview: ExpressionPreviewContext;
}> = ({ expression, preview }) => {
  const [loading, setLoading] = useState(false);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const itemCount = preview.inputItems.length || 1;
  const ix = preview.forceFirstInputItem ? 0 : preview.previewItemIndex;
  const safeIx = Math.max(0, Math.min(ix, Math.max(itemCount - 1, 0)));

  useEffect(() => {
    const trimmed = expression.trimStart();
    if (!trimmed.startsWith('=')) {
      setLoading(false);
      setPreviewText(null);
      setError(null);
      return;
    }
    if (!preview.flowOrgApi) {
      setLoading(false);
      setPreviewText(null);
      setError(null);
      return;
    }

    let cancelled = false;
    const t = window.setTimeout(() => {
      void (async () => {
        setLoading(true);
        setError(null);
        setPreviewText(null);
        try {
          const res = await preview.flowOrgApi.previewFlowExpression({
            expression,
            run_data: preview.runData,
            input_items: preview.inputItems.length ? preview.inputItems : [{}],
            preview_item_index: preview.forceFirstInputItem ? 0 : safeIx,
            execution_refs: preview.executionRefs,
          });
          if (cancelled) return;
          if (res.skipped) {
            setPreviewText(null);
            setError(null);
          } else if (!res.ok) {
            setError(res.error ?? 'Expression error');
          } else {
            setPreviewText(res.preview_text ?? String(res.value ?? ''));
          }
        } catch (e) {
          if (cancelled) return;
          setError(e instanceof Error ? e.message : 'Preview failed');
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
    }, DEBOUNCE_MS);

    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [expression, preview, preview.flowOrgApi, safeIx]);

  const trimmedOut = expression.trimStart();
  if (!trimmedOut.startsWith('=')) return null;

  const showPager = itemCount > 1 && !preview.forceFirstInputItem;

  const noSample = preview.inputItems.length === 0 && Object.keys(preview.runData).length === 0;

  return (
    <div className="mt-1.5 rounded border border-[#e5e9ee] bg-[#fafbfc] px-2 py-1.5">
      <div className="mb-0.5 flex items-center justify-between gap-2 text-[10px] font-semibold uppercase tracking-wide text-[#85909c]">
        <span>Result</span>
        {showPager ? (
          <span className="inline-flex items-center gap-1 normal-case tabular-nums">
            <button
              type="button"
              className="rounded p-0.5 text-[#657080] hover:bg-gray-200 disabled:opacity-30"
              disabled={safeIx <= 0}
              aria-label="Previous item"
              onClick={() => preview.onPreviewItemIndexChange(Math.max(0, safeIx - 1))}
            >
              <ChevronLeftIcon className="h-3.5 w-3.5" strokeWidth={1.75} />
            </button>
            <span>
              Item {safeIx}
              <span className="font-normal normal-case text-[#a8b4c2]"> · {itemCount} rows</span>
            </span>
            <button
              type="button"
              className="rounded p-0.5 text-[#657080] hover:bg-gray-200 disabled:opacity-30"
              disabled={safeIx >= itemCount - 1}
              aria-label="Next item"
              onClick={() => preview.onPreviewItemIndexChange(Math.min(itemCount - 1, safeIx + 1))}
            >
              <ChevronRightIcon className="h-3.5 w-3.5" strokeWidth={1.75} />
            </button>
          </span>
        ) : preview.forceFirstInputItem ? (
          <span className="max-w-[10rem] truncate text-[9px] font-normal normal-case text-[#9ca8b4]" title="This node binds parameters to the first inbound row only">
            Uses first inbound item
          </span>
        ) : null}
      </div>
      {!preview.flowOrgApi ? (
        <div className="text-[11px] text-[#8896a8]">Sign in with org access to evaluate expressions.</div>
      ) : noSample ? (
        <div className="text-[11px] text-[#8896a8]">Run upstream nodes or Execute step — then previews use that data.</div>
      ) : loading ? (
        <div className="text-[11px] text-[#8896a8]">Evaluating…</div>
      ) : error ? (
        <div className="break-all font-mono text-[11px] text-[#cf3d3d]">{error}</div>
      ) : previewText != null ? (
        <div className="break-all rounded border border-emerald-100 bg-emerald-50/90 px-1.5 py-1 font-mono text-[11px] leading-snug text-emerald-950">
          {previewText}
        </div>
      ) : (
        <div className="text-[11px] text-[#8896a8]">Preview idle.</div>
      )}
    </div>
  );
};
