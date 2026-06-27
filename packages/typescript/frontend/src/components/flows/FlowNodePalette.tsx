import React, { useEffect, useMemo, useState } from 'react';
import type { FlowNodeType } from '@docrouter/sdk';
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import { FlowNodeTypeIcon } from './FlowNodeTypeIcon';
import { flowNodeIconColorClass, flowNodePaletteIconWellClass, isDocRouterNodeType } from './flowNodeBrand';
import {
  FLOW_PALETTE_SECTION_ORDER,
  paletteSectionDescription,
  paletteSectionForNodeType,
  paletteSectionLabel,
  paletteSectionMatchesQuery,
  type FlowPaletteSectionId,
} from './flowPaletteGroups';
import {
  nodeTypeHasPaletteActions,
  paletteActionGroupsForNodeType,
  setFlowNodeDragData,
  type FlowPaletteAction,
  type FlowPalettePlacement,
} from './flowPaletteActions';

function emptyBuckets(): Record<FlowPaletteSectionId, FlowNodeType[]> {
  return Object.fromEntries(
    FLOW_PALETTE_SECTION_ORDER.map((id) => [id, [] as FlowNodeType[]]),
  ) as Record<FlowPaletteSectionId, FlowNodeType[]>;
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

const paletteNodeRowClass = [
  'group relative mx-3 flex cursor-grab select-none rounded-md border border-transparent py-2.5 pl-3 pr-2 transition active:cursor-grabbing',
  'before:absolute before:inset-y-0 before:left-0 before:z-10 before:border-l-2 before:border-transparent hover:bg-white hover:shadow-[0_1px_0_rgba(0,0,0,0.04)] hover:before:border-[#5297d9]',
].join(' ');

function PaletteNodeList(props: {
  title: string;
  items: FlowNodeType[];
  onNodeTypeClick?: (nt: FlowNodeType) => void;
  onNodeTypeDoubleClick?: (placement: FlowPalettePlacement) => void;
}) {
  const { title, items, onNodeTypeClick, onNodeTypeDoubleClick } = props;
  return (
    <div role="region" aria-label={`${title} nodes`}>
      <ul className="list-none pb-2">
        {items.map((nt) => {
          const hasActions = nodeTypeHasPaletteActions(nt);
          const isDocRouter = isDocRouterNodeType(nt);
          return (
            <li key={nt.key}>
              <div
                draggable
                onDragStart={(e) => {
                  setFlowNodeDragData(e.dataTransfer, { typeKey: nt.key });
                }}
                onClick={(e) => {
                  if (!hasActions) return;
                  e.preventDefault();
                  e.stopPropagation();
                  onNodeTypeClick?.(nt);
                }}
                onDoubleClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onNodeTypeDoubleClick?.({ typeKey: nt.key });
                }}
                title={nt.description}
                className={paletteNodeRowClass}
              >
                <div
                  className={[
                    'mr-3 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border',
                    flowNodePaletteIconWellClass({ isDocRouter, isTrigger: Boolean(nt.is_trigger) }),
                  ].join(' ')}
                  aria-hidden
                >
                  <FlowNodeTypeIcon
                    iconKey={nt.icon_key}
                    fallback={nt.is_trigger ? 'trigger' : 'process'}
                    className={[
                      nt.is_trigger ? 'h-[22px] w-[22px]' : 'h-5 w-5',
                      flowNodeIconColorClass({ isDocRouter, isTrigger: Boolean(nt.is_trigger) }),
                    ].join(' ')}
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
                {hasActions ? (
                  <ChevronRightIcon className="mt-1 h-3.5 w-3.5 shrink-0 text-[#7c8796]" aria-hidden />
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function PaletteActionList(props: {
  nodeType: FlowNodeType;
  onActionDoubleClick?: (placement: FlowPalettePlacement) => void;
}) {
  const { nodeType, onActionDoubleClick } = props;
  const groups = useMemo(() => paletteActionGroupsForNodeType(nodeType), [nodeType]);
  const actionCount = useMemo(() => groups.reduce((n, g) => n + g.actions.length, 0), [groups]);

  return (
    <div role="region" aria-label={`${nodeType.label} actions`}>
      <div className="border-b border-[#dfe3e9] bg-[#fafbfc] px-4 py-2">
        <div className="text-[12px] font-semibold text-[#5d656e]">Actions ({actionCount})</div>
      </div>
      {groups.map((group) => (
        <div key={group.label} className="border-b border-[#dfe3e9] last:border-b-0">
          <div className="bg-[#fafbfc] px-4 py-2">
            <div className="text-[11px] font-bold uppercase tracking-wide text-[#6b7280]">{group.label}</div>
          </div>
          <ul className="list-none pb-2">
            {group.actions.map((action) => (
              <PaletteActionRow
                key={action.key}
                nodeType={nodeType}
                action={action}
                onActionDoubleClick={onActionDoubleClick}
              />
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function PaletteActionRow(props: {
  nodeType: FlowNodeType;
  action: FlowPaletteAction;
  onActionDoubleClick?: (placement: FlowPalettePlacement) => void;
}) {
  const { nodeType, action, onActionDoubleClick } = props;
  const isDocRouter = isDocRouterNodeType(nodeType);
  const placement: FlowPalettePlacement = {
    typeKey: nodeType.key,
    parameters: action.parameters,
    nameHint: action.label,
  };

  return (
    <li>
      <div
        draggable
        onDragStart={(e) => {
          setFlowNodeDragData(e.dataTransfer, placement);
        }}
        onDoubleClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onActionDoubleClick?.(placement);
        }}
        className={paletteNodeRowClass}
      >
        <div
          className={[
            'mr-3 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border',
            flowNodePaletteIconWellClass({ isDocRouter, isTrigger: Boolean(nodeType.is_trigger) }),
          ].join(' ')}
          aria-hidden
        >
          <FlowNodeTypeIcon
            iconKey={nodeType.icon_key}
            fallback={nodeType.is_trigger ? 'trigger' : 'process'}
            className={[
              'h-5 w-5',
              flowNodeIconColorClass({ isDocRouter, isTrigger: Boolean(nodeType.is_trigger) }),
            ].join(' ')}
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[14px] font-semibold leading-tight text-[#22262b] group-hover:text-[#2066a9]">
            {action.label}
          </div>
        </div>
      </div>
    </li>
  );
}

const FlowNodePalette: React.FC<{
  nodeTypes: FlowNodeType[];
  /** When true, only search + list (title lives in the drawer header). */
  embedInDrawer?: boolean;
  /** When set with `onDrilledSectionChange`, drill state is controlled (e.g. FlowEditor header). */
  drilledSection?: FlowPaletteSectionId | null;
  onDrilledSectionChange?: (next: FlowPaletteSectionId | null) => void;
  /** When set with `onDrilledNodeTypeKeyChange`, node action drill is controlled by the drawer header. */
  drilledNodeTypeKey?: string | null;
  onDrilledNodeTypeKeyChange?: (next: string | null) => void;
  /** Fired when search has text (parent may clear drill and update the drawer title). */
  onSearchActiveChange?: (active: boolean) => void;
  searchInputRef?: React.Ref<HTMLInputElement>;
  /** Double-click: add an unconnected node on the canvas and open its configuration. */
  onNodeTypeDoubleClick?: (placement: FlowPalettePlacement) => void;
  className?: string;
}> = ({
  nodeTypes,
  embedInDrawer,
  drilledSection: drilledProp,
  onDrilledSectionChange,
  drilledNodeTypeKey: drilledNodeProp,
  onDrilledNodeTypeKeyChange,
  onSearchActiveChange,
  searchInputRef,
  onNodeTypeDoubleClick,
  className = '',
}) => {
  const [query, setQuery] = useState('');
  const [internalDrilledSection, setInternalDrilledSection] = useState<FlowPaletteSectionId | null>(null);
  const [internalDrilledNodeTypeKey, setInternalDrilledNodeTypeKey] = useState<string | null>(null);
  const drillControlled =
    drilledProp !== undefined && typeof onDrilledSectionChange === 'function';
  const drilledSection = drillControlled ? drilledProp! : internalDrilledSection;
  const setDrilledSection = drillControlled ? onDrilledSectionChange! : setInternalDrilledSection;

  const nodeDrillControlled =
    drilledNodeProp !== undefined && typeof onDrilledNodeTypeKeyChange === 'function';
  const drilledNodeTypeKey = nodeDrillControlled ? drilledNodeProp! : internalDrilledNodeTypeKey;
  const setDrilledNodeTypeKey = nodeDrillControlled
    ? onDrilledNodeTypeKeyChange!
    : setInternalDrilledNodeTypeKey;

  const nodeTypesByKey = useMemo(
    () => Object.fromEntries(nodeTypes.map((nt) => [nt.key, nt])),
    [nodeTypes],
  );

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

  const effectiveNodeDrill = useMemo((): string | null => {
    if (!drilledNodeTypeKey) return null;
    const nt = nodeTypesByKey[drilledNodeTypeKey];
    if (!nt || !nodeTypeHasPaletteActions(nt)) return null;
    return drilledNodeTypeKey;
  }, [drilledNodeTypeKey, nodeTypesByKey]);

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

  useEffect(() => {
    if (!nodeDrillControlled || !onDrilledNodeTypeKeyChange) return;
    if (drilledNodeProp !== null && effectiveNodeDrill === null) {
      onDrilledNodeTypeKeyChange(null);
    }
  }, [nodeDrillControlled, drilledNodeProp, effectiveNodeDrill, onDrilledNodeTypeKeyChange]);

  const drill = effectiveDrill;
  const drillItems = drill !== null ? buckets[drill] : [];
  const drillTitle = drill !== null ? paletteSectionLabel(drill) : '';
  const drilledNodeType = effectiveNodeDrill ? nodeTypesByKey[effectiveNodeDrill] ?? null : null;

  const onNodeTypeClick = (nt: FlowNodeType) => {
    if (!nodeTypeHasPaletteActions(nt)) return;
    setDrilledNodeTypeKey(nt.key);
  };

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
                if (v.trim()) {
                  setDrilledSection(null);
                  setDrilledNodeTypeKey(null);
                }
              }}
              placeholder="Search nodes…"
              className="w-full rounded-md border border-[#cdd3dc] bg-white py-2 pl-10 pr-3 text-sm text-[#22262b] placeholder:text-[#8b959f] focus:border-[#5297d9] focus:outline-none focus:ring-1 focus:ring-[#5297d9]"
            />
          </div>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto bg-[#fafbfc] pb-10">
        <div className="flex flex-col">
          {effectiveNodeDrill && drilledNodeType ? (
            <div className="flex flex-col">
              {!embedInDrawer && (
                <div className="border-b border-[#dfe3e9]">
                  <button
                    type="button"
                    onClick={() => setDrilledNodeTypeKey(null)}
                    className={[
                      'group relative flex w-full cursor-pointer select-none items-center gap-2 text-left',
                      'bg-[#fafbfc] py-2.5 pl-2 pr-3 text-[13px] font-bold leading-snug text-[#22262b] outline-none transition',
                      'before:absolute before:inset-y-0 before:left-0 before:border-l-2 before:border-transparent hover:before:border-[#5297d9]',
                    ].join(' ')}
                    aria-expanded
                    aria-label={`Back to ${drillTitle || 'nodes'}`}
                  >
                    <ChevronLeftIcon className="h-3.5 w-3.5 shrink-0 text-[#7c8796]" aria-hidden />
                    <span className="min-w-0 flex-1">{drilledNodeType.label}</span>
                  </button>
                </div>
              )}
              <PaletteActionList nodeType={drilledNodeType} onActionDoubleClick={onNodeTypeDoubleClick} />
            </div>
          ) : searching ? (
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
                    onNodeTypeClick={onNodeTypeClick}
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
                      {drillItems.length ? `${drillTitle} (${drillItems.length})` : drillTitle}
                    </span>
                  </button>
                </div>
              )}
              <PaletteNodeList
                title={drillTitle}
                items={drillItems}
                onNodeTypeClick={onNodeTypeClick}
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
