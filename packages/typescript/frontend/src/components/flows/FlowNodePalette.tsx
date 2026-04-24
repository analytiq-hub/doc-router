import React, { useMemo } from 'react';
import type { FlowNodeType } from '@docrouter/sdk';

const FlowNodePalette: React.FC<{ nodeTypes: FlowNodeType[] }> = ({ nodeTypes }) => {
  const grouped = useMemo(() => {
    const g = new Map<string, FlowNodeType[]>();
    for (const nt of nodeTypes) {
      const key = nt.category || 'Other';
      const arr = g.get(key) || [];
      arr.push(nt);
      g.set(key, arr);
    }
    return Array.from(g.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [nodeTypes]);

  return (
    <div className="h-full overflow-auto border-r border-gray-200 bg-white p-3">
      <div className="text-xs font-semibold text-gray-700 mb-2">Nodes</div>
      <div className="flex flex-col gap-3">
        {grouped.map(([cat, items]) => (
          <div key={cat}>
            <div className="text-[11px] font-semibold text-gray-500 mb-1">{cat}</div>
            <div className="flex flex-col gap-2">
              {items.map((nt) => (
                <div
                  key={nt.key}
                  draggable
                  onDragStart={(e) =>
                    e.dataTransfer.setData('application/flow-node-type', nt.key)
                  }
                  className="cursor-grab rounded-md border border-gray-200 px-2 py-2 hover:bg-gray-50 active:cursor-grabbing"
                  title={nt.description}
                >
                  <div className="text-sm font-medium text-gray-900">{nt.label}</div>
                  <div className="text-[11px] text-gray-500 line-clamp-2">
                    {nt.description}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
        {nodeTypes.length === 0 && (
          <div className="text-sm text-gray-500">No node types loaded.</div>
        )}
      </div>
    </div>
  );
};

export default FlowNodePalette;

