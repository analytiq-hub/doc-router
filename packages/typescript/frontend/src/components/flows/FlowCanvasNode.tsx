'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/react';
import { Handle, NodeToolbar, Position, useStore, type NodeProps } from 'reactflow';
import {
  CheckCircleIcon,
  EllipsisHorizontalIcon,
  ExclamationCircleIcon,
  BookmarkIcon,
  BoltIcon,
  PlayIcon,
  StopCircleIcon,
  TrashIcon,
} from '@heroicons/react/24/solid';
import { NoSymbolIcon } from '@heroicons/react/24/outline';
import { inputHandleCount, inputPortTypes, outputPortTypes } from './flowRf';
import type { FlowConnectionType } from './flowRf';
import type { FlowRfNodeDataWithRun, NodeRunStatusBadge } from './flowNodeRunStatus';
import { getNodeRunStatusFromRunData } from './flowNodeRunStatus';
import type { FlowCanvasActions } from './flowCanvasActionsContext';
import { useFlowCanvasActions, useFlowExecutionVisual } from './flowCanvasActionsContext';
import { FlowCanvasAppendPlusButton } from './FlowCanvasAppendPlusButton';
import { FlowNodeTypeIcon } from './FlowNodeTypeIcon';
import { flowNodeIconColorClass, isDocRouterNodeType } from './flowNodeBrand';
import {
  flowWorkspaceDropdownItemMutedClass,
  flowWorkspaceDropdownItemSimpleClass,
  flowWorkspaceMenuPanelClass,
  flowWorkspaceMenuTriggerCompactClass,
} from './flowWorkspaceMenu';
import { flowRunButtonTriggerHoverClass, FLOW_EXECUTE_FLOW_LABEL } from './flowUiClasses';

const handleClass =
  '!w-2.5 !h-2.5 -translate-y-1/2 !border-2 !border-[#d0d5dd] !bg-white hover:!border-primary-500 hover:!bg-primary-50';

const ocrHandleClass =
  '!w-2.5 !h-2.5 !border-2 !border-violet-400 !bg-violet-50 hover:!border-violet-600 hover:!bg-violet-100';

function handleClassForPortType(portType: FlowConnectionType): string {
  return portType === 'docrouter.ocr' ? ocrHandleClass : handleClass;
}

/** Trigger node body height (`h-[96px]` below); hover run button is exactly ⅓. */
const FLOW_TRIGGER_NODE_BODY_PX = 96;
const TRIGGER_EXECUTE_BTN_H_PX = FLOW_TRIGGER_NODE_BODY_PX / 3;

/** Test id slug for hover “Execute flow” control. */
function flowExecuteFlowButtonTestSlug(displayLabel: string, fallbackId: string): string {
  const t = displayLabel.trim();
  if (!t) return fallbackId.slice(0, 64);
  return t.slice(0, 120).replace(/[^\w\s-]/g, '');
}

/** Mid-edge insert already provides “+” on the connection; hide the inline stub until the node is hovered. */
const appendStubHiddenUntilNodeHoverClass =
  'opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:pointer-events-none [@media(hover:hover)]:group-hover:pointer-events-auto [@media(hover:hover)]:group-hover:opacity-100 motion-safe:transition-opacity motion-safe:duration-150';

function OutputHandleWithContinuation({
  nodeId,
  handleId,
  topPct,
  portType,
  actions,
}: {
  nodeId: string;
  handleId: string;
  topPct: number;
  portType: FlowConnectionType;
  actions: FlowCanvasActions | null;
}) {
  const canAppend = Boolean(actions?.onBeginAppendFromOutput);
  const hasOutgoingEdge = useStore(
    useCallback(
      (s) => s.edges.some((e) => e.source === nodeId && String(e.sourceHandle ?? 'out-0') === handleId),
      [nodeId, handleId],
    ),
  );

  return (
    <>
      <Handle
        id={handleId}
        type="source"
        position={Position.Right}
        className={handleClassForPortType(portType)}
        style={{ top: `${topPct}%` }}
      />
      {canAppend ? (
        <div
          className={[
            'docrouter-flow-node-append absolute left-full z-[6000] flex translate-y-[-50%] items-center gap-1',
            hasOutgoingEdge ? appendStubHiddenUntilNodeHoverClass : '',
          ]
            .filter(Boolean)
            .join(' ')}
          style={{ top: `${topPct}%` }}
        >
          <span className="pointer-events-none inline-block h-px w-4 shrink-0 bg-[#c5cad3]" aria-hidden />
          <FlowCanvasAppendPlusButton
            title="Add next node"
            ariaLabel="Add next node"
            onClick={(e) => {
              e.stopPropagation();
              actions?.onBeginAppendFromOutput?.({ source: nodeId, sourceHandle: handleId });
            }}
          />
        </div>
      ) : null}
    </>
  );
}

function OutputHandlesWithContinuation({
  outputs,
  outputPortTypesList,
  actions,
  nodeId,
}: {
  outputs: number;
  outputPortTypesList: FlowConnectionType[];
  actions: FlowCanvasActions | null;
  nodeId: string;
}) {
  const nOut = Math.max(outputs, 0);
  return (
    <>
      {Array.from({ length: nOut }).map((_, i) => {
        const topPct = (100 * (i + 1)) / (nOut + 1);
        const handleId = `out-${i}`;
        return (
          <OutputHandleWithContinuation
            key={handleId}
            nodeId={nodeId}
            handleId={handleId}
            topPct={topPct}
            portType={outputPortTypesList[i] ?? 'main'}
            actions={actions}
          />
        );
      })}
    </>
  );
}

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

function PinnedBadge() {
  return (
    <div
      className="pointer-events-none absolute -top-1 -left-1 flex h-6 w-6 items-center justify-center rounded-full border-2 border-white bg-white shadow-sm"
      title="Pinned output"
    >
      <BookmarkIcon className="h-4 w-4 text-violet-600" aria-hidden />
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

/** Trigger: rounded left (~36px), ~12px right — classic workflow trigger silhouette. */
const triggerShape = 'rounded-l-[36px] rounded-r-xl';

/**
 * Selection contour: uniform white margin, then a thick light-gray outer contour that follows
 * the node border-radius (incl. trigger pill). Stacked box-shadows, spread-only, no blur.
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

  const inputs = inputHandleCount(nt);
  const outputs = Math.max(0, nt?.outputs ?? 1);
  const inputTypes = useMemo(() => inputPortTypes(nt), [nt]);
  const outputTypes = useMemo(() => outputPortTypes(nt), [nt]);

  const typeLabel = nt?.label ?? node.type;
  const displayLabel = node.name?.trim() ? node.name : typeLabel;

  const runSt = useMemo((): NodeRunStatusBadge => {
    if (data.executionNodeStatus != null) return data.executionNodeStatus;
    if (execution === undefined) return null;
    const rd = execution?.run_data as Record<string, unknown> | undefined;
    return getNodeRunStatusFromRunData(rd, id);
  }, [data.executionNodeStatus, execution, id]);

  const isPinned = Boolean(data.pinned);

  const showToolbar = Boolean(actions);
  /** Omit on read-only executions canvas (undefined ⇒ allow). Editor sets explicit true/false. */
  const triggerReachOk = data.reachableFromTriggers !== false;

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

  const toolbar = showToolbar && actions && (
    <Menu>
      {({ open: overflowMenuOpen }) => {
        const toolbarVisible = pointerOnNodeOrToolbar || overflowMenuOpen;
        return (
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
              <span
                title={
                  isTrigger
                    ? 'Triggers run with the full workflow'
                    : !triggerReachOk
                      ? 'Connect this node from a trigger with graph edges to run this step'
                      : 'Execute step (partial run through this node)'
                }
              >
                <button
                  type="button"
                  aria-label={isTrigger ? 'Execute step unavailable for triggers' : 'Execute step'}
                  disabled={
                    isTrigger ||
                    !actions.onExecuteNodeStep ||
                    Boolean(actions.executeStepBusy) ||
                    !triggerReachOk
                  }
                  onClick={() => void actions.onExecuteNodeStep?.(id)}
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
              <span title="More">
                <MenuButton className={flowWorkspaceMenuTriggerCompactClass} aria-label="More actions">
                  <EllipsisHorizontalIcon className="h-4 w-4" aria-hidden />
                </MenuButton>
              </span>
              <MenuItems anchor="bottom end" portal modal={false} className={`${flowWorkspaceMenuPanelClass} min-w-[10rem]`}>
                <MenuItem>
                  {({ focus }) => (
                    <button
                      type="button"
                      className={`${flowWorkspaceDropdownItemSimpleClass} w-full ${focus ? 'bg-gray-100' : ''}`}
                      onClick={() => actions.onOpenNodeSettings(id)}
                    >
                      Open settings
                    </button>
                  )}
                </MenuItem>
                <MenuItem disabled>
                  <span className={`${flowWorkspaceDropdownItemMutedClass} block w-full cursor-not-allowed opacity-70`}>Duplicate (soon)</span>
                </MenuItem>
              </MenuItems>
            </div>
          </NodeToolbar>
        );
      }}
    </Menu>
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
          {actions?.onHoverExecuteWorkflowFromTrigger ? (
            <>
              {/* Corridor from node edge to/off the floated control — avoids losing `group-hover` over empty canvas */}
              <div
                aria-hidden
                className="pointer-events-none absolute right-full top-1/2 z-[6095] h-[112px] w-[calc(2.25rem+9.25rem)] -translate-y-1/2 group-hover:pointer-events-auto [@media(hover:none)]:pointer-events-auto"
                onMouseEnter={showToolbarForPointer}
                onMouseLeave={hideToolbarForPointerSoon}
              />
              <button
                type="button"
                aria-live="polite"
                aria-label={`${FLOW_EXECUTE_FLOW_LABEL} from ${displayLabel}`}
                data-test-id={`execute-flow-button-${flowExecuteFlowButtonTestSlug(displayLabel, id)}`}
                className={flowRunButtonTriggerHoverClass}
                style={{
                  height: TRIGGER_EXECUTE_BTN_H_PX,
                  minHeight: TRIGGER_EXECUTE_BTN_H_PX,
                  maxHeight: TRIGGER_EXECUTE_BTN_H_PX,
                }}
                onMouseEnter={showToolbarForPointer}
                onMouseLeave={hideToolbarForPointerSoon}
                onClick={(e) => {
                  e.stopPropagation();
                  void actions?.onHoverExecuteWorkflowFromTrigger?.(id);
                }}
              >
                <PlayIcon className="h-2.5 w-2.5 shrink-0 opacity-95" aria-hidden />
                <span>{FLOW_EXECUTE_FLOW_LABEL}</span>
              </button>
            </>
          ) : null}
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
            {isPinned && <PinnedBadge />}
            <div className="flex h-full w-full items-center justify-center">
              <FlowNodeTypeIcon
                iconKey={nt?.icon_key}
                fallback="trigger"
                className={[
                  'h-10 w-10',
                  flowNodeIconColorClass({ isDocRouter: isDocRouterNodeType(nt), isTrigger: true }),
                ].join(' ')}
              />
            </div>
            <div className="pointer-events-none absolute right-full top-1/2 -translate-y-1/2 p-1 text-primary-600">
              <BoltIcon className="h-5 w-5" aria-hidden />
            </div>
            <OutputHandlesWithContinuation
              outputs={outputs}
              outputPortTypesList={outputTypes}
              actions={actions}
              nodeId={id}
            />
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
          {isPinned && <PinnedBadge />}
          {Array.from({ length: Math.max(inputs, 0) }).map((_, i) => {
            const portType = inputTypes[i] ?? 'main';
            const isOcrPort = portType === 'docrouter.ocr';
            return (
              <Handle
                key={`in-${i}`}
                id={`in-${i}`}
                type="target"
                position={isOcrPort ? Position.Bottom : Position.Left}
                className={handleClassForPortType(portType)}
                style={
                  isOcrPort
                    ? { left: '14%', bottom: '-6px', top: 'auto', transform: 'none' }
                    : { top: `${(100 * (i + 1)) / (inputs + 1)}%` }
                }
              />
            );
          })}
          <FlowNodeTypeIcon
            iconKey={nt?.icon_key}
            fallback="process"
            className={[
              'h-9 w-9',
              flowNodeIconColorClass({ isDocRouter: isDocRouterNodeType(nt), isTrigger: false }),
            ].join(' ')}
          />
          <OutputHandlesWithContinuation
            outputs={outputs}
            outputPortTypesList={outputTypes}
            actions={actions}
            nodeId={id}
          />
          {runSt && <ExecutionStatusBadge status={runSt} />}
        </div>
        {labelBlock}
      </div>
    </div>
  );
};

export default FlowCanvasNode;
