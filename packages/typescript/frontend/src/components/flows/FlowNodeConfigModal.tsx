import React, { useEffect, useMemo, useState } from 'react';
import { Dialog, DialogTitle, IconButton, MenuItem, Tab, Tabs, TextField, Tooltip } from '@mui/material';
import { XMarkIcon } from '@heroicons/react/24/solid';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import type { Edge } from 'reactflow';
import type { FlowNode, FlowNodeType } from '@docrouter/sdk';
import { FlowNodeParameterFields, FlowNodeSettingsFields } from './flowNodeConfigFields';
import { buildNodeInputPreview, buildNodeOutputPreview } from './flowNodeIoPreview';

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
  /** When true, parameters and settings are not editable (e.g. execution review). */
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

  useEffect(() => {
    if (node) {
      setTab(0);
      setSelectedInputNodeId('');
    }
  }, [node?.id]);

  const inputPreview = useMemo(() => {
    if (!node) return { slots: [] as { slot: number; fromNodeId: string; payload: unknown }[], message: 'No node' };
    const base = buildNodeInputPreview(node.id, edges, runData);
    const filteredSlots = selectedInputNodeId
      ? base.slots.filter((s) => s.fromNodeId === selectedInputNodeId)
      : base.slots;
    return { ...base, slots: filteredSlots };
  }, [node, edges, runData]);

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

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={false}
      fullWidth
      PaperProps={{
        className: 'h-[min(90vh,900px)] w-[min(1400px,95vw)] max-w-[95vw] flex flex-col overflow-hidden m-2',
      }}
    >
      <DialogTitle className="flex shrink-0 items-center justify-between gap-2 border-b border-[#eceff2] py-2.5 pl-4 pr-2 !text-base">
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">
            {nodeType?.label ?? node.type}
          </div>
          {readOnly ? (
            <div className="truncate font-semibold text-[#1a1d21]">{node.name}</div>
          ) : (
            <TextField
              value={node.name}
              onChange={(e) => onChange({ name: e.target.value })}
              size="small"
              fullWidth
              variant="standard"
              placeholder="Node name"
              InputProps={{
                disableUnderline: false,
                sx: { fontWeight: 600, color: '#1a1d21' },
              }}
              inputProps={{
                className: 'text-[16px] leading-tight',
              }}
              sx={{
                mt: 0.25,
                maxWidth: 520,
              }}
            />
          )}
        </div>
        <IconButton size="small" onClick={onClose} aria-label="Close" edge="end">
          <XMarkIcon className="h-5 w-5" />
        </IconButton>
      </DialogTitle>

      <div className="relative min-h-0 flex-1">
        {/* Floating connected-node navigation */}
        {onSelectNode && (upstreamNodeIds.length > 0 || downstreamNodeIds.length > 0) && (
          <div className="pointer-events-none absolute inset-0 z-10">
            {/* Left: upstream */}
            <div className="absolute left-0 top-0 bottom-0 flex flex-col items-center justify-center gap-3">
              {upstreamNodeIds.map((nid) => (
                <Tooltip key={`up-${nid}`} title={nodeLabelById.get(nid) ?? nid} placement="right" disableInteractive>
                  <button
                    type="button"
                    onClick={() => onSelectNode(nid)}
                    className="pointer-events-auto flex h-11 w-11 items-center justify-center rounded-xl border border-[#e2e4e8] bg-white shadow-sm transition hover:scale-110"
                  >
                    <span className="text-xs font-bold text-[#5a6270]">◀</span>
                  </button>
                </Tooltip>
              ))}
            </div>
            {/* Right: downstream */}
            <div className="absolute right-0 top-0 bottom-0 flex flex-col items-center justify-center gap-3">
              {downstreamNodeIds.map((nid) => (
                <Tooltip key={`dn-${nid}`} title={nodeLabelById.get(nid) ?? nid} placement="left" disableInteractive>
                  <button
                    type="button"
                    onClick={() => onSelectNode(nid)}
                    className="pointer-events-auto flex h-11 w-11 items-center justify-center rounded-xl border border-[#e2e4e8] bg-white shadow-sm transition hover:scale-110"
                  >
                    <span className="text-xs font-bold text-[#5a6270]">▶</span>
                  </button>
                </Tooltip>
              ))}
            </div>
          </div>
        )}

        <PanelGroup direction="horizontal" className="h-full w-full">
          <Panel defaultSize={25} minSize={18} className="min-w-[260px]">
            <IoBlock title="Input">
              {upstreamNodeIds.length > 1 && (
                <TextField
                  select
                  size="small"
                  fullWidth
                  label="Input from"
                  className="mb-3"
                  value={selectedInputNodeId}
                  onChange={(e) => setSelectedInputNodeId(e.target.value)}
                >
                  <MenuItem value="">Auto</MenuItem>
                  {upstreamNodeIds.map((nid) => (
                    <MenuItem key={nid} value={nid}>
                      {nodeLabelById.get(nid) ?? nid}
                    </MenuItem>
                  ))}
                </TextField>
              )}

              {inputPreview.message && <div className="mb-2 text-sm text-[#6b7280]">{inputPreview.message}</div>}
              {!inputPreview.message && inputPreview.slots.length > 0 && (
                <pre className="whitespace-pre-wrap break-words rounded border border-[#eceff2] bg-[#fbfbfc] p-2 font-mono text-[11px] leading-relaxed">
                  {JSON.stringify(
                    inputPreview.slots.map((s) => ({ in: s.slot, from: nodeLabelById.get(s.fromNodeId) ?? s.fromNodeId, item: s.payload })),
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
              <div className="shrink-0 border-b border-[#eceff2] bg-white px-1">
                <Tabs
                  value={tab}
                  onChange={(_, v) => setTab(v)}
                  variant="fullWidth"
                  sx={{
                    minHeight: 40,
                    '& .MuiTab-root': { minHeight: 40, textTransform: 'none', fontWeight: 700, color: '#4b5563', opacity: 1 },
                    '& .MuiTab-root.Mui-selected': { color: '#1d4ed8' },
                  }}
                >
                  <Tab label="Parameters" sx={{ fontSize: 12 }} />
                  <Tab label="Settings" sx={{ fontSize: 12 }} />
                </Tabs>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                {tab === 0 && (
                  <FlowNodeParameterFields readOnly={readOnly} node={node} nodeType={nodeType} onChange={onChange} />
                )}
                {tab === 1 && <FlowNodeSettingsFields readOnly={readOnly} node={node} onChange={onChange} />}
              </div>
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
    </Dialog>
  );
};

export default FlowNodeConfigModal;
