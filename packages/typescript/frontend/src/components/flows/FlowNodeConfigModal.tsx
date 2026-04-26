import React, { useEffect, useMemo, useState } from 'react';
import { Dialog, DialogBackdrop, DialogPanel, DialogTitle } from '@headlessui/react';
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from '@headlessui/react';
import { BookmarkIcon, PencilSquareIcon, TrashIcon, XMarkIcon } from '@heroicons/react/24/solid';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import Editor from '@monaco-editor/react';
import type { Edge } from 'reactflow';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';
import { FlowNodeParameterFields, FlowNodeSettingsFields } from './flowNodeConfigFields';
import { buildNodeInputPreview } from './flowNodeIoPreview';
import { IoViewer } from './IoViewer';
import {
  flowInlineNameInputClass,
  flowInlineNameMeasureClass,
  flowInlineNameReadClass,
  flowLabelClass,
  flowSelectClass,
} from './flowUiClasses';
import { useInlineNameWidthPx } from './useInlineNameWidthPx';

const IoBlock: React.FC<{
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}> = ({ title, right, children }) => (
  <div className="flex min-h-0 min-w-0 flex-1 flex-col border-r border-[#e8eaee] last:border-r-0">
    <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[#eceff2] bg-[#fafbfc] px-3 py-2">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">{title}</span>
      {right}
    </div>
    <div className="min-h-0 flex-1 overflow-auto p-3 text-xs text-[#1a1d21]">{children}</div>
  </div>
);

type FlowPinNodeOutput = { main: Array<Array<{ json: unknown }> | null> };
type FlowPinData = Record<string, FlowPinNodeOutput>;

function safeParseJson(text: string): { ok: true; value: unknown } | { ok: false; error: string } {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'Invalid JSON' };
  }
}

function nodeItemsFromRunData(runData: Record<string, unknown> | null | undefined, nodeId: string): Array<{ json: unknown }> | null {
  if (!runData) return null;
  const rec = runData[nodeId] as { data?: { main?: Array<Array<{ json?: unknown } | null> | null> } } | undefined;
  const lane0 = rec?.data?.main?.[0];
  if (!Array.isArray(lane0)) return null;
  const items: Array<{ json: unknown }> = [];
  for (const it of lane0) {
    if (it && typeof it === 'object' && 'json' in it) items.push({ json: (it as { json?: unknown }).json ?? null });
  }
  return items;
}

function pinNodeOutputFromItems(items: Array<{ json: unknown }>): FlowPinNodeOutput {
  return { main: [[...items.map((i) => ({ json: i.json }))]] };
}

const FlowNodeConfigModal: React.FC<{
  open: boolean;
  onClose: () => void;
  node: FlowNode | null;
  nodeType: FlowNodeType | null;
  allNodes?: FlowNode[];
  edges: Edge[];
  runData: Record<string, unknown> | null | undefined;
  pinData?: Record<string, unknown> | null;
  onPinDataChange?: (next: Record<string, unknown> | null) => void;
  onChange: (patch: Partial<FlowNode>) => void;
  onSelectNode?: (nodeId: string) => void;
  readOnly?: boolean;
}> = ({
  open,
  onClose,
  node,
  nodeType,
  allNodes,
  edges,
  runData,
  pinData,
  onPinDataChange,
  onChange,
  onSelectNode,
  readOnly = false,
}) => {
  const [tab, setTab] = useState(0);
  const [selectedInputNodeId, setSelectedInputNodeId] = useState<string>('');
  const [nameHover, setNameHover] = useState(false);
  const [nameFocus, setNameFocus] = useState(false);
  const measure = useInlineNameWidthPx(node?.name ?? '', 'Node name');
  const nodeId = node?.id ?? '';

  useEffect(() => {
    if (node) {
      setTab(0);
      setSelectedInputNodeId('');
      setNameHover(false);
      setNameFocus(false);
    }
  }, [node?.id]);

  const inputPreview = useMemo(() => {
    if (!node) return { slots: [] as { slot: number; fromNodeId: string; payload: unknown }[], message: 'No node' };
    const base = buildNodeInputPreview(node.id, edges, runData);
    const filteredSlots = selectedInputNodeId
      ? base.slots.filter((s) => s.fromNodeId === selectedInputNodeId)
      : base.slots;
    return { ...base, slots: filteredSlots };
  }, [node, edges, runData, selectedInputNodeId]);

  const typedPinData = useMemo(() => {
    if (!pinData || typeof pinData !== 'object') return null;
    return pinData as FlowPinData;
  }, [pinData]);

  const pinnedForNode = nodeId ? (typedPinData?.[nodeId] ?? null) : null;
  const pinnedItems = useMemo(() => {
    const lane0 = pinnedForNode?.main?.[0];
    return Array.isArray(lane0) ? lane0.filter(Boolean) : null;
  }, [pinnedForNode]);

  const runItems = useMemo(() => (nodeId ? nodeItemsFromRunData(runData, nodeId) : null), [runData, nodeId]);
  const outputItems = pinnedItems ?? runItems;
  const outputValue = useMemo(() => (outputItems ? outputItems.map((i) => i.json) : null), [outputItems]);

  const [pinEditOpen, setPinEditOpen] = useState(false);
  const [pinEditText, setPinEditText] = useState('');
  const [pinEditError, setPinEditError] = useState<string>('');

  const hasPin = Boolean(pinnedForNode);

  const onTogglePin = () => {
    if (readOnly) return;
    if (!onPinDataChange) return;
    const base = (typedPinData ?? {}) as FlowPinData;
    if (hasPin) {
      const { [nodeId]: _removed, ...rest } = base;
      onPinDataChange(Object.keys(rest).length ? rest : null);
      return;
    }
    const itemsToPin = outputItems ?? [];
    const next: FlowPinData = { ...base, [nodeId]: pinNodeOutputFromItems(itemsToPin) };
    onPinDataChange(next);
  };

  const onClearPin = () => {
    if (readOnly) return;
    if (!onPinDataChange) return;
    const base = (typedPinData ?? {}) as FlowPinData;
    const { [nodeId]: _removed, ...rest } = base;
    onPinDataChange(Object.keys(rest).length ? rest : null);
  };

  const onOpenEditPin = () => {
    setPinEditError('');
    setPinEditText(JSON.stringify(pinnedForNode ?? pinNodeOutputFromItems(outputItems ?? []), null, 2));
    setPinEditOpen(true);
  };

  const onSaveEditPin = () => {
    if (readOnly) return;
    if (!onPinDataChange) return;
    const parsed = safeParseJson(pinEditText);
    if (!parsed.ok) {
      setPinEditError(parsed.error);
      return;
    }
    if (!parsed.value || typeof parsed.value !== 'object') {
      setPinEditError('Pinned output must be a JSON object with shape { "main": [[{ "json": ... }]] }.');
      return;
    }
    const base = (typedPinData ?? {}) as FlowPinData;
    const next: FlowPinData = { ...base, [nodeId]: parsed.value as FlowPinNodeOutput };
    onPinDataChange(next);
    setPinEditOpen(false);
  };

  const upstreamNodeIds = useMemo(() => {
    if (!node) return [];
    const ids = new Set<string>();
    for (const e of edges) {
      if (e.target === node.id && typeof e.source === 'string') ids.add(e.source);
    }
    return Array.from(ids);
  }, [edges, node]);

  const downstreamNodeIds = useMemo(() => {
    if (!node) return [];
    const ids = new Set<string>();
    for (const e of edges) {
      if (e.source === node.id && typeof e.target === 'string') ids.add(e.target);
    }
    return Array.from(ids);
  }, [edges, node]);

  const nodeLabelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const n of allNodes ?? []) map.set(n.id, n.name || n.type);
    return map;
  }, [allNodes]);

  if (!node) {
    return null;
  }

  const typeLabel = nodeType?.label ?? node.type;
  const showNameField = !readOnly && (nameHover || nameFocus);

  return (
    <Dialog open={open} onClose={onClose} className="relative z-[200]">
      <DialogBackdrop
        transition
        className="fixed inset-0 bg-black/20 transition data-[closed]:opacity-0 data-[enter]:duration-200 data-[leave]:duration-150"
      />
      <div className="fixed inset-0 flex w-screen items-center justify-center p-2">
        <DialogPanel
          transition
          className="flex h-[min(90vh,900px)] w-[min(1400px,95vw)] max-w-[95vw] flex-col overflow-hidden rounded-lg border border-[#e2e4e8] bg-white shadow-2xl transition data-[closed]:scale-95 data-[closed]:opacity-0"
        >
          <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[#eceff2] py-2.5 pl-4 pr-2">
            <div
              className="max-w-full shrink-0"
              onMouseEnter={() => !readOnly && setNameHover(true)}
              onMouseLeave={() => !readOnly && setNameHover(false)}
            >
              <span
                ref={measure.spanRef}
                className={flowInlineNameMeasureClass}
                style={{
                  position: 'absolute',
                  visibility: 'hidden',
                  pointerEvents: 'none',
                  whiteSpace: 'pre',
                }}
                aria-hidden
              >
                {measure.basis}
              </span>
              {readOnly ? (
                <span className="block min-w-0 truncate text-sm font-semibold text-gray-900">{node.name}</span>
              ) : showNameField ? (
                <input
                  className={flowInlineNameInputClass}
                  style={measure.widthPx ? { width: `${measure.widthPx}px` } : undefined}
                  value={node.name}
                  onChange={(e) => onChange({ name: e.target.value })}
                  placeholder="Node name"
                  aria-label="Node name"
                  onFocus={() => setNameFocus(true)}
                  onBlur={() => setNameFocus(false)}
                />
              ) : (
                <span className={flowInlineNameReadClass} title={node.name.trim() ? node.name : 'Node name'}>
                  {node.name.trim() ? node.name : 'Unnamed node'}
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="shrink-0 rounded-md p-1.5 text-gray-500 transition hover:bg-gray-100"
              aria-label="Close"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>
          <DialogTitle className="sr-only">
            {typeLabel} — {node.name}
          </DialogTitle>

          <div className="relative min-h-0 flex-1">
            {onSelectNode && (upstreamNodeIds.length > 0 || downstreamNodeIds.length > 0) && (
              <div className="pointer-events-none absolute inset-0 z-10">
                <div className="absolute left-0 top-0 bottom-0 flex flex-col items-center justify-center gap-3">
                  {upstreamNodeIds.map((nid) => (
                    <button
                      key={`up-${nid}`}
                      type="button"
                      title={nodeLabelById.get(nid) ?? nid}
                      onClick={() => onSelectNode(nid)}
                      className="pointer-events-auto flex h-11 w-11 items-center justify-center rounded-xl border border-[#e2e4e8] bg-white shadow-sm transition hover:scale-110"
                    >
                      <span className="text-xs font-bold text-[#5a6270]">◀</span>
                    </button>
                  ))}
                </div>
                <div className="absolute right-0 top-0 bottom-0 flex flex-col items-center justify-center gap-3">
                  {downstreamNodeIds.map((nid) => (
                    <button
                      key={`dn-${nid}`}
                      type="button"
                      title={nodeLabelById.get(nid) ?? nid}
                      onClick={() => onSelectNode(nid)}
                      className="pointer-events-auto flex h-11 w-11 items-center justify-center rounded-xl border border-[#e2e4e8] bg-white shadow-sm transition hover:scale-110"
                    >
                      <span className="text-xs font-bold text-[#5a6270]">▶</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <PanelGroup direction="horizontal" className="h-full w-full">
              <Panel defaultSize={25} minSize={18} className="min-w-[260px]">
                <IoBlock title="Input">
                  {upstreamNodeIds.length > 1 && (
                    <div className="mb-3">
                      <label className={flowLabelClass} htmlFor="flow-input-from">
                        Input from
                      </label>
                      <select
                        id="flow-input-from"
                        className={flowSelectClass}
                        value={selectedInputNodeId}
                        onChange={(e) => setSelectedInputNodeId(e.target.value)}
                      >
                        <option value="">Auto</option>
                        {upstreamNodeIds.map((nid) => (
                          <option key={nid} value={nid}>
                            {nodeLabelById.get(nid) ?? nid}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {inputPreview.message && <div className="mb-2 text-sm text-[#6b7280]">{inputPreview.message}</div>}
                  {!inputPreview.message && inputPreview.slots.length > 0 && (
                    <div className="space-y-3">
                      {inputPreview.slots.map((s) => (
                        <IoViewer
                          key={`${s.fromNodeId}:${s.slot}`}
                          title={`in ${s.slot} ← ${nodeLabelById.get(s.fromNodeId) ?? s.fromNodeId}`}
                          value={s.payload}
                          dragSource={{ nodeId: s.fromNodeId, source: 'nodeOutput' }}
                          defaultMode="schema"
                        />
                      ))}
                    </div>
                  )}
                </IoBlock>
              </Panel>

              <PanelResizeHandle className="w-px bg-[#e8eaee]" />

              <Panel defaultSize={42} minSize={28} className="min-w-[320px]">
                <div className="flex min-h-0 min-w-0 flex-1 flex-col">
                  <TabGroup selectedIndex={tab} onChange={setTab} className="flex min-h-0 flex-1 flex-col">
                    <div className="shrink-0 border-b border-[#eceff2] bg-white px-1">
                      <TabList className="flex w-full">
                        {(['Parameters', 'Settings'] as const).map((label) => (
                          <Tab
                            key={label}
                            className="flex-1 border-b-2 border-transparent py-2.5 text-center text-xs font-bold text-gray-600 outline-none data-[selected]:border-blue-600 data-[selected]:text-blue-800"
                          >
                            {label}
                          </Tab>
                        ))}
                      </TabList>
                    </div>
                    <TabPanels className="min-h-0 flex-1 overflow-y-auto p-3">
                      <TabPanel>
                        <FlowNodeParameterFields readOnly={readOnly} node={node} nodeType={nodeType} onChange={onChange} />
                      </TabPanel>
                      <TabPanel>
                        <FlowNodeSettingsFields readOnly={readOnly} node={node} onChange={onChange} />
                      </TabPanel>
                    </TabPanels>
                  </TabGroup>
                </div>
              </Panel>

              <PanelResizeHandle className="w-px bg-[#e8eaee]" />

              <Panel defaultSize={33} minSize={18} className="min-w-[260px]">
                <IoBlock
                  title="Output"
                  right={
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={onTogglePin}
                        disabled={readOnly || !onPinDataChange}
                        className={[
                          'inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-semibold',
                          hasPin ? 'border-violet-200 bg-violet-50 text-violet-800' : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50',
                          (readOnly || !onPinDataChange) ? 'cursor-not-allowed opacity-50' : '',
                        ].join(' ')}
                        title={hasPin ? 'Unpin output' : 'Pin output'}
                      >
                        <BookmarkIcon className="h-4 w-4" aria-hidden />
                        {hasPin ? 'Pinned' : 'Pin'}
                      </button>
                      <button
                        type="button"
                        onClick={onOpenEditPin}
                        disabled={readOnly || !onPinDataChange}
                        className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-1 text-[11px] font-semibold text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                        title="Edit pinned output"
                      >
                        <PencilSquareIcon className="h-4 w-4" aria-hidden />
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={onClearPin}
                        disabled={!hasPin || readOnly || !onPinDataChange}
                        className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-1 text-[11px] font-semibold text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                        title="Clear pin"
                      >
                        <TrashIcon className="h-4 w-4" aria-hidden />
                        Clear
                      </button>
                    </div>
                  }
                >
                  {!runData && !hasPin && <div className="text-sm text-[#6b7280]">Run the workflow to see output data for this node.</div>}
                  {hasPin && <div className="mb-2 text-[11px] font-semibold text-violet-700">Using pinned output for preview</div>}
                  {outputValue != null ? (
                    <IoViewer title={node.name || typeLabel} value={outputValue} dragSource={{ nodeId: node.id, source: 'nodeOutput' }} defaultMode="table" />
                  ) : (
                    <div className="text-sm text-[#6b7280]">No output items.</div>
                  )}
                </IoBlock>
              </Panel>
            </PanelGroup>
          </div>
        </DialogPanel>
      </div>

      <Dialog open={pinEditOpen} onClose={() => setPinEditOpen(false)} className="relative z-[250]">
        <DialogBackdrop className="fixed inset-0 bg-black/30" />
        <div className="fixed inset-0 flex items-center justify-center p-3">
          <DialogPanel className="w-[min(900px,95vw)] overflow-hidden rounded-lg border border-gray-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
              <div className="text-sm font-semibold text-gray-900">Edit pinned output</div>
              <button
                type="button"
                onClick={() => setPinEditOpen(false)}
                className="rounded-md p-1.5 text-gray-600 hover:bg-gray-100"
                aria-label="Close"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            {pinEditError && <div className="border-b border-gray-100 px-4 py-2 text-sm text-red-600">{pinEditError}</div>}
            <div className="p-3">
              <div className="rounded border border-gray-200">
                <Editor
                  height="520px"
                  language="json"
                  value={pinEditText}
                  onChange={(val) => {
                    setPinEditError('');
                    setPinEditText(val ?? '');
                  }}
                  options={{
                    minimap: { enabled: false },
                    fontSize: 12,
                    scrollBeyondLastLine: false,
                    wordWrap: 'on',
                    readOnly: readOnly || !onPinDataChange,
                  }}
                />
              </div>
              <div className="mt-2 text-xs text-gray-500">
                Shape: <span className="font-mono">{`{ "<node_id>": { "main": [[{ "json": ... }]] } }`}</span>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-gray-100 px-4 py-3">
              <button
                type="button"
                onClick={() => setPinEditOpen(false)}
                className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm font-semibold text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onSaveEditPin}
                disabled={readOnly || !onPinDataChange}
                className="rounded-md bg-violet-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Save
              </button>
            </div>
          </DialogPanel>
        </div>
      </Dialog>
    </Dialog>
  );
};

export default FlowNodeConfigModal;
