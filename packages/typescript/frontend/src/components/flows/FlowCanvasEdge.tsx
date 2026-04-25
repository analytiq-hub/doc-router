'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  getMarkerEnd,
  getSmoothStepPath,
  getStraightPath,
  MarkerType,
  type Edge,
  type EdgeProps,
} from 'reactflow';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline';
import { Tooltip } from '@mui/material';
import { useFlowCanvasActions } from './flowCanvasActionsContext';

const DEFAULT_MARKER_END = getMarkerEnd(MarkerType.ArrowClosed);

/** Delay closing edge controls so the pointer can leave the SVG hit path and reach the HTML toolbar. */
const EDGE_CONTROLS_HIDE_MS = 280;

/** Custom edge: directed arrow, plain item label above the line, + / delete centered on the path (editor only). */
export default function FlowCanvasEdge(props: EdgeProps) {
  const edge = props as EdgeProps & Pick<Edge, 'sourceHandle' | 'targetHandle'>;
  const {
    id,
    source,
    target,
    sourceHandle,
    targetHandle,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    markerEnd,
    style,
    data,
    selected,
  } = edge;
  const actions = useFlowCanvasActions();

  const isVisuallyStraight =
    Math.abs(sourceY - targetY) < 0.5 &&
    ((sourcePosition === 'right' && targetPosition === 'left') ||
      (sourcePosition === 'left' && targetPosition === 'right') ||
      (sourcePosition === 'bottom' && targetPosition === 'top') ||
      (sourcePosition === 'top' && targetPosition === 'bottom'));

  const [edgePath, labelX, labelY] = isVisuallyStraight
    ? getStraightPath({ sourceX, sourceY, targetX, targetY })
    : getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });

  const count = (data as { itemCount?: number } | undefined)?.itemCount ?? 1;
  const label = `${count} item${count === 1 ? '' : 's'}`;
  const canEdit = Boolean(actions?.onDeleteEdge);
  const canInsert = Boolean(actions?.onBeginInsertOnEdge);

  const [edgeControlsOpen, setEdgeControlsOpen] = useState(false);
  const hideControlsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelHideControlsTimer = useCallback(() => {
    if (hideControlsTimerRef.current != null) {
      clearTimeout(hideControlsTimerRef.current);
      hideControlsTimerRef.current = null;
    }
  }, []);

  const showEdgeControlsSoon = useCallback(() => {
    cancelHideControlsTimer();
    setEdgeControlsOpen(true);
  }, [cancelHideControlsTimer]);

  const hideEdgeControlsSoon = useCallback(() => {
    cancelHideControlsTimer();
    hideControlsTimerRef.current = setTimeout(() => {
      hideControlsTimerRef.current = null;
      setEdgeControlsOpen(false);
    }, EDGE_CONTROLS_HIDE_MS);
  }, [cancelHideControlsTimer]);

  useEffect(() => () => cancelHideControlsTimer(), [cancelHideControlsTimer]);

  const showItemLabel = !canEdit || !edgeControlsOpen;

  const stroke = selected ? '#818cf8' : '#a8b0bd';

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd ?? DEFAULT_MARKER_END}
        interactionWidth={0}
        style={{
          stroke,
          strokeWidth: selected ? 2 : 1.5,
          ...style,
        }}
      />
      {/* Wide hit target + hover source for edge controls (BaseEdge interaction path has no React handlers). */}
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={32}
        className="react-flow__edge-interaction"
        onMouseEnter={canEdit ? showEdgeControlsSoon : undefined}
        onMouseLeave={canEdit ? hideEdgeControlsSoon : undefined}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
          }}
          className="nodrag nopan relative flex flex-col items-center"
        >
          {showItemLabel && (
            isVisuallyStraight ? (
              <div className="pointer-events-none absolute bottom-full left-1/2 mb-1 -translate-x-1/2 whitespace-nowrap text-[11px] font-medium text-[#5a6270]">
                {label}
              </div>
            ) : (
              <div className="pointer-events-none whitespace-nowrap bg-[#f7f7f9] px-1 text-[11px] font-medium text-[#5a6270]">
                {label}
              </div>
            )
          )}
          {canEdit && edgeControlsOpen && (
            <div
              className="pointer-events-auto flex items-center gap-1"
              onMouseEnter={showEdgeControlsSoon}
              onMouseLeave={hideEdgeControlsSoon}
            >
              <Tooltip title="Add node on this connection">
                <span>
                  <button
                    type="button"
                    disabled={!canInsert}
                    aria-label="Add node on this connection"
                    onClick={(e) => {
                      e.stopPropagation();
                      actions?.onBeginInsertOnEdge?.({
                        edgeId: id,
                        source,
                        target,
                        sourceHandle: sourceHandle ?? null,
                        targetHandle: targetHandle ?? null,
                        flowPosition: { x: labelX, y: labelY },
                      });
                    }}
                    className="flex h-7 w-7 items-center justify-center rounded border border-[#c5cad3] bg-[#f4f5f6] text-gray-700 shadow-sm hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <PlusIcon className="h-3.5 w-3.5" strokeWidth={2} />
                  </button>
                </span>
              </Tooltip>
              <Tooltip title="Delete connection">
                <span>
                  <button
                    type="button"
                    aria-label="Delete connection"
                    onClick={(e) => {
                      e.stopPropagation();
                      actions?.onDeleteEdge(id);
                    }}
                    className="flex h-7 w-7 items-center justify-center rounded border border-[#c5cad3] bg-[#f4f5f6] text-gray-700 shadow-sm hover:bg-red-50 hover:border-red-200 hover:text-red-700"
                  >
                    <TrashIcon className="h-3.5 w-3.5" strokeWidth={2} />
                  </button>
                </span>
              </Tooltip>
            </div>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
