'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { QuestionMarkCircleIcon } from '@heroicons/react/24/outline';

type FlowParamLabelProps = {
  label: string;
  htmlFor?: string;
  description?: string;
  className?: string;
  wrapperClassName?: string;
  /** When true, listen for hover on a parent ``group/field`` wrapper (e.g. boolean toggle row). */
  useParentGroup?: boolean;
};

const TOOLTIP_MAX_WIDTH_PX = 288;
const VIEWPORT_PAD_PX = 8;

function ParamInfoTooltip({
  description,
  anchorEl,
  open,
}: {
  description: string;
  anchorEl: HTMLElement | null;
  open: boolean;
}) {
  const [style, setStyle] = useState<React.CSSProperties>({ visibility: 'hidden' });

  useEffect(() => {
    if (!open || !anchorEl || typeof window === 'undefined') return;

    const update = () => {
      const rect = anchorEl.getBoundingClientRect();
      const width = Math.min(TOOLTIP_MAX_WIDTH_PX, window.innerWidth - VIEWPORT_PAD_PX * 2);
      let left = rect.left + rect.width / 2 - width / 2;
      left = Math.max(VIEWPORT_PAD_PX, Math.min(left, window.innerWidth - width - VIEWPORT_PAD_PX));
      const top = rect.bottom + 6;
      setStyle({
        position: 'fixed',
        top,
        left,
        width,
        zIndex: 300,
        visibility: 'visible',
      });
    };

    update();
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
  }, [anchorEl, open]);

  if (!open || typeof document === 'undefined') return null;

  return createPortal(
    <div
      role="tooltip"
      style={style}
      className="rounded-md bg-gray-900 px-2.5 py-1.5 text-left text-xs font-normal leading-snug text-white shadow-lg"
    >
      {description}
    </div>,
    document.body,
  );
}

/** Parameter label with optional info tooltip (schema ``description``). */
export function FlowParamLabel({
  label,
  htmlFor,
  description,
  className,
  wrapperClassName,
  useParentGroup = false,
}: FlowParamLabelProps) {
  const labelClass = className ?? 'mb-0 text-xs font-medium leading-none text-gray-600';
  const infoRef = useRef<HTMLSpanElement>(null);
  const [tooltipOpen, setTooltipOpen] = useState(false);

  const showTooltip = useCallback(() => setTooltipOpen(true), []);
  const hideTooltip = useCallback(() => setTooltipOpen(false), []);

  const infoVisibilityClass =
    'opacity-0 transition-opacity duration-150 pointer-events-none group-hover/field:opacity-100 group-focus-within/field:opacity-100 group-hover/field:pointer-events-auto group-focus-within/field:pointer-events-auto';

  return (
    <div
      className={`${useParentGroup ? '' : 'group/field '}mb-1 flex min-w-0 items-center gap-1 ${wrapperClassName ?? ''}`.trim()}
    >
      {htmlFor ? (
        <label className={labelClass} htmlFor={htmlFor}>
          {label}
        </label>
      ) : (
        <span className={labelClass}>{label}</span>
      )}
      {description ? (
        <>
          <span
            ref={infoRef}
            className={`inline-flex shrink-0 cursor-help items-center self-center ${infoVisibilityClass}`}
            onMouseEnter={showTooltip}
            onMouseLeave={hideTooltip}
            onFocus={showTooltip}
            onBlur={hideTooltip}
            tabIndex={0}
            role="button"
            aria-label={`More information about ${label}`}
          >
            <QuestionMarkCircleIcon className="h-3.5 w-3.5 text-gray-400" aria-hidden />
            <span className="sr-only">{description}</span>
          </span>
          <ParamInfoTooltip description={description} anchorEl={infoRef.current} open={tooltipOpen} />
        </>
      ) : null}
    </div>
  );
}
