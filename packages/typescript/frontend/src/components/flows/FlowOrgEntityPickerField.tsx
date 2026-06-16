'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import type { Prompt, Tag } from '@docrouter/sdk';
import type { DocRouterOrgApi } from '@/utils/api';
import { flowInputClass, flowLabelClass } from './flowUiClasses';

const SEARCH_DEBOUNCE_MS = 250;
const PAGE_SIZE = 50;

export type OrgEntityPickerKind = 'tag' | 'prompt';

type PickerRow = { id: string; label: string; sublabel?: string };

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

async function fetchRows(
  api: DocRouterOrgApi,
  kind: OrgEntityPickerKind,
  query: string,
): Promise<{ rows: PickerRow[]; total: number }> {
  if (kind === 'tag') {
    const res = await api.listTags({
      skip: 0,
      limit: PAGE_SIZE,
      nameSearch: query.trim() || undefined,
    });
    return {
      rows: res.tags.map((t: Tag) => ({ id: t.id, label: t.name })),
      total: res.total_count ?? res.tags.length,
    };
  }
  const res = await api.listPrompts({
    skip: 0,
    limit: PAGE_SIZE,
    nameSearch: query.trim() || undefined,
  });
  const seen = new Set<string>();
  const rows: PickerRow[] = [];
  for (const p of res.prompts as Prompt[]) {
    const pid = p.prompt_id;
    if (!pid || seen.has(pid)) continue;
    seen.add(pid);
    rows.push({
      id: pid,
      label: p.name || pid,
      sublabel: p.prompt_version ? `v${p.prompt_version}` : undefined,
    });
  }
  return { rows, total: res.total_count ?? rows.length };
}

type SelectedEntityState = {
  name: string | null;
  deleted: boolean;
};

function isNotFoundError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    (error as { status?: number }).status === 404
  );
}

async function resolveSelectedEntity(
  api: DocRouterOrgApi,
  kind: OrgEntityPickerKind,
  id: string,
): Promise<SelectedEntityState> {
  if (!id) return { name: null, deleted: false };
  try {
    if (kind === 'tag') {
      const tag = await api.getTag({ tagId: id });
      return { name: tag.name, deleted: false };
    }
    const versions = await api.listPromptVersions({ promptId: id });
    const latest = versions.prompts?.[0];
    if (latest?.name) return { name: latest.name, deleted: false };
    return { name: null, deleted: true };
  } catch (error) {
    return { name: null, deleted: isNotFoundError(error) };
  }
}

function SelectedEntityValue({
  id,
  name,
  deleted,
  emptyLabel,
}: {
  id: string;
  name: string | null;
  deleted: boolean;
  emptyLabel: string;
}) {
  if (!id) {
    return <span className="text-gray-500">{emptyLabel}</span>;
  }
  if (deleted) {
    return (
      <span className="inline-flex items-baseline gap-1.5">
        <span className="font-mono text-xs text-gray-600">{id}</span>
        <span className="text-[10px] font-medium uppercase tracking-wide text-gray-400">deleted</span>
      </span>
    );
  }
  return <span>{name || id}</span>;
}

export const FlowOrgEntityPickerField: React.FC<{
  kind: OrgEntityPickerKind;
  label: string;
  description?: string;
  value: unknown;
  readOnly?: boolean;
  flowOrgApi: DocRouterOrgApi | null | undefined;
  onChange: (id: string) => void;
}> = ({ kind, label, description, value, readOnly = false, flowOrgApi, onChange }) => {
  const selectedId = typeof value === 'string' ? value : '';
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebouncedValue(query, SEARCH_DEBOUNCE_MS);
  const [rows, setRows] = useState<PickerRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [selectedDeleted, setSelectedDeleted] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const emptyLabel = kind === 'tag' ? 'Any tag' : 'Any prompt';

  useEffect(() => {
    if (!flowOrgApi || !selectedId) {
      setSelectedName(null);
      setSelectedDeleted(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      const resolved = await resolveSelectedEntity(flowOrgApi, kind, selectedId);
      if (!cancelled) {
        setSelectedName(resolved.name);
        setSelectedDeleted(resolved.deleted);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [flowOrgApi, kind, selectedId]);

  const loadRows = useCallback(async () => {
    if (!flowOrgApi) {
      setRows([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const result = await fetchRows(flowOrgApi, kind, debouncedQuery);
      setRows(result.rows);
      setTotal(result.total);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Failed to load options');
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [flowOrgApi, kind, debouncedQuery]);

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

  if (readOnly) {
    return (
      <div className="mb-3">
        <span className={flowLabelClass}>{label}</span>
        <div className={`${flowInputClass} flex items-center`}>
          <SelectedEntityValue
            id={selectedId}
            name={selectedName}
            deleted={selectedDeleted}
            emptyLabel={emptyLabel}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="mb-3">
      <label className={flowLabelClass} htmlFor={`org-entity-${kind}-search`}>
        {label}
      </label>
      {description ? <p className="mb-1.5 text-[11px] leading-snug text-gray-500">{description}</p> : null}
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-sm text-gray-800">
          <SelectedEntityValue
            id={selectedId}
            name={selectedName}
            deleted={selectedDeleted}
            emptyLabel={emptyLabel}
          />
        </span>
        {selectedId ? (
          <button
            type="button"
            className="text-xs text-blue-600 hover:underline"
            onClick={() => onChange('')}
          >
            Clear
          </button>
        ) : null}
      </div>
      <div className="relative">
        <MagnifyingGlassIcon
          className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
          aria-hidden
        />
        <input
          id={`org-entity-${kind}-search`}
          type="search"
          role="combobox"
          aria-expanded={rows.length > 0}
          aria-controls={`org-entity-${kind}-list`}
          autoComplete="off"
          placeholder={kind === 'tag' ? 'Search tags…' : 'Search prompts…'}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className={`${flowInputClass} pl-9`}
          disabled={!flowOrgApi}
        />
      </div>
      {listHint ? <p className="mt-1 text-[11px] text-gray-500">{listHint}</p> : null}
      <div
        id={`org-entity-${kind}-list`}
        role="listbox"
        aria-label={label}
        className="mt-2 max-h-[min(220px,35vh)] overflow-y-auto rounded-md border border-gray-200 bg-gray-50/80"
      >
        {rows.map((row) => {
          const selected = row.id === selectedId;
          return (
            <button
              key={row.id}
              type="button"
              role="option"
              aria-selected={selected}
              className={`flex w-full items-center justify-between gap-2 border-b border-gray-100 px-3 py-2 text-left text-sm last:border-b-0 hover:bg-white ${
                selected ? 'bg-blue-50 font-medium text-blue-900' : 'text-gray-800'
              }`}
              onClick={() => onChange(row.id)}
            >
              <span className="truncate">{row.label}</span>
              {row.sublabel ? <span className="shrink-0 text-xs text-gray-500">{row.sublabel}</span> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
};
