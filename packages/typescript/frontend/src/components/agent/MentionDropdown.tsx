'use client';

import React, { useEffect, useRef } from 'react';

export interface MentionItem {
  type: 'schema' | 'prompt' | 'tag';
  id: string;
  label: string;
  /** Optional subtitle, e.g. version for schemas */
  subtitle?: string;
}

interface MentionDropdownProps {
  items: MentionItem[];
  search: string;
  position: { top: number; left: number } | null;
  selectedIndex: number;
  onSelect: (item: MentionItem) => void;
  onClose: () => void;
  loading?: boolean;
  anchorRef: React.RefObject<HTMLTextAreaElement | null>;
}

export default function MentionDropdown({
  items,
  search,
  position,
  selectedIndex,
  onSelect,
  onClose,
  loading,
  anchorRef,
}: MentionDropdownProps) {
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selectedIndex >= 0 && listRef.current) {
      const el = listRef.current.children[selectedIndex] as HTMLElement;
      el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [selectedIndex]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (anchorRef.current?.contains(target) || listRef.current?.contains(target)) return;
      onClose();
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose, anchorRef]);

  if (!position) return null;

  return (
    <div
      ref={listRef}
      className="absolute z-[100] rounded-md border border-gray-200 bg-white shadow-lg py-1 min-w-[220px] max-h-[200px] overflow-y-auto"
      style={{ top: position.top, left: position.left }}
    >
      {loading ? (
        <div className="px-3 py-2 text-xs text-gray-500">Loading…</div>
      ) : items.length === 0 ? (
        <div className="px-3 py-2 text-xs text-gray-500">
          {search ? `No matches for "${search}"` : 'Type to search schemas, prompts, tags'}
        </div>
      ) : (
        items.map((item, i) => (
          <button
            key={`${item.type}-${item.id}`}
            type="button"
            onClick={() => onSelect(item)}
            className={`block w-full text-left px-3 py-1.5 text-xs ${
              i === selectedIndex ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-50'
            }`}
          >
            <span className="font-medium">{item.label}</span>
            {item.subtitle && (
              <span className="ml-1 text-gray-500">({item.subtitle})</span>
            )}
          </button>
        ))
      )}
    </div>
  );
}

/** Fetch and merge schemas, prompts, tags into MentionItem[] with optional name filter */
export async function fetchMentionItems(
  api: {
    listSchemas: (p?: { skip?: number; limit?: number; nameSearch?: string }) => Promise<{ schemas: Array<{ schema_revid: string; name: string; schema_version: number }> }>;
    listPrompts: (p?: { skip?: number; limit?: number; nameSearch?: string }) => Promise<{ prompts: Array<{ prompt_revid: string; name: string; prompt_version: number }> }>;
    listTags: (p?: { skip?: number; limit?: number; nameSearch?: string }) => Promise<{ tags: Array<{ id: string; name: string }> }>;
  },
  search: string
): Promise<MentionItem[]> {
  const limit = 15;
  const nameSearch = search.trim() || undefined;
  const [schemasRes, promptsRes, tagsRes] = await Promise.all([
    api.listSchemas({ skip: 0, limit, nameSearch }),
    api.listPrompts({ skip: 0, limit, nameSearch }),
    api.listTags({ skip: 0, limit, nameSearch }),
  ]);
  const items: MentionItem[] = [];
  for (const s of schemasRes.schemas) {
    items.push({
      type: 'schema',
      id: s.schema_revid,
      label: s.name,
      subtitle: `v${s.schema_version}`,
    });
  }
  for (const p of promptsRes.prompts) {
    items.push({
      type: 'prompt',
      id: p.prompt_revid,
      label: p.name,
      subtitle: `v${p.prompt_version}`,
    });
  }
  for (const t of tagsRes.tags) {
    items.push({
      type: 'tag',
      id: t.id,
      label: t.name,
    });
  }
  return items;
}
