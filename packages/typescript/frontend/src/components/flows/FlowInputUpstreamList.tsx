'use client';

import React from 'react';
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/react';
import { ChevronRightIcon } from '@heroicons/react/24/outline';
import { FlowNodeTypeIcon } from './FlowNodeTypeIcon';
import { IoDataModeTabs, IoViewer } from './IoViewer';

export type UpstreamInputSlot = { slot: number; fromNodeId: string; itemsJson: unknown[] };

export type UpstreamNodeIconMeta = { iconKey?: string | null; isTrigger?: boolean };

function slotKey(s: UpstreamInputSlot): string {
  return `${s.fromNodeId}:${s.slot}`;
}

/**
 * n8n-style input schema: one expandable row per upstream node (name + item count),
 * shared Schema / Table / JSON mode for all sources; body is accordion JSON inside each row.
 */
export const FlowInputUpstreamList: React.FC<{
  slots: UpstreamInputSlot[];
  nodeLabelById: Map<string, string>;
  /** When set, shows a preset icon per upstream node id (from flow node type). */
  upstreamNodeIcons?: ReadonlyMap<string, UpstreamNodeIconMeta | undefined>;
  mode: 'schema' | 'table' | 'json';
  onModeChange: (next: 'schema' | 'table' | 'json') => void;
  expressionConfigNodeId?: string;
}> = ({ slots, nodeLabelById, upstreamNodeIcons, mode, onModeChange, expressionConfigNodeId }) => {
  if (slots.length === 0) return null;

  return (
    <div className="min-w-0">
      <div className="mb-2 flex items-center justify-end gap-2">
        <IoDataModeTabs mode={mode} onChange={onModeChange} />
      </div>
      <div className="divide-y divide-gray-100 overflow-hidden rounded border border-[#eceff2] bg-white">
        {slots.map((s, i) => {
          const label = nodeLabelById.get(s.fromNodeId) ?? s.fromNodeId;
          const n = s.itemsJson.length;
          const countLabel = `${n} ${n === 1 ? 'item' : 'items'}`;
          const titleSuffix = s.slot > 0 ? ` · in ${s.slot}` : '';
          return (
            <Disclosure key={slotKey(s)} as="div" defaultOpen={i === 0}>
              <DisclosureButton className="flex w-full items-center gap-2 px-2 py-1.5 text-left outline-none hover:bg-gray-50">
                {({ open }) => (
                  <>
                    <span className="flex h-4 w-4 shrink-0 items-center justify-center text-gray-500" aria-hidden>
                      <ChevronRightIcon
                        className={['h-3 w-3 transition-transform duration-150 ease-out', open ? 'rotate-90' : 'rotate-0'].join(
                          ' ',
                        )}
                        strokeWidth={1.5}
                      />
                    </span>
                    {upstreamNodeIcons && (
                      <span
                        className={[
                          'flex h-4 w-4 shrink-0 items-center justify-center',
                          upstreamNodeIcons.get(s.fromNodeId)?.isTrigger ? 'text-[#a8b0ba]' : 'text-[#94a3b8]',
                        ].join(' ')}
                        aria-hidden
                      >
                        <FlowNodeTypeIcon
                          iconKey={upstreamNodeIcons.get(s.fromNodeId)?.iconKey}
                          fallback={upstreamNodeIcons.get(s.fromNodeId)?.isTrigger ? 'trigger' : 'process'}
                          className="h-3.5 w-3.5"
                        />
                      </span>
                    )}
                    <span className="min-w-0 flex-1 truncate text-[11px] font-semibold text-gray-900">
                      {label}
                      {titleSuffix}
                    </span>
                    <span className="shrink-0 whitespace-nowrap text-[11px] font-medium tabular-nums text-gray-500">
                      {countLabel}
                    </span>
                  </>
                )}
              </DisclosureButton>
              <DisclosurePanel className="bg-[#fafbfc]/40">
                <div className="border-t border-gray-100 px-1 py-1.5">
                  <IoViewer
                    hideHeader
                    value={s.itemsJson}
                    valueKind="executionItems"
                    dragSource={{ nodeId: s.fromNodeId, source: 'nodeOutput' }}
                    expressionConfigNodeId={expressionConfigNodeId}
                    defaultMode="schema"
                    mode={mode}
                    onModeChange={onModeChange}
                  />
                </div>
              </DisclosurePanel>
            </Disclosure>
          );
        })}
      </div>
    </div>
  );
};
