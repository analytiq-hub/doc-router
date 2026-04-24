import React, { useMemo, useState } from 'react';
import type { FlowNodeType } from '@docrouter/sdk';
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';

const FlowNodePalette: React.FC<{
  nodeTypes: FlowNodeType[];
  /** When true, only search + list (title lives in the drawer header). */
  embedInDrawer?: boolean;
  searchInputRef?: React.Ref<HTMLInputElement>;
  /** n8n-style: double-click adds an unconnected node and opens its configuration. */
  onNodeTypeDoubleClick?: (typeKey: string) => void;
  className?: string;
}> = ({ nodeTypes, embedInDrawer, searchInputRef, onNodeTypeDoubleClick, className = '' }) => {
  const [query, setQuery] = useState('');
  const grouped = useMemo(() => {
    const g = new Map<string, FlowNodeType[]>();
    for (const nt of nodeTypes) {
      if (query.trim()) {
        const q = query.trim().toLowerCase();
        const hit =
          nt.label.toLowerCase().includes(q) ||
          nt.key.toLowerCase().includes(q) ||
          (nt.description && nt.description.toLowerCase().includes(q)) ||
          (nt.category && nt.category.toLowerCase().includes(q));
        if (!hit) continue;
      }
      const key = nt.category || 'Other';
      const arr = g.get(key) || [];
      arr.push(nt);
      g.set(key, arr);
    }
    return Array.from(g.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [nodeTypes, query]);

  return (
    <div className={['flex h-full min-h-0 flex-col bg-[#fbfbfc]', embedInDrawer ? '' : 'border-r border-[#e2e4e8]', className].filter(Boolean).join(' ')}>
      <div className="shrink-0 border-b border-[#eceff2] p-2.5">
        {!embedInDrawer && (
          <div className="text-[11px] font-semibold uppercase tracking-wide text-[#6b7280]">Add node</div>
        )}
        <div className={embedInDrawer ? '' : 'mt-2'}>
          <div className="relative">
          <MagnifyingGlassIcon
            className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9ca3af]"
            aria-hidden
          />
          <input
            ref={searchInputRef}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search nodes…"
            className="w-full rounded-md border border-[#d8dce3] bg-white py-1.5 pl-8 pr-2 text-sm text-gray-800 placeholder:text-gray-400 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
          />
          </div>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2.5">
        <div className="flex flex-col gap-3">
          {grouped.map(([cat, items]) => (
            <div key={cat}>
              <div className="mb-1.5 pl-0.5 text-[10px] font-semibold uppercase text-[#9ca3af]">{cat}</div>
              <div className="flex flex-col gap-1.5">
                {items.map((nt) => (
                  <div
                    key={nt.key}
                    draggable
                    onDragStart={(e) => e.dataTransfer.setData('application/flow-node-type', nt.key)}
                    onDoubleClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onNodeTypeDoubleClick?.(nt.key);
                    }}
                    className="group cursor-grab select-none rounded-lg border border-[#e2e4e8] bg-white p-2.5 shadow-sm transition hover:border-sky-300 hover:shadow active:cursor-grabbing"
                    title={nt.description}
                  >
                    <div className="text-sm font-semibold text-[#1a1d21] group-hover:text-sky-800">{nt.label}</div>
                    {nt.description && (
                      <div className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-[#6b7280]">
                        {nt.description}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        {nodeTypes.length === 0 && (
          <div className="p-2 text-sm text-gray-500">No node types loaded.</div>
        )}
        {nodeTypes.length > 0 && grouped.length === 0 && (
          <div className="p-2 text-sm text-gray-500">No nodes match your search.</div>
        )}
      </div>
    </div>
  );
};

export default FlowNodePalette;
