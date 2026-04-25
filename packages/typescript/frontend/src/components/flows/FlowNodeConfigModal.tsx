import React, { useEffect, useMemo, useState } from 'react';
import { Dialog, DialogBackdrop, DialogPanel, DialogTitle } from '@headlessui/react';
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/solid';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import type { Edge } from 'reactflow';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';
import { FlowNodeParameterFields, FlowNodeSettingsFields } from './flowNodeConfigFields';
import { buildNodeInputPreview, buildNodeOutputPreview } from './flowNodeIoPreview';
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
  children: React.ReactNode;
}> = ({ title, children }) => (
  <div className="flex min-h-0 min-w-0 flex-1 flex-col border-r border-[#e8eaee] last:border-r-0">
    <div className="shrink-0 border-b border-[#eceff2] bg-[#fafbfc] px-3 py-2">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">{title}</span>
    </div>
    <div className="min-h-0 flex-1 overflow-auto p-3 text-xs text-[#1a1d21]">{children}</div>
  </div>
);

const FlowNodeConfigModal: React.FC<{
  open: boolean;
  onClose: () => void;
  node: FlowNode | null;
  nodeType: FlowNodeType | null;
  allNodes?: FlowNode[];
  edges: Edge[];
  runData: Record<string, unknown> | null | undefined;
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
  onChange,
  onSelectNode,
  readOnly = false,
}) => {
  const [tab, setTab] = useState(0);
  const [selectedInputNodeId, setSelectedInputNodeId] = useState<string>('');
  const [nameHover, setNameHover] = useState(false);
  const [nameFocus, setNameFocus] = useState(false);
  const measure = useInlineNameWidthPx(node?.name ?? '', 'Node name');

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

  const outputPreview = useMemo(() => {
    if (!node) return { data: null, message: 'No node' };
    return buildNodeOutputPreview(node.id, runData);
  }, [node, runData]);

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
                    <pre className="whitespace-pre-wrap break-words rounded border border-[#eceff2] bg-[#fbfbfc] p-2 font-mono text-[11px] leading-relaxed">
                      {JSON.stringify(
                        inputPreview.slots.map((s) => ({
                          in: s.slot,
                          from: nodeLabelById.get(s.fromNodeId) ?? s.fromNodeId,
                          item: s.payload,
                        })),
                        null,
                        2,
                      )}
                    </pre>
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
                <IoBlock title="Output">
                  {outputPreview.data != null ? (
                    <>
                      {outputPreview.message && <div className="mb-2 text-sm text-amber-800">{outputPreview.message}</div>}
                      <pre className="whitespace-pre-wrap break-words rounded border border-[#eceff2] bg-[#fbfbfc] p-2 font-mono text-[11px] leading-relaxed">
                        {JSON.stringify(outputPreview.data, null, 2)}
                      </pre>
                    </>
                  ) : (
                    <div className="text-sm text-[#6b7280]">{outputPreview.message ?? '—'}</div>
                  )}
                </IoBlock>
              </Panel>
            </PanelGroup>
          </div>
        </DialogPanel>
      </div>
    </Dialog>
  );
};

export default FlowNodeConfigModal;
