'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import type { Tag } from '@docrouter/sdk';
import type { DocRouterOrgApi } from '@/utils/api';
import { isColorLight } from '@/utils/colors';
import { flowInputClass, flowLabelClass } from './flowUiClasses';

const SEARCH_DEBOUNCE_MS = 250;
const PAGE_SIZE = 50;

type TagRow = Pick<Tag, 'id' | 'name' | 'color'>;

type ResolvedTag = {
  id: string;
  name: string | null;
  color: string | null;
  deleted: boolean;
};

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

function coerceTagIds(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .filter((id): id is string => typeof id === 'string' && id.trim().length > 0)
      .map((id) => id.trim());
  }
  return [];
}

function isNotFoundError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    (error as { status?: number }).status === 404
  );
}

async function resolveTag(api: DocRouterOrgApi, id: string): Promise<ResolvedTag> {
  try {
    const tag = await api.getTag({ tagId: id });
    return { id, name: tag.name, color: tag.color, deleted: false };
  } catch (error) {
    return { id, name: null, color: null, deleted: isNotFoundError(error) };
  }
}

function TagChip({
  tag,
  onRemove,
  readOnly,
}: {
  tag: ResolvedTag;
  onRemove?: () => void;
  readOnly?: boolean;
}) {
  if (tag.deleted) {
    return (
      <span className="inline-flex items-center gap-1 rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs">
        <span className="font-mono text-[10px] text-gray-600">{tag.id}</span>
        <span className="text-[10px] font-medium uppercase tracking-wide text-gray-400">deleted</span>
        {!readOnly && onRemove ? (
          <button
            type="button"
            className="ml-0.5 text-gray-500 hover:text-red-600"
            onClick={onRemove}
            aria-label="Remove tag"
          >
            ×
          </button>
        ) : null}
      </span>
    );
  }

  const bgColor = tag.color || '#9CA3AF';
  const textColor = isColorLight(bgColor) ? 'text-gray-800' : 'text-white';
  return (
    <span
      className={`inline-flex items-center px-2 py-1 text-sm leading-none shadow-sm ${textColor} rounded`}
      style={{ backgroundColor: bgColor }}
    >
      {tag.name || tag.id}
      {!readOnly && onRemove ? (
        <button
          type="button"
          className={`ml-1 text-xs font-bold hover:opacity-80 ${
            isColorLight(bgColor) ? 'text-gray-700 hover:text-red-600' : 'text-white/90 hover:text-red-200'
          }`}
          onClick={onRemove}
          aria-label="Remove tag"
        >
          ×
        </button>
      ) : null}
    </span>
  );
}

function TagOptionChip({ tag, selected }: { tag: TagRow; selected: boolean }) {
  const bgColor = tag.color || '#9CA3AF';
  const textColor = isColorLight(bgColor) ? 'text-gray-800' : 'text-white';
  return (
    <span
      className={`inline-flex items-center px-2 py-1 text-sm leading-none shadow-sm ${textColor} rounded ${
        selected ? 'ring-2 ring-blue-400 ring-offset-1' : ''
      }`}
      style={{ backgroundColor: bgColor }}
    >
      {tag.name}
    </span>
  );
}

export const FlowOrgTagMultiPickerField: React.FC<{
  label: string;
  description?: string;
  value: unknown;
  readOnly?: boolean;
  flowOrgApi: DocRouterOrgApi | null | undefined;
  onChange: (tagIds: string[]) => void;
}> = ({ label, description, value, readOnly = false, flowOrgApi, onChange }) => {
  const selectedIds = useMemo(() => coerceTagIds(value), [value]);
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebouncedValue(query, SEARCH_DEBOUNCE_MS);
  const [rows, setRows] = useState<TagRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [resolvedById, setResolvedById] = useState<Record<string, ResolvedTag>>({});

  useEffect(() => {
    if (!flowOrgApi || selectedIds.length === 0) {
      setResolvedById({});
      return;
    }
    let cancelled = false;
    void (async () => {
      const entries = await Promise.all(selectedIds.map((id) => resolveTag(flowOrgApi, id)));
      if (!cancelled) {
        setResolvedById(Object.fromEntries(entries.map((entry) => [entry.id, entry])));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [flowOrgApi, selectedIds]);

  const loadRows = useCallback(async () => {
    if (!flowOrgApi) {
      setRows([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const res = await flowOrgApi.listTags({
        skip: 0,
        limit: PAGE_SIZE,
        nameSearch: debouncedQuery.trim() || undefined,
      });
      setRows(
        res.tags.map((t: Tag) => ({
          id: t.id,
          name: t.name,
          color: t.color,
        })),
      );
      setTotal(res.total_count ?? res.tags.length);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Failed to load tags');
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [flowOrgApi, debouncedQuery]);

  useEffect(() => {
    void loadRows();
  }, [loadRows]);

  const listHint = useMemo(() => {
    if (!flowOrgApi) return 'Organization API unavailable.';
    if (loading) return 'Loading…';
    if (loadError) return loadError;
    if (total > rows.length) {
      return `Showing ${rows.length} of ${total}. Refine search to find more.`;
    }
    if (rows.length === 0) return 'No matches.';
    return null;
  }, [flowOrgApi, loading, loadError, total, rows.length]);

  const toggleTag = (tagId: string) => {
    if (selectedIds.includes(tagId)) {
      onChange(selectedIds.filter((id) => id !== tagId));
      return;
    }
    onChange([...selectedIds, tagId]);
  };

  const selectedTags = selectedIds.map((id) => resolvedById[id] ?? { id, name: null, color: null, deleted: false });

  if (readOnly) {
    return (
      <div className="mb-3">
        <span className={flowLabelClass}>{label}</span>
        <div className={`${flowInputClass} flex flex-wrap items-center gap-2`}>
          {selectedTags.length === 0 ? (
            <span className="text-gray-500">Any tag</span>
          ) : (
            selectedTags.map((tag) => <TagChip key={tag.id} tag={tag} readOnly />)
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="mb-3">
      <label className={flowLabelClass} htmlFor="org-tag-multi-search">
        {label}
      </label>
      {description ? <p className="mb-1.5 text-[11px] leading-snug text-gray-500">{description}</p> : null}
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {selectedTags.length === 0 ? (
          <span className="text-sm text-gray-500">Any tag</span>
        ) : (
          selectedTags.map((tag) => (
            <TagChip key={tag.id} tag={tag} onRemove={() => toggleTag(tag.id)} />
          ))
        )}
        {selectedIds.length > 0 ? (
          <button type="button" className="text-xs text-blue-600 hover:underline" onClick={() => onChange([])}>
            Clear all
          </button>
        ) : null}
      </div>
      <div className="relative">
        <MagnifyingGlassIcon
          className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
          aria-hidden
        />
        <input
          id="org-tag-multi-search"
          type="search"
          role="combobox"
          aria-expanded={rows.length > 0}
          aria-controls="org-tag-multi-list"
          autoComplete="off"
          placeholder="Search tags…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className={`${flowInputClass} pl-9`}
          disabled={!flowOrgApi}
        />
      </div>
      {listHint ? <p className="mt-1 text-[11px] text-gray-500">{listHint}</p> : null}
      <div
        id="org-tag-multi-list"
        role="listbox"
        aria-label={label}
        aria-multiselectable="true"
        className="mt-2 max-h-[min(220px,35vh)] overflow-y-auto rounded-md border border-gray-200 bg-gray-50/80"
      >
        {rows.map((row) => {
          const selected = selectedIds.includes(row.id);
          return (
            <button
              key={row.id}
              type="button"
              role="option"
              aria-selected={selected}
              className={`flex w-full items-center justify-between gap-2 border-b border-gray-100 px-3 py-2 text-left text-sm last:border-b-0 hover:bg-white ${
                selected ? 'bg-blue-50' : 'text-gray-800'
              }`}
              onClick={() => toggleTag(row.id)}
            >
              <TagOptionChip tag={row} selected={selected} />
              {selected ? <span className="shrink-0 text-xs font-medium text-blue-700">Selected</span> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
};
