import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogBackdrop,
  DialogPanel,
  DialogTitle,
  Disclosure,
  DisclosureButton,
  DisclosurePanel,
  Menu,
  MenuButton,
  MenuItem,
  MenuItems,
  Tab,
  TabGroup,
  TabList,
  TabPanel,
  TabPanels,
} from '@headlessui/react';
import { BeakerIcon, ChevronRightIcon, EllipsisVerticalIcon, MapPinIcon as MapPinOutlineIcon } from '@heroicons/react/24/outline';
import { MapPinIcon as MapPinSolidIcon, PencilSquareIcon, XMarkIcon } from '@heroicons/react/24/solid';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import Editor from '@monaco-editor/react';
import type { Edge } from 'reactflow';
import type { FlowNode, FlowNodeType, FlowPinData, FlowPinItem, FlowPinNodeOutput } from '@docrouter/sdk';
import type { DocRouterOrgApi } from '@/utils/api';
import { FlowNodeParameterFields, FlowNodeSettingsFields } from './flowNodeConfigFields';
import { FlowNodeCredentialSlots } from './flowNodeCredentialSlots';
import {
  buildNodeInputPreview,
  buildNodeOutputPreview,
  runDataMergedWithPins,
  soleInboundParentFromEdges,
} from './flowNodeIoPreview';
import { NodeRunErrorDetails } from './flowNodeRunErrorDetails';
import { FlowInputUpstreamList } from './FlowInputUpstreamList';
import { FlowNodeTypeIcon } from './FlowNodeTypeIcon';
import { FLOW_VALUE_MIME, IoViewer } from './IoViewer';
import {
  flowInlineNameInputClass,
  flowInlineNameMeasureClass,
  flowInlineNameReadClass,
} from './flowUiClasses';
import type { ExpressionPreviewContext } from './FlowExpressionPreviewLine';
import { useInlineNameWidthPx } from './useInlineNameWidthPx';
import { FlowModalSideNavStraddle } from './FlowCanvasViewTabs';
import {
  flowWorkspaceDropdownItemSimpleClass,
  flowWorkspaceMenuPanelClass,
  flowWorkspaceMenuTriggerIconBtnClass,
} from './flowWorkspaceMenu';
import { triggerReachabilityFromGraph } from './flowTriggerReachability';
import { copyToClipboard } from '@/utils/clipboard';

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

const WEBHOOK_NODE_KEY = 'flows.trigger.webhook';

const WebhookUrlHeader: React.FC<{
  node: FlowNode;
  readOnly: boolean;
  onChange: (patch: Partial<FlowNode>) => void;
  organizationId?: string | null;
  testListenActive?: boolean;
  testListenBusy?: boolean;
  testListeningLeaf?: string | null;
  onStartWebhookTestListen?: (leaf: string) => void | Promise<void>;
  onStopWebhookTestListen?: (leaf: string) => void | Promise<void>;
}> = ({
  node,
  readOnly,
  onChange,
  organizationId = null,
  testListenActive = false,
  testListenBusy = false,
  testListeningLeaf = null,
  onStartWebhookTestListen,
  onStopWebhookTestListen,
}) => {
  const [mode, setMode] = useState<'test' | 'production'>('test');
  const leaf = (node.parameters?.webhook_leaf as string | undefined) ?? '';

  const ensureLeaf = useCallback(() => {
    if (readOnly) return;
    const cur = (node.parameters?.webhook_leaf as string | undefined) ?? '';
    if (cur && cur.trim()) return;
    const next = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : String(Date.now());
    onChange({ parameters: { ...(node.parameters ?? {}), webhook_leaf: next } });
  }, [node.parameters, onChange, readOnly]);

  useEffect(() => {
    ensureLeaf();
  }, [ensureLeaf]);

  const leafForListen = useCallback((): string => {
    const raw = (node.parameters?.webhook_leaf as string | undefined) ?? '';
    if (raw.trim()) return raw.trim();
    const generated = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : String(Date.now());
    onChange({ parameters: { ...(node.parameters ?? {}), webhook_leaf: generated } });
    return generated.trim();
  }, [node.parameters, onChange]);

  const href = useMemo(() => {
    const fastApiPrefixRaw = process.env.NEXT_PUBLIC_FASTAPI_FRONTEND_URL || '/fastapi';
    const fastApiBaseRaw = fastApiPrefixRaw.trim();
    const isAbsolute = /^https?:\/\//i.test(fastApiBaseRaw);
    const origin = typeof window !== 'undefined' ? window.location.origin : '';
    const fastApiBase = isAbsolute
      ? fastApiBaseRaw.replace(/\/$/, '')
      : `${origin}${fastApiBaseRaw.startsWith('/') ? '' : '/'}${fastApiBaseRaw}`.replace(/\/$/, '');
    const s = (leaf || '').trim();
    if (!fastApiBase || !s) return '';
    const org = (organizationId || '').trim();
    if (!org) return '';
    return mode === 'test'
      ? `${fastApiBase}/v0/orgs/${org}/flows/webhook-test/${s}`
      : `${fastApiBase}/v0/orgs/${org}/flows/webhook/${s}`;
  }, [leaf, mode, organizationId]);

  const trimmedLeaf = (leaf || '').trim();
  const listeningHere =
    Boolean(testListenActive && testListeningLeaf && trimmedLeaf && testListeningLeaf.trim() === trimmedLeaf);
  const testUrlLive = listeningHere;

  return (
    <div className="rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">Webhook URLs</div>
        <div className="flex items-center gap-2">
          <div className="inline-flex overflow-hidden rounded-md border border-gray-200 bg-white">
            <button
              type="button"
              className={[
                'px-2.5 py-1 text-[11px] font-semibold',
                mode === 'test' ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-50',
              ].join(' ')}
              onClick={() => setMode('test')}
            >
              Test URL
            </button>
            <button
              type="button"
              className={[
                'px-2.5 py-1 text-[11px] font-semibold',
                mode === 'production' ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-50',
              ].join(' ')}
              onClick={() => setMode('production')}
            >
              Production URL
            </button>
          </div>
          {onStartWebhookTestListen && !readOnly ? (
            <button
              type="button"
              disabled={testListenBusy}
              aria-pressed={listeningHere}
              className={[
                'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-semibold shadow-sm transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60',
                listeningHere
                  ? 'border-green-700 bg-green-600 text-white'
                  : 'border-red-200 bg-[#ff6d5a] text-white hover:opacity-95',
              ].join(' ')}
              onClick={() => {
                if (listeningHere) {
                  void onStopWebhookTestListen?.(trimmedLeaf || leafForListen());
                  return;
                }
                void onStartWebhookTestListen?.(leafForListen());
              }}
              title={listeningHere ? 'Stop forwarding test webhook hits to this editor snapshot' : 'Store this editor snapshot for the test webhook URL'}
            >
              {testListenBusy ? (
                <span
                  className="inline-block h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-white border-t-transparent"
                  aria-hidden
                />
              ) : null}
              {listeningHere ? 'Stop listening' : 'Listen for test event'}
            </button>
          ) : null}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <div className="min-w-0">
          {href ? (
            <>
              <a
                href={mode === 'test' && !testUrlLive ? undefined : href}
                target="_blank"
                rel="noreferrer"
                aria-disabled={mode === 'test' && !testUrlLive}
                onClick={(e) => {
                  if (mode === 'test' && !testUrlLive) {
                    e.preventDefault();
                  }
                }}
                className={[
                  'block truncate font-mono text-[12px] font-semibold',
                  mode === 'test' && !testUrlLive ? 'cursor-not-allowed text-gray-500' : 'text-blue-700 hover:underline',
                ].join(' ')}
                title={href}
              >
                {href}
              </a>
              {mode === 'test' && !testUrlLive ? (
                <div className="mt-1 text-[10px] text-gray-500">
                  Listening is off — click <span className="font-semibold">Listen for test event</span> to enable the test URL.
                </div>
              ) : null}
            </>
          ) : (
            <div className="font-mono text-[12px] text-gray-500">Set a valid UUID leaf to enable URLs.</div>
          )}
        </div>
        {href ? (
          <button
            type="button"
            className={[
              'shrink-0 rounded-md border border-gray-200 bg-white px-2 py-1 text-[11px] font-semibold hover:bg-gray-50',
              mode === 'test' && !testUrlLive ? 'cursor-not-allowed opacity-60' : 'text-gray-700',
            ].join(' ')}
            disabled={mode === 'test' && !testUrlLive}
            onClick={() => void copyToClipboard(href)}
            title="Copy URL"
          >
            Copy
          </button>
        ) : null}
      </div>
    </div>
  );
};

const VariablesAndContext: React.FC = () => (
  <Disclosure as="div" defaultOpen={false} className="mb-3 rounded border border-[#eceff2] bg-white">
    <DisclosureButton className="flex w-full items-center gap-2 border-b border-gray-100 px-2 py-1.5 text-left outline-none hover:bg-gray-50">
      {({ open }) => (
        <>
          <span className="flex h-4 w-4 shrink-0 items-center justify-center text-gray-500" aria-hidden>
            <ChevronRightIcon
              className={['h-3 w-3 transition-transform duration-150 ease-out', open ? 'rotate-90' : 'rotate-0'].join(' ')}
              strokeWidth={1.5}
            />
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[11px] font-semibold text-gray-900">Context</div>
          </div>
        </>
      )}
    </DisclosureButton>
    <DisclosurePanel className="max-h-[280px] overflow-auto text-[11px]">
      <div className="divide-y divide-gray-100">
        {(
          [
            ['_json', 'Object'],
            ['_binary', 'Object'],
          ] as const
        ).map(([name, preview]) => (
          <div key={name} className="flex items-center gap-2 px-2 py-1.5">
            <div className="h-4 w-4 shrink-0" aria-hidden />
            <div className="flex min-w-0 flex-1 items-start justify-between gap-2">
              <div
                className="min-w-0 cursor-grab truncate font-mono font-semibold text-gray-900 active:cursor-grabbing"
                draggable
                title={`Drag to insert ${name} into a parameter`}
                onDragStart={(e) => {
                  e.dataTransfer.setData(
                    FLOW_VALUE_MIME,
                    JSON.stringify({
                      kind: 'contextVar',
                      varName: name,
                      path: [],
                      exampleValue: null,
                    }),
                  );
                  e.dataTransfer.effectAllowed = 'copy';
                }}
              >
                {name}
              </div>
              <div className="min-w-0 truncate text-right font-mono text-gray-600">{preview}</div>
            </div>
          </div>
        ))}
      </div>
    </DisclosurePanel>
  </Disclosure>
);

function safeParseJson(text: string): { ok: true; value: unknown } | { ok: false; error: string } {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'Invalid JSON' };
  }
}

function nodeItemsFromRunData(runData: Record<string, unknown> | null | undefined, nodeId: string): FlowPinItem[] | null {
  if (!runData) return null;
  const rec = runData[nodeId] as { data?: { main?: Array<Array<{ json?: unknown } | null> | null> } } | undefined;
  const lane0 = rec?.data?.main?.[0];
  if (!Array.isArray(lane0)) return null;
  const items: FlowPinItem[] = [];
  for (const it of lane0) {
    if (it && typeof it === 'object' && 'json' in it) items.push({ json: (it as { json?: unknown }).json ?? null });
  }
  return items;
}

function pinNodeOutputFromItems(items: FlowPinItem[]): FlowPinNodeOutput {
  return { main: [[...items.map((i) => ({ json: i.json }))]] };
}

const FlowNodeConfigModal: React.FC<{
  open: boolean;
  onClose: () => void;
  node: FlowNode | null;
  nodeType: FlowNodeType | null;
  allNodes?: FlowNode[];
  /** When provided, upstream input rows show per-node preset icons. */
  nodeTypes?: FlowNodeType[];
  edges: Edge[];
  runData: Record<string, unknown> | null | undefined;
  /** When set (e.g. executions viewer), pass execution ids into expression preview (`_execution`, …). */
  expressionExecution?: { execution_id: string; flow_id: string; flow_revid: string } | null;
  pinData?: FlowPinData | null;
  onPinDataChange?: (next: FlowPinData | null) => void;
  onChange: (patch: Partial<FlowNode>) => void;
  onSelectNode?: (nodeId: string) => void;
  readOnly?: boolean;
  /** Run this node with upstream reuse (editor test `runData` as seed). */
  onExecuteStep?: () => void | Promise<void>;
  executeStepBusy?: boolean;
  /** When set, credential slot pickers load saved org credentials. */
  flowOrgApi?: DocRouterOrgApi | null;
  /** Begin listening on `/webhook-test/{leaf}` for this editor snapshot. */
  onStartWebhookTestListen?: (leaf: string) => void | Promise<void>;
  /** Tear down `/webhook-test/{leaf}` listener snapshot. */
  onStopWebhookTestListen?: (leaf: string) => void | Promise<void>;
  webhookTestListening?: boolean;
  webhookTestListeningLeaf?: string | null;
  webhookTestListenBusy?: boolean;
}> = ({
  open,
  onClose,
  node,
  nodeType,
  allNodes,
  nodeTypes,
  edges,
  runData,
  expressionExecution,
  pinData,
  onPinDataChange,
  onChange,
  onSelectNode,
  readOnly = false,
  onExecuteStep,
  executeStepBusy = false,
  flowOrgApi = null,
  onStartWebhookTestListen,
  onStopWebhookTestListen,
  webhookTestListening = false,
  webhookTestListeningLeaf = null,
  webhookTestListenBusy = false,
}) => {
  const [tab, setTab] = useState(0);
  const [nameHover, setNameHover] = useState(false);
  const [nameFocus, setNameFocus] = useState(false);
  const [inputIoMode, setInputIoMode] = useState<'schema' | 'table' | 'json'>('schema');
  const [outputIoMode, setOutputIoMode] = useState<'schema' | 'table' | 'json'>('schema');
  const [expressionPreviewItemIndex, setExpressionPreviewItemIndex] = useState(0);
  const measure = useInlineNameWidthPx(node?.name ?? '', 'Node name');
  const nodeId = node?.id ?? '';

  useEffect(() => {
    if (nodeId) {
      setTab(0);
      setNameHover(false);
      setNameFocus(false);
      setInputIoMode('schema');
      setOutputIoMode('schema');
      setExpressionPreviewItemIndex(0);
    }
  }, [nodeId]);

  const typedPinData = useMemo(() => pinData ?? null, [pinData]);

  const inputPreview = useMemo(() => {
    if (!node) return { slots: [] as { slot: number; fromNodeId: string; itemsJson: unknown[] }[], message: 'No node' };
    return buildNodeInputPreview(node.id, edges, runData, typedPinData);
  }, [node, edges, runData, typedPinData]);

  const expressionPreviewSlots0Count = inputPreview.slots[0]?.itemsJson?.length ?? 0;
  useEffect(() => {
    if (expressionPreviewSlots0Count === 0) return;
    if (expressionPreviewItemIndex > expressionPreviewSlots0Count - 1) {
      setExpressionPreviewItemIndex(Math.max(0, expressionPreviewSlots0Count - 1));
    }
  }, [expressionPreviewSlots0Count, expressionPreviewItemIndex]);

  const expressionPreview = useMemo((): ExpressionPreviewContext | null => {
    if (!node) return null;
    const raw = inputPreview.slots[0]?.itemsJson ?? [];
    const inputItems = raw.map((x) =>
      x != null && typeof x === 'object' && !Array.isArray(x) ? ({ ...x } as Record<string, unknown>) : {},
    );
    return {
      flowOrgApi,
      runData: runDataMergedWithPins(runData, typedPinData),
      inputItems,
      previewItemIndex: expressionPreviewItemIndex,
      onPreviewItemIndexChange: setExpressionPreviewItemIndex,
      forceFirstInputItem: nodeType?.key === 'flows.http_request',
      executionRefs:
        expressionExecution != null
          ? {
              execution_id: expressionExecution.execution_id,
              flow_id: expressionExecution.flow_id,
              flow_revid: expressionExecution.flow_revid,
            }
          : undefined,
      revisionNodes: (allNodes ?? []).map((n) => ({ ...n }) as Record<string, unknown>),
    };
  }, [
    node,
    flowOrgApi,
    runData,
    typedPinData,
    inputPreview.slots,
    expressionPreviewItemIndex,
    nodeType?.key,
    expressionExecution,
    allNodes,
  ]);

  const pinnedForNode = nodeId ? (typedPinData?.[nodeId] ?? null) : null;
  const pinnedItems = useMemo(() => {
    const lane0 = pinnedForNode?.main?.[0];
    return Array.isArray(lane0) ? lane0.filter(Boolean) : null;
  }, [pinnedForNode]);

  const runItems = useMemo(() => (nodeId ? nodeItemsFromRunData(runData, nodeId) : null), [runData, nodeId]);
  const outputItems = pinnedItems ?? runItems;
  const outputValue = useMemo(() => (outputItems ? outputItems.map((i) => i.json) : null), [outputItems]);

  const outputExecPreview = useMemo(
    () =>
      nodeId ? buildNodeOutputPreview(nodeId, runData, typedPinData) : { itemsJson: [] as unknown[], message: null as string | null },
    [nodeId, runData, typedPinData],
  );

  const outputRunError = useMemo(() => {
    if (!nodeId || !runData) return undefined;
    const rec = runData[nodeId];
    if (!rec || typeof rec !== 'object') return undefined;
    return (rec as { error?: unknown }).error;
  }, [nodeId, runData]);

  const isTrigger = Boolean(nodeType?.is_trigger);

  const nodeTypesByKeyModal = useMemo(
    () => Object.fromEntries((nodeTypes ?? []).map((nt) => [nt.key, nt])),
    [nodeTypes],
  );

  const reachFromTriggersModal = useMemo(() => {
    const list = allNodes?.length ? allNodes : node ? [node] : [];
    return triggerReachabilityFromGraph(list, edges, nodeTypesByKeyModal);
  }, [allNodes, edges, node, nodeTypesByKeyModal]);

  const executeStepDisconnected =
    Boolean(node && !isTrigger && !reachFromTriggersModal.reachable.has(node.id));

  const [pinEditOpen, setPinEditOpen] = useState(false);
  const [pinEditText, setPinEditText] = useState('');
  const [pinEditError, setPinEditError] = useState<string>('');

  const hasPin = Boolean(pinnedForNode);

  const onTogglePin = () => {
    if (readOnly) return;
    if (!onPinDataChange) return;
    const base = (typedPinData ?? {}) as FlowPinData;
    if (hasPin) {
      const { [nodeId]: removed, ...rest } = base;
      void removed;
      onPinDataChange(Object.keys(rest).length ? rest : null);
      return;
    }
    const itemsToPin = outputItems ?? [];
    const next: FlowPinData = { ...base, [nodeId]: pinNodeOutputFromItems(itemsToPin) };
    onPinDataChange(next);
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

  /** Exactly one inbound edge → upstream field drags from that parent use `_json` instead of `_node["…"].json`. */
  const soleInboundParentNodeId = useMemo(
    () => (node ? soleInboundParentFromEdges(node.id, edges) : null),
    [edges, node],
  );

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

  const upstreamNodeIcons = useMemo(() => {
    if (!nodeTypes?.length) return undefined;
    const byKey = new Map(nodeTypes.map((nt) => [nt.key, nt]));
    const m = new Map<string, { iconKey?: string | null; isTrigger?: boolean }>();
    for (const n of allNodes ?? []) {
      const nt = byKey.get(n.type);
      m.set(n.id, {
        iconKey: nt?.icon_key ?? null,
        isTrigger: Boolean(nt?.is_trigger),
      });
    }
    return m;
  }, [allNodes, nodeTypes]);

  if (!node) {
    return null;
  }

  const typeLabel = nodeType?.label ?? node.type;
  const showNameField = !readOnly && (nameHover || nameFocus);

  const downloadJson = (filename: string, data: unknown) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <Dialog open={open} onClose={onClose} className="relative z-[200]">
      <DialogBackdrop
        transition
        className="fixed inset-0 bg-black/20 transition data-[closed]:opacity-0 data-[enter]:duration-200 data-[leave]:duration-150"
      />
      <div className="fixed inset-0 flex w-screen items-center justify-center py-2 px-[calc(22px+3pt)]">
        <DialogPanel
          transition
          className="relative flex h-[min(90vh,900px)] max-h-[90vh] w-[min(1200px,90vw)] max-w-[90vw] flex-col overflow-visible rounded-lg border border-[#e2e4e8] bg-white shadow-2xl transition data-[closed]:scale-95 data-[closed]:opacity-0"
        >
          {/*
            Outer panel stays overflow-visible so FlowModalSideNavStraddle buttons (±50% translate on the edge)
            are not clipped; inner shell keeps overflow-hidden for layout + rounded chrome.
          */}
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg">
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
            <div className="flex shrink-0 items-center gap-0.5">
              <Menu as="div" className="relative inline-flex">
                <MenuButton className={flowWorkspaceMenuTriggerIconBtnClass} aria-label="More actions">
                  <EllipsisVerticalIcon className="h-5 w-5" aria-hidden />
                </MenuButton>
                <MenuItems anchor="bottom end" portal modal={false} className={flowWorkspaceMenuPanelClass}>
                  <MenuItem>
                    {({ focus }) => (
                      <button
                        type="button"
                        className={`${flowWorkspaceDropdownItemSimpleClass} w-full ${focus ? 'bg-gray-100' : ''}`}
                        onClick={() => downloadJson(`node_${node.id}.json`, node)}
                      >
                        Download
                      </button>
                    )}
                  </MenuItem>
                </MenuItems>
              </Menu>
              <button
                type="button"
                onClick={onClose}
                className="shrink-0 rounded-md p-1.5 text-gray-500 transition hover:bg-gray-100"
                aria-label="Close"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            </div>
            <DialogTitle className="sr-only">
              {typeLabel} — {node.name}
            </DialogTitle>

            <div className="relative z-0 flex min-h-0 flex-1 flex-col overflow-hidden">
            <PanelGroup direction="horizontal" className="relative z-0 flex min-h-0 flex-1 overflow-hidden">
              {!isTrigger && (
                <>
                  <Panel defaultSize={25} minSize={18} className="flex min-h-0 min-w-[260px] overflow-hidden">
                    <IoBlock title="Input">
                      {inputPreview.message && <div className="mb-2 text-sm text-[#6b7280]">{inputPreview.message}</div>}
                      {!inputPreview.message && inputPreview.slots.length > 0 && (
                        <FlowInputUpstreamList
                          slots={inputPreview.slots}
                          nodeLabelById={nodeLabelById}
                          upstreamNodeIcons={upstreamNodeIcons}
                          mode={inputIoMode}
                          onModeChange={setInputIoMode}
                          expressionConfigNodeId={node.id}
                          soleInboundParentNodeId={soleInboundParentNodeId}
                        />
                      )}
                      {!inputPreview.message && inputPreview.slots.length === 0 && (
                        <IoViewer
                          title="Input"
                          value={[]}
                          valueKind="executionItems"
                          dragSource={{
                            nodeId: node.id,
                            source: 'nodeInput',
                            ...((node.name ?? '').trim() ? { nodeDisplayName: (node.name ?? '').trim() } : {}),
                          }}
                          expressionConfigNodeId={node.id}
                          defaultMode="schema"
                          mode={inputIoMode}
                          onModeChange={setInputIoMode}
                        />
                      )}
                      {inputIoMode === 'schema' && <VariablesAndContext />}
                    </IoBlock>
                  </Panel>

                  <PanelResizeHandle className="w-px bg-[#e8eaee]" />
                </>
              )}

              <Panel defaultSize={isTrigger ? 67 : 42} minSize={28} className="flex min-h-0 min-w-[320px] overflow-hidden">
                <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
                  <TabGroup selectedIndex={tab} onChange={setTab} className="flex min-h-0 flex-1 flex-col overflow-hidden">
                    <div className="shrink-0 border-b border-[#eceff2] bg-white px-1">
                      <div className="flex items-stretch gap-2">
                        <TabList className="flex min-w-0 flex-1">
                          {(['Parameters', 'Settings'] as const).map((label) => (
                            <Tab
                              key={label}
                              className="flex-1 border-b-2 border-transparent py-2.5 text-center text-xs font-bold text-gray-600 outline-none data-[selected]:border-blue-600 data-[selected]:text-blue-800"
                            >
                              {label}
                            </Tab>
                          ))}
                        </TabList>
                        {onExecuteStep && !readOnly && !isTrigger ? (
                          <div className="flex shrink-0 items-center pr-1">
                            <button
                              type="button"
                              disabled={executeStepBusy || executeStepDisconnected}
                              onClick={() => void onExecuteStep()}
                              aria-busy={executeStepBusy}
                              className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-red-200 bg-[#ff6d5a] px-2.5 py-1.5 text-[11px] font-semibold text-white shadow-sm transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
                              title={
                                executeStepDisconnected
                                  ? 'Connect this node from at least one trigger with graph edges'
                                  : executeStepBusy
                                    ? 'Running…'
                                    : 'Run this node; upstream outputs are reused from the latest test run when available'
                              }
                            >
                              {executeStepBusy ? (
                                <span
                                  className="inline-block h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-white border-t-transparent"
                                  aria-hidden
                                />
                              ) : (
                                <BeakerIcon className="h-3.5 w-3.5 shrink-0" aria-hidden />
                              )}
                              {executeStepBusy ? 'Running…' : 'Execute step'}
                            </button>
                          </div>
                        ) : null}
                      </div>
                    </div>
                    <TabPanels className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain p-3 [scrollbar-gutter:stable]">
                      <TabPanel>
                        <div className="min-w-0 space-y-4">
                          {node && nodeType?.key === WEBHOOK_NODE_KEY ? (
                            <WebhookUrlHeader
                              node={node}
                              readOnly={readOnly}
                              onChange={onChange}
                              organizationId={flowOrgApi?.organizationId ?? null}
                              testListenActive={webhookTestListening}
                              testListenBusy={webhookTestListenBusy}
                              testListeningLeaf={webhookTestListeningLeaf}
                              onStartWebhookTestListen={onStartWebhookTestListen}
                              onStopWebhookTestListen={onStopWebhookTestListen}
                            />
                          ) : null}
                          {node && (
                            <FlowNodeParameterFields
                              readOnly={readOnly}
                              node={node}
                              nodeType={nodeType}
                              onChange={onChange}
                              expressionPreview={expressionPreview}
                              soleInboundParentNodeId={soleInboundParentNodeId}
                            />
                          )}
                          {node && (
                            <FlowNodeCredentialSlots
                              key={`${node.id}-${nodeType?.key ?? ''}`}
                              flowOrgApi={flowOrgApi}
                              node={node}
                              nodeType={nodeType}
                              onChange={onChange}
                              readOnly={readOnly}
                            />
                          )}
                        </div>
                      </TabPanel>
                      <TabPanel>
                        <FlowNodeSettingsFields readOnly={readOnly} node={node} onChange={onChange} />
                      </TabPanel>
                    </TabPanels>
                  </TabGroup>
                </div>
              </Panel>

              <PanelResizeHandle className="w-px bg-[#e8eaee]" />

              <Panel defaultSize={33} minSize={18} className="flex min-h-0 min-w-[260px] overflow-hidden">
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
                        title={hasPin ? 'Discard pinned output' : 'Pin current output for preview and execute step'}
                        aria-pressed={hasPin}
                      >
                        {hasPin ? (
                          <MapPinSolidIcon className="h-4 w-4" aria-hidden />
                        ) : (
                          <MapPinOutlineIcon className="h-4 w-4" aria-hidden strokeWidth={1.75} />
                        )}
                        {hasPin ? 'Unpin' : 'Pin'}
                      </button>
                      <button
                        type="button"
                        onClick={onOpenEditPin}
                        disabled={readOnly || !onPinDataChange}
                        className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-1 text-[11px] font-semibold text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                        title={hasPin ? 'Edit pinned output JSON' : 'Edit output JSON (saves as pin when you Save)'}
                      >
                        <PencilSquareIcon className="h-4 w-4" aria-hidden />
                        Edit
                      </button>
                    </div>
                  }
                >
                  {hasPin && <div className="mb-2 text-[11px] font-semibold text-violet-700">Using pinned output for preview</div>}
                  {!hasPin && !runData && (
                    <div className="mb-2 text-sm text-[#6b7280]">Run the workflow to see output data for this node.</div>
                  )}
                  {!hasPin && runData != null && outputExecPreview.message && (
                    <div className="mb-2 text-sm text-amber-800">{outputExecPreview.message}</div>
                  )}
                  <NodeRunErrorDetails error={outputRunError} />
                  <IoViewer
                    title={node.name || typeLabel}
                    value={outputValue ?? outputExecPreview.itemsJson ?? []}
                    valueKind="executionItems"
                    dragSource={{
                      nodeId: node.id,
                      source: 'nodeOutput',
                      ...((node.name ?? '').trim() ? { nodeDisplayName: (node.name ?? '').trim() } : {}),
                    }}
                    expressionConfigNodeId={node.id}
                    defaultMode="schema"
                    mode={outputIoMode}
                    onModeChange={setOutputIoMode}
                  />
                </IoBlock>
              </Panel>
            </PanelGroup>
          </div>
          </div>
          {onSelectNode && upstreamNodeIds.length > 0 && (
            <FlowModalSideNavStraddle side="left">
              {upstreamNodeIds.map((nid) => {
                const meta = upstreamNodeIcons?.get(nid);
                return (
                  <button
                    key={`up-${nid}`}
                    type="button"
                    title={nodeLabelById.get(nid) ?? nid}
                    onClick={() => onSelectNode(nid)}
                    className="flex h-11 w-11 items-center justify-center rounded-xl border border-[#e2e4e8] bg-white shadow-md ring-1 ring-black/5 transition hover:scale-105"
                  >
                    <FlowNodeTypeIcon
                      iconKey={meta?.iconKey}
                      fallback={meta?.isTrigger ? 'trigger' : 'process'}
                      className="h-5 w-5 shrink-0 text-gray-600"
                    />
                  </button>
                );
              })}
            </FlowModalSideNavStraddle>
          )}
          {onSelectNode && downstreamNodeIds.length > 0 && (
            <FlowModalSideNavStraddle side="right">
              {downstreamNodeIds.map((nid) => {
                const meta = upstreamNodeIcons?.get(nid);
                return (
                  <button
                    key={`dn-${nid}`}
                    type="button"
                    title={nodeLabelById.get(nid) ?? nid}
                    onClick={() => onSelectNode(nid)}
                    className="flex h-11 w-11 items-center justify-center rounded-xl border border-[#e2e4e8] bg-white shadow-md ring-1 ring-black/5 transition hover:scale-105"
                  >
                    <FlowNodeTypeIcon
                      iconKey={meta?.iconKey}
                      fallback={meta?.isTrigger ? 'trigger' : 'process'}
                      className="h-5 w-5 shrink-0 text-gray-600"
                    />
                  </button>
                );
              })}
            </FlowModalSideNavStraddle>
          )}
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
