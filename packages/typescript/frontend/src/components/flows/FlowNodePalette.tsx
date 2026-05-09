import React, { useEffect, useMemo, useState } from 'react';
import type { FlowNodeType } from '@docrouter/sdk';
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import { FlowNodeTypeIcon } from './FlowNodeTypeIcon';
import {
  FLOW_PALETTE_SECTION_ORDER,
  paletteSectionDescription,
  paletteSectionForNodeType,
  paletteSectionLabel,
  paletteSectionMatchesQuery,
  type FlowPaletteSectionId,
} from './flowPaletteGroups';

function emptyBuckets(): Record<FlowPaletteSectionId, FlowNodeType[]> {
  return {
    docrouter: [],
    app: [],
    flow: [],
    core: [],
    trigger: [],
  };
}

function nodeMatchesPaletteQuery(nt: FlowNodeType, ql: string): boolean {
  const section = paletteSectionForNodeType(nt);
  if (paletteSectionMatchesQuery(section, ql)) return true;
  const hitLabel = nt.label.toLowerCase().includes(ql);
  const hitKey = nt.key.toLowerCase().includes(ql);
  const hitDesc = nt.description && nt.description.toLowerCase().includes(ql);
  const hitCat = nt.category && nt.category.toLowerCase().includes(ql);
  const hitIcon = nt.icon_key && nt.icon_key.toLowerCase().includes(ql);
  const hitPalette = nt.palette_group && nt.palette_group.toLowerCase().includes(ql);
  return hitLabel || hitKey || Boolean(hitDesc) || Boolean(hitCat) || Boolean(hitIcon) || Boolean(hitPalette);
}

function PaletteNodeList(props: {
  title: string;
  items: FlowNodeType[];
  onNodeTypeDoubleClick?: (typeKey: string) => void;
}) {
  const { title, items, onNodeTypeDoubleClick } = props;
  return (
    <div role="region" aria-label={`${title} nodes`}>
      <ul className="list-none pb-2">
        {items.map((nt) => (
          <li key={nt.key}>
            <div
              draggable
              onDragStart={(e) => {
                e.dataTransfer.effectAllowed = 'copy';
                e.dataTransfer.setData('application/flow-node-type', nt.key);
                e.dataTransfer.setData('text/plain', nt.key);
              }}
              onDoubleClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onNodeTypeDoubleClick?.(nt.key);
              }}
              title={nt.description}
              className={[
                'group relative mx-3 flex cursor-grab select-none rounded-md border border-transparent py-2.5 pl-3 pr-2 transition active:cursor-grabbing',
                'before:absolute before:inset-y-0 before:left-0 before:z-10 before:border-l-2 before:border-transparent hover:bg-white hover:shadow-[0_1px_0_rgba(0,0,0,0.04)] hover:before:border-[#5297d9]',
              ].join(' ')}
            >
              <div
                className={[
                  'mr-3 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border',
                  nt.is_trigger ? 'border-[#f0d9d6] bg-[#fff7f6]' : 'border-[#e6eaef] bg-white',
                ].join(' ')}
                aria-hidden
              >
                <FlowNodeTypeIcon
                  iconKey={nt.icon_key}
                  fallback={nt.is_trigger ? 'trigger' : 'process'}
                  className={
                    nt.is_trigger ? 'h-[22px] w-[22px] text-[#a8b0ba]' : 'h-5 w-5 text-[#94a3b8]'
                  }
                />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[14px] font-semibold leading-tight text-[#22262b] group-hover:text-[#2066a9]">
                  {nt.label}
                </div>
                {nt.description && (
                  <div className="mt-1 line-clamp-2 text-[12px] leading-snug text-[#5d656e]">
                    {nt.description}
                  </div>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

const FlowNodePalette: React.FC<{
  nodeTypes: FlowNodeType[];
  /** When true, only search + list (title lives in the drawer header). */
  embedInDrawer?: boolean;
  /** When set with `onDrilledSectionChange`, drill state is controlled (e.g. FlowEditor header). */
  drilledSection?: FlowPaletteSectionId | null;
  onDrilledSectionChange?: (next: FlowPaletteSectionId | null) => void;
  /** Fired when search has text (parent may clear drill and update the drawer title). */
  onSearchActiveChange?: (active: boolean) => void;
  searchInputRef?: React.Ref<HTMLInputElement>;
  /** Double-click: add an unconnected node on the canvas and open its configuration. */
  onNodeTypeDoubleClick?: (typeKey: string) => void;
  className?: string;
}> = ({
  nodeTypes,
  embedInDrawer,
  drilledSection: drilledProp,
  onDrilledSectionChange,
  onSearchActiveChange,
  searchInputRef,
  onNodeTypeDoubleClick,
  className = '',
}) => {
  const [query, setQuery] = useState('');
  const [internalDrilledSection, setInternalDrilledSection] = useState<FlowPaletteSectionId | null>(null);
  const drillControlled =
    drilledProp !== undefined && typeof onDrilledSectionChange === 'function';
  const drilledSection = drillControlled ? drilledProp! : internalDrilledSection;
  const setDrilledSection = drillControlled ? onDrilledSectionChange! : setInternalDrilledSection;

  const buckets = useMemo(() => {
    const b = emptyBuckets();
    const ql = query.trim().toLowerCase();
    for (const nt of nodeTypes) {
      if (ql && !nodeMatchesPaletteQuery(nt, ql)) continue;
      const section = paletteSectionForNodeType(nt);
      b[section].push(nt);
    }
    for (const id of FLOW_PALETTE_SECTION_ORDER) {
      b[id].sort((a, c) => a.label.localeCompare(c.label));
    }
    return b;
  }, [nodeTypes, query]);

  const searching = Boolean(query.trim());

  const visibleSections = useMemo(
    () => FLOW_PALETTE_SECTION_ORDER.filter((id) => buckets[id].length > 0),
    [buckets],
  );

  const effectiveDrill = useMemo((): FlowPaletteSectionId | null => {
    if (searching) return null;
    if (drilledSection === null) return null;
    return visibleSections.includes(drilledSection) ? drilledSection : null;
  }, [searching, drilledSection, visibleSections]);

  useEffect(() => {
    onSearchActiveChange?.(searching);
  }, [searching, onSearchActiveChange]);

  /** Keep parent drill header in sync when the palette drops out of drill (search, empty bucket, …). */
  useEffect(() => {
    if (!drillControlled || !onDrilledSectionChange) return;
    if (drilledProp !== null && effectiveDrill === null) {
      onDrilledSectionChange(null);
    }
  }, [drillControlled, drilledProp, effectiveDrill, onDrilledSectionChange]);

  const drill = effectiveDrill;
  const drillItems = drill !== null ? buckets[drill] : [];
  const drillTitle = drill !== null ? paletteSectionLabel(drill) : '';

  return (
    <div
      className={[
        'flex h-full min-h-0 flex-col',
        embedInDrawer ? '' : 'border-r border-[#dfe3e9] bg-[#fafbfc]',
        className,
      ].filter(Boolean).join(' ')}
    >
      <div className="shrink-0 border-b border-[#dfe3e9] bg-[#fafbfc] p-4">
        {!embedInDrawer && (
          <div className="text-[11px] font-semibold uppercase tracking-wide text-[#6b7280]">
            Add node
          </div>
        )}
        <div className={embedInDrawer ? '' : 'mt-2'}>
          <div className="relative">
            <MagnifyingGlassIcon
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9ca3af]"
              aria-hidden
            />
            <input
              ref={searchInputRef}
              type="search"
              value={query}
              onChange={(e) => {
                const v = e.target.value;
                setQuery(v);
                if (v.trim()) setDrilledSection(null);
              }}
              placeholder="Search nodes…"
              className="w-full rounded-md border border-[#cdd3dc] bg-white py-2 pl-10 pr-3 text-sm text-[#22262b] placeholder:text-[#8b959f] focus:border-[#5297d9] focus:outline-none focus:ring-1 focus:ring-[#5297d9]"
            />
          </div>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto bg-[#fafbfc] pb-10">
        <div className="flex flex-col">
          {searching ? (
            visibleSections.map((section) => {
              const items = buckets[section];
              const count = items.length;
              const title = paletteSectionLabel(section);
              const label = count ? `${title} (${count})` : title;
              return (
                <div key={section} className="border-b border-[#dfe3e9] last:border-b-0">
                  <div className="bg-[#fafbfc] px-4 py-3">
                    <div className="text-[13px] font-bold leading-snug text-[#22262b]">{label}</div>
                    <div className="mt-1 text-[12px] font-normal leading-snug text-[#5d656e]">
                      {paletteSectionDescription(section)}
                    </div>
                  </div>
                  <PaletteNodeList
                    title={title}
                    items={items}
                    onNodeTypeDoubleClick={onNodeTypeDoubleClick}
                  />
                </div>
              );
            })
          ) : drill !== null ? (
            <div className="flex flex-col">
              {!embedInDrawer && (
                <div className="border-b border-[#dfe3e9]">
                  <button
                    type="button"
                    onClick={() => setDrilledSection(null)}
                    className={[
                      'group relative flex w-full cursor-pointer select-none items-center gap-2 text-left',
                      'bg-[#fafbfc] py-2.5 pl-2 pr-3 text-[13px] font-bold leading-snug text-[#22262b] outline-none transition',
                      'before:absolute before:inset-y-0 before:left-0 before:border-l-2 before:border-transparent hover:before:border-[#5297d9]',
                    ].join(' ')}
                    aria-expanded
                    aria-label="Back to categories"
                  >
                    <ChevronLeftIcon className="h-3.5 w-3.5 shrink-0 text-[#7c8796]" aria-hidden />
                    <span className="min-w-0 flex-1">
                      {drillItems.length
                        ? `${drillTitle} (${drillItems.length})`
                        : drillTitle}
                    </span>
                  </button>
                </div>
              )}
              <PaletteNodeList
                title={drillTitle}
                items={drillItems}
                onNodeTypeDoubleClick={onNodeTypeDoubleClick}
              />
            </div>
          ) : (
            visibleSections.map((section) => {
              const items = buckets[section];
              const count = items.length;
              const title = paletteSectionLabel(section);
              const label = count ? `${title} (${count})` : title;
              return (
                <div key={section} className="border-b border-[#dfe3e9] last:border-b-0">
                  <button
                    type="button"
                    aria-expanded={false}
                    onClick={() => setDrilledSection(section)}
                    className={[
                      'group relative flex w-full cursor-pointer select-none items-start gap-2 text-left text-[#22262b]',
                      'bg-[#fafbfc] py-3 pl-4 pr-3 outline-none transition',
                      'before:absolute before:inset-y-0 before:left-0 before:border-l-2 before:border-transparent hover:before:border-[#5297d9]',
                    ].join(' ')}
                  >
                    <span className="min-w-0 flex-1 pr-1">
                      <span className="block text-[13px] font-bold leading-snug text-[#22262b]">
                        {label}
                      </span>
                      <span className="mt-1 block text-[12px] font-normal leading-snug text-[#5d656e]">
                        {paletteSectionDescription(section)}
                      </span>
                    </span>
                    <ChevronRightIcon
                      className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#7c8796]"
                      aria-hidden
                    />
                  </button>
                </div>
              );
            })
          )}
        </div>
        {nodeTypes.length === 0 && (
          <div className="p-4 text-sm text-[#5d656e]">No node types loaded.</div>
        )}
        {nodeTypes.length > 0 && visibleSections.length === 0 && (
          <div className="p-4 text-sm text-[#5d656e]">No nodes match your search.</div>
        )}
      </div>
    </div>
  );
};

export default FlowNodePalette;
