'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Handle, NodeToolbar, Position, type NodeProps } from 'reactflow';
import {
  CheckCircleIcon,
  CursorArrowRaysIcon,
  EllipsisHorizontalIcon,
  ExclamationCircleIcon,
  BoltIcon,
  PlayIcon,
  Squares2X2Icon,
  StopCircleIcon,
  TrashIcon,
} from '@heroicons/react/24/solid';
import { NoSymbolIcon } from '@heroicons/react/24/outline';
import { inputHandleCount } from './flowRf';
import type { FlowRfNodeDataWithRun, NodeRunStatusBadge } from './flowNodeRunStatus';
import { getNodeRunStatusFromRunData } from './flowNodeRunStatus';
import { useFlowCanvasActions, useFlowExecutionVisual } from './flowCanvasActionsContext';

const handleClass =
  '!w-2.5 !h-2.5 -translate-y-1/2 !border-2 !border-[#d0d5dd] !bg-white hover:!border-emerald-500 hover:!bg-emerald-50';

function ExecutionStatusBadge({ status }: { status: NonNullable<NodeRunStatusBadge> }) {
  if (status === 'success') {
    return (
      <div
        className="pointer-events-none absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-white shadow-sm"
        title="Succeeded"
      >
        <CheckCircleIcon className="h-5 w-5 text-emerald-500" aria-hidden />
      </div>
    );
  }
  if (status === 'error') {
    return (
      <div
        className="pointer-events-none absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-white shadow-sm"
        title="Error"
      >
        <ExclamationCircleIcon className="h-5 w-5 text-red-500" aria-hidden />
      </div>
    );
  }
  if (status === 'running') {
    return (
      <div
        className="pointer-events-none absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-white shadow-sm"
        title="Running"
      >
        <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-sky-500 border-t-transparent" />
      </div>
    );
  }
  if (status === 'stopped') {
    return (
      <div
        className="pointer-events-none absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-white shadow-sm"
        title="Stopped"
      >
        <StopCircleIcon className="h-5 w-5 text-amber-600" aria-hidden />
      </div>
    );
  }
  return (
    <div
      className="pointer-events-none absolute -bottom-0.5 -right-0.5 h-4 min-w-4 rounded border border-amber-200 bg-amber-50 px-0.5 text-center text-[9px] font-bold leading-4 text-amber-800"
      title="Skipped"
    >
      —
    </div>
  );
}

/** Thin stroke, white fill; selection uses stacked spread shadows (white gap + thick light-gray band). */
const nodeBodyBase =
  'relative flex flex-col items-center justify-center border bg-white transition-[border-color,box-shadow]';

function nodeBorderClass(): string {
  return 'border-[#d2d6dc]';
}

/** Process nodes: uniform ~12px corners. */
const processShape = 'rounded-xl';

/** Trigger: more rounded on the left (~36px left, ~12px right). */
const triggerShape = 'rounded-l-[36px] rounded-r-xl';

/**
 * Selection contour: uniform white margin, then a thick light-gray outer contour that follows
 * the same border-radius as the node (incl. trigger D-shape). Implemented as stacked box-shadows
 * (spread-only, no blur).
 */
function nodeSelectionContour(selected: boolean): string {
  if (!selected) return '';
  return 'shadow-[0_0_0_0px_#fff,0_0_0_5px_#e0e2e5]';
}

/** Delay before hiding so the pointer can cross the gap to the portaled `NodeToolbar`. */
const TOOLBAR_HIDE_MS = 280;

const FlowCanvasNode: React.FC<NodeProps<FlowRfNodeDataWithRun>> = ({ id, data, selected }) => {
  const nt = data.nodeType;
  const node = data.flowNode;
  const isTrigger = Boolean(nt?.is_trigger);
  const actions = useFlowCanvasActions();
  const execution = useFlowExecutionVisual();
  const [pointerOnNodeOrToolbar, setPointerOnNodeOrToolbar] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const moreMenuRef = useRef<HTMLDivElement | null>(null);
  const hideToolbarTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelHideToolbarTimer = useCallback(() => {
    if (hideToolbarTimerRef.current != null) {
      clearTimeout(hideToolbarTimerRef.current);
      hideToolbarTimerRef.current = null;
    }
  }, []);

  const showToolbarForPointer = useCallback(() => {
    cancelHideToolbarTimer();
    setPointerOnNodeOrToolbar(true);
  }, [cancelHideToolbarTimer]);

  const hideToolbarForPointerSoon = useCallback(() => {
    cancelHideToolbarTimer();
    hideToolbarTimerRef.current = setTimeout(() => {
      hideToolbarTimerRef.current = null;
      setPointerOnNodeOrToolbar(false);
    }, TOOLBAR_HIDE_MS);
  }, [cancelHideToolbarTimer]);

  useEffect(() => () => cancelHideToolbarTimer(), [cancelHideToolbarTimer]);

  useEffect(() => {
    if (!moreOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target as Node)) {
        setMoreOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [moreOpen]);

  const inputs = inputHandleCount(nt);
  const outputs = Math.max(0, nt?.outputs ?? 1);

  const typeLabel = nt?.label ?? node.type;
  const displayLabel = node.name?.trim() ? node.name : typeLabel;

  const runSt = useMemo((): NodeRunStatusBadge => {
    if (data.executionNodeStatus != null) return data.executionNodeStatus;
    if (execution === undefined) return null;
    const rd = execution?.run_data as Record<string, unknown> | undefined;
    return getNodeRunStatusFromRunData(rd, id);
  }, [data.executionNodeStatus, execution, id]);

  const showToolbar = Boolean(actions);

  const labelBlock = (
    <div className="pointer-events-none absolute left-1/2 top-full z-0 mt-4 min-w-[120px] max-w-[260px] -translate-x-1/2 px-1 text-center">
      <div className="line-clamp-2 text-sm font-semibold leading-tight text-[#1a1d21]" title={displayLabel}>
        {displayLabel}
      </div>
    </div>
  );

  const disabledStrike = node.disabled ? (
    <div
      className="pointer-events-none absolute left-[-12px] right-[-12px] top-1/2 z-[5] h-px -translate-y-1/2 bg-[#64748b]/90"
      aria-hidden
    />
  ) : null;

  const toolbarVisible = pointerOnNodeOrToolbar || moreOpen;

  const toolbar = showToolbar && actions && (
    <NodeToolbar
      nodeId={id}
      isVisible={toolbarVisible}
      position={Position.Top}
      offset={10}
      align="center"
      className="rounded-lg border border-[#d8dce3] bg-white/95 shadow-md backdrop-blur-sm"
    >
      <div
        className="flex gap-0.5 px-1 py-0.5"
        onMouseEnter={showToolbarForPointer}
        onMouseLeave={hideToolbarForPointerSoon}
      >
        <span title="Run workflow">
          <button
            type="button"
            aria-label="Run workflow"
            disabled={!actions.onRunWorkflow}
            onClick={() => actions.onRunWorkflow?.()}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-gray-600 enabled:hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <PlayIcon className="h-4 w-4" />
          </button>
        </span>
        <span title={node.disabled ? 'Enable node' : 'Disable node'}>
          <button
            type="button"
            aria-label={node.disabled ? 'Enable node' : 'Disable node'}
            onClick={() => actions.onToggleNodeDisabled(id)}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-gray-600 hover:bg-gray-100"
          >
            <NoSymbolIcon className={`h-4 w-4 ${node.disabled ? 'text-amber-600' : 'text-gray-500'}`} />
          </button>
        </span>
        <span title="Delete node">
          <button
            type="button"
            aria-label="Delete node"
            onClick={() => actions.onDeleteNode(id)}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-gray-600 hover:bg-gray-100"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        </span>
        <div className="relative" ref={moreMenuRef}>
          <span title="More">
            <button
              type="button"
              aria-label="More actions"
              aria-expanded={moreOpen}
              onClick={() => setMoreOpen((o) => !o)}
              className="inline-flex h-7 w-7 items-center justify-center rounded-md text-gray-600 hover:bg-gray-100"
            >
              <EllipsisHorizontalIcon className="h-4 w-4" />
            </button>
          </span>
          {moreOpen && (
            <div
              className="absolute right-0 top-full z-[200] mt-1 w-40 rounded-md border border-gray-200 bg-white py-1 text-sm shadow-lg"
              role="menu"
            >
              <button
                type="button"
                className="block w-full px-3 py-2 text-left text-gray-800 hover:bg-gray-100"
                onClick={() => {
                  setMoreOpen(false);
                  actions.onOpenNodeSettings(id);
                }}
                role="menuitem"
              >
                Open settings
              </button>
              <div className="px-3 py-2 text-left text-gray-400" role="menuitem" aria-disabled>
                Duplicate (soon)
              </div>
            </div>
          )}
        </div>
      </div>
    </NodeToolbar>
  );

  if (isTrigger) {
    return (
      <div
        className={`group relative mx-auto w-[120px] pb-8 ${node.disabled ? 'opacity-60' : ''}`}
        onMouseEnter={showToolbarForPointer}
        onMouseLeave={hideToolbarForPointerSoon}
      >
        {toolbar}
        <div className="relative mx-auto w-[96px]">
          <div
            className={[
              nodeBodyBase,
              'mx-auto h-[96px] w-[96px]',
              triggerShape,
              nodeBorderClass(),
              nodeSelectionContour(selected),
            ].join(' ')}
          >
            {disabledStrike}
            <div className="flex h-full w-full items-center justify-center">
              <CursorArrowRaysIcon className="h-10 w-10 text-[#a8b0ba]" aria-hidden />
            </div>
            {/* Trigger bolt: outside-left, vertically centered (`right: 100%`, `margin: auto`). */}
            <div className="pointer-events-none absolute right-full top-1/2 -translate-y-1/2 p-1 text-[#ff6d5a]">
              <BoltIcon className="h-5 w-5" aria-hidden />
            </div>
            {Array.from({ length: Math.max(outputs, 0) }).map((_, i) => (
              <Handle
                key={`out-${i}`}
                id={`out-${i}`}
                type="source"
                position={Position.Right}
                className={handleClass}
                style={{ top: `${(100 * (i + 1)) / (outputs + 1)}%` }}
              />
            ))}
            {runSt && <ExecutionStatusBadge status={runSt} />}
          </div>
          {labelBlock}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`group relative mx-auto w-[120px] pb-8 ${node.disabled ? 'opacity-60' : ''}`}
      onMouseEnter={showToolbarForPointer}
      onMouseLeave={hideToolbarForPointerSoon}
    >
      {toolbar}
      <div className="relative mx-auto w-[96px]">
        <div
          className={[
            nodeBodyBase,
            'mx-auto h-[96px] w-[96px]',
            processShape,
            nodeBorderClass(),
            nodeSelectionContour(selected),
          ].join(' ')}
        >
          {disabledStrike}
          {Array.from({ length: Math.max(inputs, 0) }).map((_, i) => (
            <Handle
              key={`in-${i}`}
              id={`in-${i}`}
              type="target"
              position={Position.Left}
              className={handleClass}
              style={{ top: `${(100 * (i + 1)) / (inputs + 1)}%` }}
            />
          ))}
          <Squares2X2Icon className="h-9 w-9 text-[#94a3b8]" aria-hidden />
          {Array.from({ length: Math.max(outputs, 0) }).map((_, i) => (
            <Handle
              key={`out-${i}`}
              id={`out-${i}`}
              type="source"
              position={Position.Right}
              className={handleClass}
              style={{ top: `${(100 * (i + 1)) / (outputs + 1)}%` }}
            />
          ))}
          {runSt && <ExecutionStatusBadge status={runSt} />}
        </div>
        {labelBlock}
      </div>
    </div>
  );
};

export default FlowCanvasNode;
