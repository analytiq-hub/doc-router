'use client';

import React from 'react';

export const sidebarNavTooltipClass =
  'pointer-events-none absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs font-medium text-white opacity-0 transition-opacity duration-200 group-hover:opacity-100';

interface SidebarNavTooltipProps {
  label: string;
  /** When false, the tooltip is not shown (e.g. expanded sidebar with visible labels). */
  show?: boolean;
  /** Extra classes on the tooltip label (e.g. `md:hidden` for icon-only mobile nav). */
  tooltipClassName?: string;
  children: React.ReactNode;
  className?: string;
}

const SidebarNavTooltip: React.FC<SidebarNavTooltipProps> = ({
  label,
  show = true,
  tooltipClassName = '',
  children,
  className = '',
}) => (
  <span className={['group relative block', className].filter(Boolean).join(' ')}>
    {children}
    {show && (
      <span
        role="tooltip"
        className={[sidebarNavTooltipClass, tooltipClassName].filter(Boolean).join(' ')}
      >
        {label}
      </span>
    )}
  </span>
);

export default SidebarNavTooltip;
