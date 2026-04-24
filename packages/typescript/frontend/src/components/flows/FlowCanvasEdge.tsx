'use client';

import React, { useState } from 'react';
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from 'reactflow';
import { useFlowCanvasActions } from './flowCanvasActionsContext';

/** Custom edge: smooth steps, optional “N items” count label on the path; delete when editable. */
export default function FlowCanvasEdge(props: EdgeProps) {
  const { id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, markerEnd, style, data } = props;
  const [hovered, setHovered] = useState(false);
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
  const canDelete = Boolean(actions?.onDeleteEdge);

  return (
    <g onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        interactionWidth={22}
        style={{
          stroke: '#a8b0bd',
          strokeWidth: 1.5,
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
          <div className="pointer-events-none select-none rounded border border-[#dadce2] bg-[#eceff2] px-1.5 py-0.5 text-[11px] font-medium text-[#5a6270] shadow-sm">
            {label}
          </div>
          {hovered && canDelete && (
            <button
              type="button"
              className="pointer-events-auto rounded border border-red-200 bg-white px-2 py-0.5 text-[11px] font-semibold text-red-700 shadow-sm hover:bg-red-50"
              onClick={(e) => {
                e.stopPropagation();
                actions?.onDeleteEdge(id);
              }}
            >
              Remove
            </button>
          )}
        </div>
      </EdgeLabelRenderer>
    </g>
  );
}
