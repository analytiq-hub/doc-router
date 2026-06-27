import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { BoltIcon, ChevronRightIcon, EllipsisVerticalIcon, MapPinIcon as MapPinOutlineIcon, PlayIcon } from '@heroicons/react/24/outline';
import { MapPinIcon as MapPinSolidIcon, PencilSquareIcon, XMarkIcon } from '@heroicons/react/24/solid';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import Editor from '@monaco-editor/react';
import type { Edge } from 'reactflow';
import type { FlowBinaryRef, FlowNode, FlowNodeType, FlowPinData, FlowPinItem, FlowPinNodeOutput } from '@docrouter/sdk';
import type { DocRouterOrgApi } from '@/utils/api';
import { FlowNodeParameterFields, FlowNodeSettingsFields } from './flowNodeConfigFields';
import { FlowNodeCredentialSlots } from './flowNodeCredentialSlots';
import { parameterSchemaUsesCredentialAuthenticationWidget } from './flowSchemaParameterUtils';
import {
  buildNodeInputPreview,
  buildNodeOutputPreview,
  runDataMergedWithPins,
  soleInboundParentFromEdges,
} from './flowNodeIoPreview';
import { NodeRunErrorDetails } from './flowNodeRunErrorDetails';
import { FlowNodeTracePanel, hasNodeTraceContent } from './flowNodeTracePanel';
import { FlowInputUpstreamList } from './FlowInputUpstreamList';
import { FlowNodeTypeIcon } from './FlowNodeTypeIcon';
import { flowNodeIconColorClass, isDocRouterNodeType } from './flowNodeBrand';
import type { FlowExecutionBlobContext, FlowRevisionPinBlobContext } from './flowExecutionBlob';
import { FLOW_VALUE_MIME, IoViewer, type IoDataMode } from './IoViewer';
import {
  flowInlineNameInputClass,
  flowInlineNameMeasureClass,
  flowInlineNameReadClass,
  flowPanelColResizeHandleClass,
  flowPanelColResizeHitAreaMargins,
  flowRunButtonCompactClass,
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
  <div className="flex min-h-0 min-w-0 flex-1 flex-col">
    <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[#eceff2] bg-[#fafbfc] px-3 py-2">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">{title}</span>
      {right}
    </div>
    <div className="min-h-0 flex-1 overflow-auto p-3 text-xs text-[#1a1d21]">{children}</div>
  </div>
);

const WEBHOOK_NODE_KEY = 'flows.trigger.webhook';
const SCHEDULE_NODE_KEY = 'flows.trigger.schedule';

/** Must match `MAX_PIN_UPLOAD_BYTES` in `app/routes/flows.py` pin binary upload. */
const PIN_BINARY_MAX_BYTES = 50 * 1024 * 1024;

const ScheduleTriggerTestHeader: React.FC<{
  node: FlowNode;
  readOnly: boolean;
  busy?: boolean;
  onTest?: (triggerNodeId: string) => void | Promise<void>;
  description?: string;
}> = ({
  node,
  readOnly,
  busy = false,
  onTest,
  description = 'Run this schedule once using the current editor graph. Activation is not required.',
}) => (
  <div className="rounded-md border border-gray-200 bg-gray-50/80 px-3 py-2">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="min-w-0 text-xs text-gray-600">{description}</p>
      <button
        type="button"
        disabled={readOnly || busy || !onTest}
        onClick={() => void onTest?.(node.id)}
        className={flowRunButtonCompactClass}
      >
        {busy ? (
          <span
            className="inline-block h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-white border-t-transparent"
            aria-hidden
          />
        ) : (
          <BoltIcon className="h-3.5 w-3.5 shrink-0" aria-hidden />
        )}
        {busy ? 'Running…' : 'Test trigger'}
      </button>
    </div>
  </div>
);

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
                  : 'border-primary-700/25 bg-primary-600 text-white hover:bg-primary-700',
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
    if (it && typeof it === 'object' && 'json' in it) {
      const bin = (it as { binary?: unknown }).binary;
      items.push({
        json: (it as { json?: unknown }).json ?? null,
        ...(bin && typeof bin === 'object' && !Array.isArray(bin) ? { binary: bin as Record<string, FlowBinaryRef> } : {}),
      });
    }
  }
  return items;
}

/** One pin lane row (`main[0]`) shape from upstream / run output snapshots. Must preserve refs. */
function pinLaneRowFromPinItem(item: FlowPinItem): { json: unknown; binary?: Record<string, FlowBinaryRef> } {
  const bin =
    item.binary && typeof item.binary === 'object' && !Array.isArray(item.binary)
      ? (item.binary as Record<string, FlowBinaryRef>)
      : undefined;
  if (bin != null && Object.keys(bin).length > 0) {
    return { json: item.json, binary: bin };
  }
  return { json: item.json };
}

/**
 * Persist pin_data from modal output items (`FlowPinItem[]`), including binary refs already on items.
 *
 * Caller: first-time Pin from Execute output only (`onTogglePin`); edit flow uses `pinNodeOutputFromJsonAndBinary`.
 */
function pinNodeOutputFromItems(items: FlowPinItem[]): FlowPinNodeOutput {
  return { main: [[...items.map((i) => pinLaneRowFromPinItem(i))]] };
}

function isLikelyCancelledUpload(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false;
  const o = err as { code?: unknown; name?: unknown };
  return o.code === 'ERR_CANCELED' || o.name === 'CanceledError';
}

type UiPinnedBinary = Array<Record<string, FlowBinaryRef[]>>;

function pinNodeOutputFromJsonAndBinary(args: { jsonItems: unknown[]; binaryItems: UiPinnedBinary }): FlowPinNodeOutput {
  const { jsonItems, binaryItems } = args;
  const n = Math.max(jsonItems.length, binaryItems.length);
  const out: Array<{ json: unknown; binary?: Record<string, FlowBinaryRef> }> = [];
  for (let i = 0; i < n; i++) {
    const rawJson = i < jsonItems.length ? jsonItems[i] : {};
    const json = rawJson != null && typeof rawJson === 'object' && !Array.isArray(rawJson) ? rawJson : {};
    const bin = i < binaryItems.length ? (binaryItems[i] ?? {}) : {};
    const flat: Record<string, FlowBinaryRef> = {};
    for (const [prop, refs] of Object.entries(bin)) {
      const list = Array.isArray(refs) ? refs.filter(Boolean) : [];
      for (let j = 0; j < list.length; j++) {
        const ref = list[j]!;
        const key = j === 0 ? prop : `${prop}_${j + 1}`;
        flat[key] = ref;
      }
    }
    out.push(Object.keys(flat).length ? { json, binary: flat } : { json });
  }
  return { main: [[...out.map((i) => ({ json: i.json, ...(i.binary ? { binary: i.binary } : {}) }))]] };
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
  /** Execution-level error when this node is `last_node_executed` (executions viewer). */
  executionError?: Record<string, unknown> | null;
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
  onTestScheduleTrigger?: (triggerNodeId: string) => void | Promise<void>;
  scheduleTestBusy?: boolean;
  onTestPollTrigger?: (triggerNodeId: string) => void | Promise<void>;
  pollTestBusy?: boolean;
  /** When set, Binary tab View/Download can resolve `flow_blobs:` payloads for this execution. */
  flowBlobDownloadContext?: FlowExecutionBlobContext | null;
  flowRevisionPinBlobContext?: FlowRevisionPinBlobContext | null;
  /** Flow id for revision pin-binary upload URLs. */
  flowId?: string | null;
  /** Saved revision id used for pin-binary uploads. */
  flowRevidForPins?: string | null;
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
  executionError = null,
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
  onTestScheduleTrigger,
  scheduleTestBusy = false,
  onTestPollTrigger,
  pollTestBusy = false,
  flowBlobDownloadContext = null,
  flowRevisionPinBlobContext = null,
  flowId = null,
  flowRevidForPins = null,
}) => {
  const [tab, setTab] = useState(0);
  const [nameHover, setNameHover] = useState(false);
  const [nameFocus, setNameFocus] = useState(false);
  const [inputIoMode, setInputIoMode] = useState<IoDataMode>('schema');
  const [outputIoMode, setOutputIoMode] = useState<IoDataMode>('schema');
  const [rightIoTab, setRightIoTab] = useState<'output' | 'trace'>('output');
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
      setRightIoTab('output');
      setExpressionPreviewItemIndex(0);
    }
  }, [nodeId]);

  const typedPinData = useMemo(() => pinData ?? null, [pinData]);

  const inputPreview = useMemo(() => {
    if (!node) {
      return {
        slots: [] as {
          slot: number;
          fromNodeId: string;
          itemsJson: unknown[];
          itemsBinaries: Record<string, unknown>[];
        }[],
        message: 'No node',
      };
    }
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

  const outputExecPreview = useMemo(
    () =>
      nodeId
        ? buildNodeOutputPreview(nodeId, runData, typedPinData)
        : {
            itemsJson: [] as unknown[],
            itemsBinaries: [] as Record<string, unknown>[],
            logs: [] as string[],
            message: null as string | null,
          },
    [nodeId, runData, typedPinData],
  );

  // Mirror n8n behavior: surface code-node stdout (print/log) lines to browser console during manual preview.
  const lastConsoleLogsKeyRef = React.useRef<string>('');
  useEffect(() => {
    if (!nodeId) return;
    const logs = outputExecPreview.logs ?? [];
    if (!logs.length) return;
    const key = `${nodeId}:${logs.join('')}`;
    if (key === lastConsoleLogsKeyRef.current) return;
    lastConsoleLogsKeyRef.current = key;
    try {
      const name = node?.name || nodeId;
      for (const line of logs) {
        // Logs include trailing newline; keep output readable.
        console.log(`[Flow Code: "${name}"]`, String(line).replace(/\n$/, ''));
      }
    } catch {
      // ignore console errors in restricted environments
    }
  }, [nodeId, node?.name, outputExecPreview.logs]);

  const outputHasBinary = useMemo(() => {
    for (const b of outputExecPreview.itemsBinaries ?? []) {
      if (b && typeof b === 'object' && Object.keys(b).length > 0) return true;
    }
    return false;
  }, [outputExecPreview.itemsBinaries]);

  const outputRunError = useMemo(() => {
    if (!nodeId || !runData) return undefined;
    const rec = runData[nodeId];
    if (!rec || typeof rec !== 'object') return undefined;
    return (rec as { error?: unknown }).error;
  }, [nodeId, runData]);

  const nodeRunTraceEvents = useMemo(() => {
    if (!nodeId || !runData) return undefined;
    const rec = runData[nodeId];
    if (!rec || typeof rec !== 'object') return undefined;
    return (rec as { trace?: unknown }).trace;
  }, [nodeId, runData]);

  const showTraceTab = useMemo(
    () =>
      hasNodeTraceContent({
        nodeError: outputRunError,
        executionError,
        codeLogs: outputExecPreview.logs,
        traceEvents: nodeRunTraceEvents,
      }),
    [outputRunError, executionError, outputExecPreview.logs, nodeRunTraceEvents],
  );

  useEffect(() => {
    if (rightIoTab === 'trace' && !showTraceTab) setRightIoTab('output');
  }, [rightIoTab, showTraceTab, nodeId]);

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
  const [pinEditText, setPinEditText] = useState(''); // JSON tab text (array)
  const [pinEditBinary, setPinEditBinary] = useState<UiPinnedBinary>([]);
  const [pinEditBinaryAddProp, setPinEditBinaryAddProp] = useState<Record<number, string>>({});
  const [pinEditError, setPinEditError] = useState<string>('');
  /** Per-item keyed upload progress (`onUploadProgress`); cleared when idle or modal closes. */
  const [pinBinaryUploadProgress, setPinBinaryUploadProgress] = useState<{
    itemIndex: number;
    percent: number;
  } | null>(null);
  const modalMountedRef = useRef(true);
  const pinBinaryUploadAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    modalMountedRef.current = true;
    return () => {
      modalMountedRef.current = false;
      pinBinaryUploadAbortRef.current?.abort();
      pinBinaryUploadAbortRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!pinEditOpen) {
      pinBinaryUploadAbortRef.current?.abort();
      pinBinaryUploadAbortRef.current = null;
      setPinBinaryUploadProgress(null);
    }
  }, [pinEditOpen]);

  const onPinBinaryFileInputChange = useCallback(
    async (itemIndex: number, e: React.ChangeEvent<HTMLInputElement>) => {
      const input = e.currentTarget;
      const file = input.files?.[0];
      if (!file) return;
      if (!flowOrgApi || !flowId || !flowRevidForPins) {
        input.value = '';
        return;
      }
      if (file.size > PIN_BINARY_MAX_BYTES) {
        setPinEditError(`File too large (max ${Math.round(PIN_BINARY_MAX_BYTES / (1024 * 1024))} MB).`);
        input.value = '';
        return;
      }
      setPinEditError('');
      setPinBinaryUploadProgress({ itemIndex, percent: 0 });
      const prop = (pinEditBinaryAddProp[itemIndex] ?? 'pdf').trim() || 'pdf';
      const fd = new FormData();
      fd.set('node_id', node?.id ?? '');
      fd.set('slot', '0');
      fd.set('item_index', String(itemIndex));
      fd.set('property', prop);
      fd.set('file', file);
      pinBinaryUploadAbortRef.current?.abort();
      const ac = new AbortController();
      pinBinaryUploadAbortRef.current = ac;
      try {
        const ref = await flowOrgApi.getHttpClient().postFormData<FlowBinaryRef>(
          `/v0/orgs/${flowOrgApi.organizationId}/flows/${flowId}/revisions/${flowRevidForPins}/pins/binary`,
          fd,
          {
            signal: ac.signal,
            onUploadProgress: (pe) => {
              if (!modalMountedRef.current) return;
              const total = pe.total && pe.total > 0 ? pe.total : Math.max(file.size, 1);
              const pct = Math.min(100, Math.round((100 * pe.loaded) / Math.max(total, 1)));
              setPinBinaryUploadProgress({ itemIndex, percent: pct });
            },
          },
        );
        if (!modalMountedRef.current) return;
        setPinEditBinary((cur) => {
          const next = [...cur];
          const copy = { ...(next[itemIndex] ?? {}) };
          const list = (copy[prop] ?? []).slice();
          list.push(ref);
          copy[prop] = list;
          next[itemIndex] = copy;
          return next;
        });
      } catch (err) {
        if (!modalMountedRef.current || isLikelyCancelledUpload(err)) return;
        setPinEditError(err instanceof Error ? err.message : 'Upload failed');
      } finally {
        if (pinBinaryUploadAbortRef.current === ac) pinBinaryUploadAbortRef.current = null;
        setPinBinaryUploadProgress((p) => (p?.itemIndex === itemIndex ? null : p));
        input.value = '';
      }
    },
    [flowOrgApi, flowId, flowRevidForPins, node?.id, pinEditBinaryAddProp],
  );

  const hasPin = Boolean(pinnedForNode);
  const pinUiDisabled = Boolean(readOnly || !onPinDataChange);
  const pinUiDisabledReason = null;

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
    if (pinUiDisabled) return;
    setPinEditError('');
    const lane0 = pinnedForNode?.main?.[0] ?? null;
    const seedLane = Array.isArray(lane0) ? lane0 : outputItems ?? [];
    const seedItems = seedLane.map((i) => i?.json ?? null);
    setPinEditText(JSON.stringify(seedItems, null, 2));
    const seedBin: UiPinnedBinary = seedLane.map((i) => {
      const raw = (i as unknown as { binary?: unknown }).binary;
      if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
      const out: Record<string, FlowBinaryRef[]> = {};
      for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
        if (v && typeof v === 'object' && 'storage_id' in (v as object)) out[k] = [v as FlowBinaryRef];
      }
      return out;
    });
    setPinEditBinary(seedBin);
    setPinEditBinaryAddProp({});
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
    if (!Array.isArray(parsed.value)) {
      setPinEditError('Pinned output must be a JSON array of items (e.g. [{...}, {...}] or []).');
      return;
    }
    const base = (typedPinData ?? {}) as FlowPinData;
    const next: FlowPinData = {
      ...base,
      [nodeId]: pinNodeOutputFromJsonAndBinary({ jsonItems: parsed.value, binaryItems: pinEditBinary }),
    };
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
    const m = new Map<string, { iconKey?: string | null; isTrigger?: boolean; isDocRouter?: boolean }>();
    for (const n of allNodes ?? []) {
      const nt = byKey.get(n.type);
      m.set(n.id, {
        iconKey: nt?.icon_key ?? null,
        isTrigger: Boolean(nt?.is_trigger),
        isDocRouter: isDocRouterNodeType(nt),
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
            <PanelGroup
              key={isTrigger ? 'flow-node-config-panels-2' : 'flow-node-config-panels-3'}
              direction="horizontal"
              autoSaveId={isTrigger ? 'flow-node-config-panels-2' : 'flow-node-config-panels-3'}
              className="relative z-0 flex min-h-0 flex-1 overflow-hidden"
            >
              {!isTrigger && (
                <>
                  <Panel
                    id="flow-node-config-panel-input"
                    defaultSize={25}
                    minSize={18}
                    className="flex min-h-0 min-w-0 overflow-hidden"
                  >
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
                          flowBlobDownloadContext={flowBlobDownloadContext ?? null}
                          flowRevisionPinBlobContext={flowRevisionPinBlobContext ?? null}
                        />
                      )}
                      {!inputPreview.message && inputPreview.slots.length === 0 && (
                        <IoViewer
                          title="Input"
                          value={[]}
                          valueKind="executionItems"
                          executionItemsBinaries={[]}
                          flowBlobDownloadContext={flowBlobDownloadContext ?? null}
                          flowRevisionPinBlobContext={flowRevisionPinBlobContext ?? null}
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

                  <PanelResizeHandle
                    id="flow-node-config-handle-input-params"
                    className={flowPanelColResizeHandleClass}
                    hitAreaMargins={flowPanelColResizeHitAreaMargins}
                  />
                </>
              )}

              <Panel
                id="flow-node-config-panel-params"
                defaultSize={isTrigger ? 67 : 42}
                minSize={28}
                className="flex min-h-0 min-w-0 overflow-hidden"
              >
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
                              className={flowRunButtonCompactClass}
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
                                <PlayIcon className="h-3.5 w-3.5 shrink-0" aria-hidden />
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
                          {node && nodeType?.key === SCHEDULE_NODE_KEY ? (
                            <ScheduleTriggerTestHeader
                              node={node}
                              readOnly={readOnly}
                              busy={scheduleTestBusy}
                              onTest={onTestScheduleTrigger}
                            />
                          ) : null}
                          {node && nodeType?.polling && nodeType.key !== SCHEDULE_NODE_KEY ? (
                            <ScheduleTriggerTestHeader
                              node={node}
                              readOnly={readOnly}
                              busy={pollTestBusy}
                              onTest={onTestPollTrigger}
                              description="Poll Google Drive once using the current editor graph. Activation is not required."
                            />
                          ) : null}
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
                          {node &&
                          nodeType?.credential_slots?.length &&
                          !parameterSchemaUsesCredentialAuthenticationWidget(nodeType.parameter_schema) ? (
                            <FlowNodeCredentialSlots
                              key={`${node.id}-${nodeType?.key ?? ''}-cred`}
                              placement="top"
                              flowOrgApi={flowOrgApi}
                              node={node}
                              nodeType={nodeType}
                              onChange={onChange}
                              readOnly={readOnly}
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
                              flowOrgApi={flowOrgApi}
                              edges={edges}
                              allNodes={allNodes}
                            />
                          )}
                        </div>
                      </TabPanel>
                      <TabPanel>
                        <FlowNodeSettingsFields
                          readOnly={readOnly}
                          node={node}
                          nodeType={nodeType}
                          onChange={onChange}
                        />
                      </TabPanel>
                    </TabPanels>
                  </TabGroup>
                </div>
              </Panel>

              <PanelResizeHandle
                id="flow-node-config-handle-params-output"
                className={flowPanelColResizeHandleClass}
                hitAreaMargins={flowPanelColResizeHitAreaMargins}
              />

              <Panel
                id="flow-node-config-panel-output"
                defaultSize={33}
                minSize={18}
                className="flex min-h-0 min-w-0 overflow-hidden"
              >
                <div className="flex min-h-0 min-w-0 flex-1 flex-col">
                  <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[#eceff2] bg-[#fafbfc] px-3 py-2">
                    {showTraceTab ? (
                      <div className="inline-flex rounded-md border border-gray-200 bg-white p-0.5 text-[11px]">
                        {(['output', 'trace'] as const).map((t) => (
                          <button
                            key={t}
                            type="button"
                            onClick={() => setRightIoTab(t)}
                            className={[
                              'rounded px-2 py-1 font-semibold capitalize',
                              rightIoTab === t ? 'bg-gray-900 text-white' : 'text-gray-700 hover:bg-gray-50',
                            ].join(' ')}
                          >
                            {t}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#9ca3af]">Output</span>
                    )}
                    {rightIoTab === 'output' ? (
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={onTogglePin}
                          disabled={pinUiDisabled}
                          className={[
                            'inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-semibold',
                            hasPin ? 'border-violet-200 bg-violet-50 text-violet-800' : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50',
                            pinUiDisabled ? 'cursor-not-allowed opacity-50' : '',
                          ].join(' ')}
                          title={
                            pinUiDisabledReason ??
                            (hasPin ? 'Discard pinned output' : 'Pin current output for preview and execute step')
                          }
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
                          disabled={pinUiDisabled}
                          className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-1 text-[11px] font-semibold text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                          title={
                            pinUiDisabledReason ??
                            (hasPin ? 'Edit pinned output JSON' : 'Edit output JSON (saves as pin when you Save)')
                          }
                        >
                          <PencilSquareIcon className="h-4 w-4" aria-hidden />
                          Edit
                        </button>
                      </div>
                    ) : null}
                  </div>
                  <div className="min-h-0 flex-1 overflow-auto p-3 text-xs text-[#1a1d21]">
                    {rightIoTab === 'trace' && showTraceTab ? (
                      <FlowNodeTracePanel
                        nodeError={outputRunError}
                        executionError={executionError}
                        codeLogs={outputExecPreview.logs}
                        traceEvents={nodeRunTraceEvents}
                      />
                    ) : (
                      <>
                        {hasPin && (
                          <div className="mb-2 text-[11px] font-semibold text-violet-700">Using pinned output for preview</div>
                        )}
                        {!hasPin && !runData && (
                          <div className="mb-2 text-sm text-[#6b7280]">Run the workflow to see output data for this node.</div>
                        )}
                        {!hasPin && runData != null && outputExecPreview.message && (
                          <div className="mb-2 text-sm text-amber-800">{outputExecPreview.message}</div>
                        )}
                        <NodeRunErrorDetails error={outputRunError} />
                        <IoViewer
                          title={node.name || typeLabel}
                          value={outputExecPreview.itemsJson}
                          valueKind="executionItems"
                          executionItemsBinaries={outputExecPreview.itemsBinaries}
                          flowBlobDownloadContext={flowBlobDownloadContext ?? null}
                          flowRevisionPinBlobContext={flowRevisionPinBlobContext ?? null}
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
                      </>
                    )}
                  </div>
                </div>
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
                      className={[
                        'h-5 w-5 shrink-0',
                        flowNodeIconColorClass({
                          isDocRouter: Boolean(meta?.isDocRouter),
                          isTrigger: Boolean(meta?.isTrigger),
                        }),
                      ].join(' ')}
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
                      className={[
                        'h-5 w-5 shrink-0',
                        flowNodeIconColorClass({
                          isDocRouter: Boolean(meta?.isDocRouter),
                          isTrigger: Boolean(meta?.isTrigger),
                        }),
                      ].join(' ')}
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
              <TabGroup>
                <TabList className="flex items-center gap-1 border-b border-gray-200 bg-gray-50 px-2 py-1">
                  <Tab className="rounded px-2 py-1 text-xs font-semibold text-gray-700 data-[selected]:bg-white data-[selected]:shadow-sm">
                    Json
                  </Tab>
                  <Tab className="rounded px-2 py-1 text-xs font-semibold text-gray-700 data-[selected]:bg-white data-[selected]:shadow-sm">
                    Binary
                  </Tab>
                </TabList>
                <TabPanels>
                  <TabPanel>
                    <div className="rounded border border-gray-200">
                      <Editor
                        height="420px"
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
                      Shape: <span className="font-mono">{`[ { ... }, { ... } ]`}</span>
                    </div>
                  </TabPanel>
                  <TabPanel>
                    <div className="rounded border border-gray-200 p-3">
                      {!flowOrgApi || !flowId || !flowRevidForPins ? (
                        <div className="text-sm text-gray-600">
                          Binary pin uploads need a saved revision context. Save the flow, then reopen this modal to upload pinned binaries.
                        </div>
                      ) : (
                        <div className="space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Pinned binaries</div>
                            <button
                              type="button"
                              disabled={pinBinaryUploadProgress !== null}
                              className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                              onClick={() => setPinEditBinary((cur) => [...cur, {}])}
                            >
                              Add item
                            </button>
                          </div>
                          <p className="text-[11px] text-gray-500">
                            Maximum file size {Math.round(PIN_BINARY_MAX_BYTES / (1024 * 1024))} MB per file; oversized
                            files are rejected before upload completes.
                          </p>

                          {pinEditBinary.length === 0 ? (
                            <div className="text-sm text-gray-600">No pinned binary items yet.</div>
                          ) : null}

                          {pinEditBinary.map((itemBin, itemIndex) => (
                            <div key={`bin-${itemIndex}`} className="rounded-md border border-gray-200 bg-white p-2">
                              <div className="mb-2 flex items-center justify-between">
                                <div className="text-xs font-semibold text-gray-900">{`Item ${itemIndex}`}</div>
                                <button
                                  type="button"
                                  className="text-xs font-semibold text-gray-500 hover:text-gray-700"
                                  onClick={() =>
                                    setPinEditBinary((cur) => cur.filter((_, i) => i !== itemIndex))
                                  }
                                >
                                  Remove item
                                </button>
                              </div>

                              <div className="space-y-2">
                                {Object.keys(itemBin).length === 0 ? (
                                  <div className="text-xs text-gray-500">No files.</div>
                                ) : (
                                  Object.entries(itemBin).map(([prop, refs]) => (
                                    <div key={`${itemIndex}-${prop}`} className="rounded border border-gray-100 bg-gray-50 p-2">
                                      <div className="flex items-center justify-between">
                                        <div className="text-xs font-semibold text-gray-700">{prop}</div>
                                        <button
                                          type="button"
                                          className="text-xs font-semibold text-gray-500 hover:text-gray-700"
                                          onClick={() =>
                                            setPinEditBinary((cur) => {
                                              const next = [...cur];
                                              const copy = { ...(next[itemIndex] ?? {}) };
                                              delete copy[prop];
                                              next[itemIndex] = copy;
                                              return next;
                                            })
                                          }
                                        >
                                          Remove
                                        </button>
                                      </div>
                                      <div className="mt-1 space-y-1">
                                        {(refs ?? []).map((r, idx) => (
                                          <div key={`${prop}-${idx}`} className="flex items-center justify-between text-xs text-gray-700">
                                            <div className="min-w-0 truncate font-mono">
                                              {(r.file_name ?? 'file') + (r.mime_type ? ` (${r.mime_type})` : '')}
                                            </div>
                                            <div className="flex items-center gap-2">
                                              <a
                                                className="text-blue-700 hover:underline"
                                                href={
                                                  r.storage_id
                                                    ? `/fastapi/v0/orgs/${flowOrgApi.organizationId}/flows/${flowId}/revisions/${flowRevidForPins}/pins/blob?storage_id=${encodeURIComponent(r.storage_id)}&action=view`
                                                    : undefined
                                                }
                                                target="_blank"
                                                rel="noreferrer"
                                                aria-disabled={!r.storage_id}
                                                onClick={(e) => {
                                                  if (!r.storage_id) e.preventDefault();
                                                }}
                                              >
                                                View
                                              </a>
                                              <button
                                                type="button"
                                                className="text-xs font-semibold text-gray-500 hover:text-gray-700"
                                                onClick={() =>
                                                  setPinEditBinary((cur) => {
                                                    const next = [...cur];
                                                    const copy = { ...(next[itemIndex] ?? {}) };
                                                    const list = (copy[prop] ?? []).slice();
                                                    list.splice(idx, 1);
                                                    if (list.length) copy[prop] = list;
                                                    else delete copy[prop];
                                                    next[itemIndex] = copy;
                                                    return next;
                                                  })
                                                }
                                              >
                                                Remove file
                                              </button>
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  ))
                                )}

                                <div className="flex flex-wrap items-center gap-2">
                                  <input
                                    className="w-44 rounded-md border border-gray-200 px-2 py-1 text-xs"
                                    placeholder="property name (e.g. pdf)"
                                    disabled={pinBinaryUploadProgress !== null}
                                    value={pinEditBinaryAddProp[itemIndex] ?? 'pdf'}
                                    onChange={(e) =>
                                      setPinEditBinaryAddProp((cur) => ({ ...cur, [itemIndex]: e.target.value }))
                                    }
                                  />
                                  <input
                                    type="file"
                                    disabled={pinBinaryUploadProgress !== null}
                                    className="text-xs disabled:opacity-50"
                                    onChange={(e) => void onPinBinaryFileInputChange(itemIndex, e)}
                                  />
                                </div>
                                {pinBinaryUploadProgress?.itemIndex === itemIndex ? (
                                  <div className="mt-2 max-w-xs">
                                    <div className="mb-1 text-[11px] text-gray-600">
                                      Uploading… {pinBinaryUploadProgress.percent}%
                                    </div>
                                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
                                      <div
                                        className="h-full rounded-full bg-violet-600 transition-[width] duration-150"
                                        style={{ width: `${pinBinaryUploadProgress.percent}%` }}
                                        aria-valuenow={pinBinaryUploadProgress.percent}
                                        aria-valuemin={0}
                                        aria-valuemax={100}
                                        role="progressbar"
                                      />
                                    </div>
                                  </div>
                                ) : null}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </TabPanel>
                </TabPanels>
              </TabGroup>
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
