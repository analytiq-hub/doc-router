'use client';

import React from 'react';
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from 'reactflow';

/** Custom edge: smooth steps, optional “N items” count label on the path. */
export default function FlowCanvasEdge(props: EdgeProps) {
  const { id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, markerEnd, style, data } = props;
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

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
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
          className="nodrag nopan pointer-events-none select-none rounded border border-[#dadce2] bg-[#eceff2] px-1.5 py-0.5 text-[11px] font-medium text-[#5a6270] shadow-sm"
        >
          {label}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
