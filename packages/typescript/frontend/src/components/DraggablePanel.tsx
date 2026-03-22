'use client';

import type { ReactNode } from 'react';
import DragIndicator from '@mui/icons-material/DragIndicator';
import { useDraggablePosition } from '@/hooks/useDraggablePosition';

export interface DraggablePanelProps {
  /** When false, nothing is rendered. */
  open: boolean;
  /** Resets drag offset when this changes (e.g. document id). */
  resetToken: string | number;
  /** Viewport-relative anchor as percentage (0–100). */
  anchorPercent?: { x: number; y: number };
  width?: number | string;
  height?: number | string;
  zIndex?: number;
  className?: string;
  /** Shown in the drag bar; default label is "Drag to move" when neither title nor headerActions is set. */
  title?: ReactNode;
  /** e.g. a Close button (drag handle remains the full bar). */
  headerActions?: ReactNode;
  /** Applied to the panel root for accessibility when used as a modal. */
  ariaLabel?: string;
  children: React.ReactNode;
}

/**
 * Floating panel anchored in the viewport; drag the top bar to reposition.
 * Uses `useDraggablePosition` (centered at `anchorPercent` + pixel offset).
 */
export default function DraggablePanel({
  open,
  resetToken,
  anchorPercent = { x: 50, y: 45 },
  width = 400,
  height = 'min(88vh, 820px)',
  zIndex = 1250,
  className = '',
  title,
  headerActions,
  ariaLabel,
  children,
}: DraggablePanelProps) {
  const { offset, handlePointerDown } = useDraggablePosition(open, resetToken);

  if (!open) return null;

  const w = typeof width === 'number' ? `${width}px` : width;

  return (
    <div
      role={ariaLabel ? 'dialog' : undefined}
      aria-modal={ariaLabel ? true : undefined}
      aria-label={ariaLabel}
      className={`pointer-events-auto flex flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-xl ${className}`}
      style={{
        position: 'fixed',
        left: `${anchorPercent.x}%`,
        top: `${anchorPercent.y}%`,
        zIndex,
        width: w,
        height,
        transform: `translate(calc(-50% + ${offset.x}px), calc(-50% + ${offset.y}px))`,
      }}
    >
      <div
        className="flex h-9 shrink-0 cursor-grab items-center gap-2 border-b border-gray-200 bg-slate-50 px-2 active:cursor-grabbing"
        onPointerDown={handlePointerDown}
        role="presentation"
      >
        <DragIndicator className="shrink-0 text-slate-400" fontSize="small" />
        {title != null || headerActions != null ? (
          <>
            {title != null ? (
              <div className="flex min-w-0 flex-1 items-center gap-2 text-sm font-medium text-slate-800">
                {title}
              </div>
            ) : (
              <span className="min-w-0 flex-1 select-none text-xs font-medium text-slate-600">
                Drag to move
              </span>
            )}
            {headerActions != null ? <div className="flex shrink-0 items-center gap-1">{headerActions}</div> : null}
          </>
        ) : (
          <span className="select-none text-xs font-medium text-slate-600">Drag to move</span>
        )}
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
    </div>
  );
}
