'use client';

import React from 'react';
import {
  ArrowsRightLeftIcon,
  ArrowPathRoundedSquareIcon,
  ArrowUturnLeftIcon,
  BoltIcon,
  BookOpenIcon,
  ChatBubbleLeftRightIcon,
  ClockIcon,
  CodeBracketSquareIcon,
  CommandLineIcon,
  CursorArrowRaysIcon,
  DocumentMagnifyingGlassIcon,
  DocumentTextIcon,
  GlobeAltIcon,
  QueueListIcon,
  RectangleStackIcon,
  SparklesIcon,
  Square2StackIcon,
  Squares2X2Icon,
} from '@heroicons/react/24/solid';
import { AnalytiqHubIcon } from './icons/AnalytiqHubIcon';
import { GmailIcon } from './icons/GmailIcon';
import { GoogleDriveIcon } from './icons/GoogleDriveIcon';
import { MicrosoftOneDriveIcon } from './icons/MicrosoftOneDriveIcon';
import { MicrosoftOutlookIcon } from './icons/MicrosoftOutlookIcon';

/** Preset strings returned by `GET .../flows/node-types` for built-in nodes; UI maps to bundled icons. */
export const FLOW_BUILTIN_ICON_KEYS = [
  'manual_trigger',
  'manual_trigger_document',
  'document_event_trigger',
  'http_request',
  'webhook',
  'webhook_trigger',
  'branch',
  'merge',
  'code',
  'ocr',
  'llm_run',
  'google_drive',
  'gmail',
  'microsoft_onedrive',
  'microsoft_outlook',
  'schedule_trigger',
  'chat_trigger',
  'agent',
  'tool_code',
  'flow_tool',
  'execute_flow',
  'knowledge_base',
  'tool_executor',
  'tool_trigger',
  'respond_to_webhook',
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
      case 'document_event_trigger':
        return <DocumentTextIcon className={className} aria-hidden={ariaHidden} />;
      case 'http_request':
      case 'webhook':
      case 'webhook_trigger':
        return <GlobeAltIcon className={className} aria-hidden={ariaHidden} />;
      case 'branch':
        return <ArrowsRightLeftIcon className={className} aria-hidden={ariaHidden} />;
      case 'merge':
        return <Square2StackIcon className={className} aria-hidden={ariaHidden} />;
      case 'code':
        return <CodeBracketSquareIcon className={className} aria-hidden={ariaHidden} />;
      case 'tool_code':
        return <CommandLineIcon className={className} aria-hidden={ariaHidden} />;
      case 'ocr':
        return <DocumentMagnifyingGlassIcon className={className} aria-hidden={ariaHidden} />;
      case 'llm_run':
        return <SparklesIcon className={className} aria-hidden={ariaHidden} />;
      case 'agent':
        return <AnalytiqHubIcon className={className} />;
      case 'chat_trigger':
        return <ChatBubbleLeftRightIcon className={className} aria-hidden={ariaHidden} />;
      case 'flow_tool':
        return <RectangleStackIcon className={className} aria-hidden={ariaHidden} />;
      case 'execute_flow':
        return <ArrowPathRoundedSquareIcon className={className} aria-hidden={ariaHidden} />;
      case 'knowledge_base':
        return <BookOpenIcon className={className} aria-hidden={ariaHidden} />;
      case 'tool_executor':
        return <BoltIcon className={className} aria-hidden={ariaHidden} />;
      case 'tool_trigger':
        return <QueueListIcon className={className} aria-hidden={ariaHidden} />;
      case 'respond_to_webhook':
        return <ArrowUturnLeftIcon className={className} aria-hidden={ariaHidden} />;
      case 'google_drive':
        return <GoogleDriveIcon className={className} />;
      case 'gmail':
        return <GmailIcon className={className} />;
      case 'microsoft_onedrive':
        return <MicrosoftOneDriveIcon className={className} />;
      case 'microsoft_outlook':
        return <MicrosoftOutlookIcon className={className} />;
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
