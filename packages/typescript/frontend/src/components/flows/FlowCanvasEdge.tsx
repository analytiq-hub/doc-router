'use client';

import React from 'react';
import { BaseEdge, EdgeLabelRenderer, getMarkerEnd, getSmoothStepPath, MarkerType, type EdgeProps } from 'reactflow';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline';
import { Tooltip } from '@mui/material';
import { useFlowCanvasActions } from './flowCanvasActionsContext';

const DEFAULT_MARKER_END = getMarkerEnd(MarkerType.ArrowClosed);

/** Custom edge: directed arrow, item count above the path, + / delete centered on the path (editor only). */
export default function FlowCanvasEdge(props: EdgeProps) {
  const { id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, markerEnd, style, data, selected } =
    props;
  const actions = useFlowCanvasActions();
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });
  const count = (data as { itemCount?: number } | undefined)?.itemCount ?? 1;
  const label = `${count} item${count === 1 ? '' : 's'}`;
  const canEdit = Boolean(actions?.onDeleteEdge);
  const canAdd = Boolean(actions?.onOpenNodePalette);

  const stroke = selected ? '#818cf8' : '#a8b0bd';

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd ?? DEFAULT_MARKER_END}
        interactionWidth={28}
        style={{
          stroke,
          strokeWidth: selected ? 2 : 1.5,
          ...style,
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
          }}
          className="nodrag nopan flex flex-col items-center gap-1"
        >
          {/* Item count — above the edge / arrow line */}
          <div className="pointer-events-none -translate-y-2 rounded border border-[#dadce2] bg-white px-1.5 py-0.5 text-[11px] font-medium text-[#5a6270] shadow-sm">
            {label}
          </div>
          {canEdit && (
            <div className="pointer-events-auto flex items-center gap-1">
              <Tooltip title="Add node">
                <span>
                  <button
                    type="button"
                    disabled={!canAdd}
                    aria-label="Add node"
                    onClick={(e) => {
                      e.stopPropagation();
                      actions?.onOpenNodePalette?.();
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
