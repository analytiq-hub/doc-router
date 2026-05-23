'use client';

import React from 'react';
import {
  ArrowsRightLeftIcon,
  ClockIcon,
  CodeBracketSquareIcon,
  CursorArrowRaysIcon,
  DocumentMagnifyingGlassIcon,
  DocumentTextIcon,
  GlobeAltIcon,
  SparklesIcon,
  Square2StackIcon,
  Squares2X2Icon,
  TagIcon,
} from '@heroicons/react/24/solid';
import { GoogleDriveIcon } from './icons/GoogleDriveIcon';

/** Preset strings returned by `GET .../flows/node-types` for built-in nodes; UI maps to bundled icons. */
export const FLOW_BUILTIN_ICON_KEYS = [
  'manual_trigger',
  'manual_trigger_document',
  'http_request',
  'webhook',
  'branch',
  'merge',
  'code',
  'ocr',
  'llm_extract',
  'set_tags',
  'google_drive',
  'schedule_trigger',
] as const;

export type FlowBuiltinIconKey = (typeof FLOW_BUILTIN_ICON_KEYS)[number];

function isBuiltinKey(k: string): k is FlowBuiltinIconKey {
  return (FLOW_BUILTIN_ICON_KEYS as readonly string[]).includes(k);
}

/** Renders a preset icon when `icon_key` is known; otherwise generic trigger/process glyph per `fallback`. */
export function FlowNodeTypeIcon({
  iconKey,
  fallback,
  className,
  'aria-hidden': ariaHidden = true,
}: {
  iconKey?: string | null | undefined;
  fallback: 'trigger' | 'process';
  className?: string;
  'aria-hidden'?: boolean | 'true' | 'false';
}): React.ReactElement {
  const k = typeof iconKey === 'string' ? iconKey.trim() : '';
  if (k && isBuiltinKey(k)) {
    switch (k) {
      case 'manual_trigger':
        return <CursorArrowRaysIcon className={className} aria-hidden={ariaHidden} />;
      case 'manual_trigger_document':
        return <DocumentTextIcon className={className} aria-hidden={ariaHidden} />;
      case 'http_request':
      case 'webhook':
        return <GlobeAltIcon className={className} aria-hidden={ariaHidden} />;
      case 'branch':
        return <ArrowsRightLeftIcon className={className} aria-hidden={ariaHidden} />;
      case 'merge':
        return <Square2StackIcon className={className} aria-hidden={ariaHidden} />;
      case 'code':
        return <CodeBracketSquareIcon className={className} aria-hidden={ariaHidden} />;
      case 'ocr':
        return <DocumentMagnifyingGlassIcon className={className} aria-hidden={ariaHidden} />;
      case 'llm_extract':
        return <SparklesIcon className={className} aria-hidden={ariaHidden} />;
      case 'set_tags':
        return <TagIcon className={className} aria-hidden={ariaHidden} />;
      case 'google_drive':
        return <GoogleDriveIcon className={className} />;
      case 'schedule_trigger':
        return <ClockIcon className={className} aria-hidden={ariaHidden} />;
      default:
        break;
    }
  }

  if (fallback === 'trigger') {
    return <CursorArrowRaysIcon className={className} aria-hidden={ariaHidden} />;
  }
  return <Squares2X2Icon className={className} aria-hidden={ariaHidden} />;
}
