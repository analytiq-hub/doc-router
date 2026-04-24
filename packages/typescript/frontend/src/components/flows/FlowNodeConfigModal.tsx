import React, { useEffect, useMemo, useState } from 'react';
import { Dialog, DialogTitle, IconButton, Tab, Tabs } from '@mui/material';
import { XMarkIcon } from '@heroicons/react/24/solid';
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
  edges: Edge[];
  runData: Record<string, unknown> | null | undefined;
  onChange: (patch: Partial<FlowNode>) => void;
  /** When true, parameters and settings are not editable (e.g. execution review). */
  readOnly?: boolean;
}> = ({
  open,
  onClose,
  node,
  nodeType,
  edges,
  runData,
  onChange,
  readOnly = false,
}) => {
  const [tab, setTab] = useState(0);

  useEffect(() => {
    if (node) setTab(0);
  }, [node?.id]);

  const inputPreview = useMemo(() => {
    if (!node) return { slots: [] as { slot: number; fromNodeId: string; payload: unknown }[], message: 'No node' };
    return buildNodeInputPreview(node.id, edges, runData);
  }, [node, edges, runData]);

  const outputPreview = useMemo(() => {
    if (!node) return { data: null, message: 'No node' };
    return buildNodeOutputPreview(node.id, runData);
  }, [node, runData]);

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
          <div className="truncate font-semibold text-[#1a1d21]">{node.name}</div>
        </div>
        <IconButton size="small" onClick={onClose} aria-label="Close" edge="end">
          <XMarkIcon className="h-5 w-5" />
        </IconButton>
      </DialogTitle>

      <div className="grid min-h-0 flex-1 grid-cols-1 sm:grid-cols-3">
        <IoBlock title="Input">
          {inputPreview.message && <div className="mb-2 text-sm text-[#6b7280]">{inputPreview.message}</div>}
          {!inputPreview.message && inputPreview.slots.length > 0 && (
            <pre className="whitespace-pre-wrap break-words rounded border border-[#eceff2] bg-[#fbfbfc] p-2 font-mono text-[11px] leading-relaxed">
              {JSON.stringify(
                inputPreview.slots.map((s) => ({ in: s.slot, from: s.fromNodeId, item: s.payload })),
                null,
                2,
              )}
            </pre>
          )}
        </IoBlock>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col border-r border-[#e8eaee]">
          <div className="shrink-0 border-b border-[#eceff2] bg-white px-1">
            <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="fullWidth" sx={{ minHeight: 40 }}>
              <Tab label="Parameters" sx={{ minHeight: 40, fontSize: 12, textTransform: 'none', fontWeight: 600 }} />
              <Tab label="Settings" sx={{ minHeight: 40, fontSize: 12, textTransform: 'none', fontWeight: 600 }} />
            </Tabs>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {tab === 0 && (
              <FlowNodeParameterFields readOnly={readOnly} node={node} nodeType={nodeType} onChange={onChange} />
            )}
            {tab === 1 && <FlowNodeSettingsFields readOnly={readOnly} node={node} onChange={onChange} />}
          </div>
        </div>

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
      </div>
    </Dialog>
  );
};

export default FlowNodeConfigModal;
