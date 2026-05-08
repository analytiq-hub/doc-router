'use client';

import React from 'react';
import { PlusIcon } from '@heroicons/react/24/outline';

/** Matches the mid-edge “add node” control in `FlowCanvasEdge`. */
export const flowCanvasAppendPlusButtonClassName =
  'flex h-7 w-7 items-center justify-center rounded border border-[#c5cad3] bg-[#f4f5f6] text-gray-700 shadow-sm hover:bg-white disabled:cursor-not-allowed disabled:opacity-50';

export function FlowCanvasAppendPlusButton({
  title,
  ariaLabel,
  onClick,
  disabled = false,
}: {
  title: string;
  ariaLabel: string;
  onClick: (e: React.MouseEvent) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      aria-label={ariaLabel}
      onClick={onClick}
      className={flowCanvasAppendPlusButtonClassName}
    >
      <PlusIcon className="h-3.5 w-3.5" strokeWidth={2} />
    </button>
  );
}
