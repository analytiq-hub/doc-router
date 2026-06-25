'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  Panel,
  addEdge,
  getNodesBounds,
  getViewportForBounds,
  MarkerType,
  useNodesInitialized,
  useReactFlow,
  useStore,
  type Connection,
  type Edge,
  type Node,
  applyEdgeChanges,
  applyNodeChanges,
  type EdgeChange,
  type NodeChange,
} from 'reactflow';
import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/react';
import {
  ArrowUturnLeftIcon,
  ArrowsPointingOutIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  MagnifyingGlassIcon,
  MagnifyingGlassMinusIcon,
  MagnifyingGlassPlusIcon,
  PlayIcon,
  PlusIcon,
  Square2StackIcon,
} from '@heroicons/react/24/outline';
import { XMarkIcon } from '@heroicons/react/24/solid';
import 'reactflow/dist/style.css';
import './flows-canvas.css';

import type { FlowExecution, FlowNode, FlowNodeType, FlowPinData } from '@docrouter/sdk';
import {
  flowCanvasDisplayName,
  rewriteRfNodesDisplayRefsRemove,
  rewriteRfNodesDisplayRefsRename,
} from './flowExpressionNodeRefs';
import type { DocRouterOrgApi } from '@/utils/api';
import type { FlowExecutionBlobContext, FlowRevisionPinBlobContext } from './flowExecutionBlob';
import FlowNodePalette from './FlowNodePalette';
import {
  parseFlowNodeDragPayload,
  paletteActionsForNodeType,
  type FlowPalettePlacement,
} from './flowPaletteActions';
import FlowNodeConfigModal from './FlowNodeConfigModal';
import {
  paletteSectionDescription,
  paletteSectionForNodeType,
  paletteSectionLabel,
  type FlowPaletteSectionId,
} from './flowPaletteGroups';
import { FLOW_RF_LABELED_EDGE_TYPE } from './flowRfCanvasTypes';
import { useStableFlowRfCanvasRegistration } from './useStableFlowRfCanvasRegistration';
import {
  FlowCanvasActionsProvider,
  FlowExecutionVisualProvider,
  type EdgeInsertPayload,
  type OutputAppendPayload,
} from './flowCanvasActionsContext';
import { FLOW_CANVAS_GRID_PX, snapToFlowGrid } from './canvasGrid';
import { edgesWithRunDataItemCounts } from './flowNodeIoPreview';
import { inputHandleCount, inputPortType, outputPortType, portTypesCompatible, edgeConnectionType } from './flowRf';
import type { FlowConnectionType, FlowRfNodeData } from './flowRf';
import { triggerReachabilityFromGraph } from './flowTriggerReachability';
import { flowRunButtonCanvasClass, FLOW_EXECUTE_FLOW_LABEL } from './flowUiClasses';
import { flowWorkspaceDropdownItemSimpleClass, flowWorkspaceMenuPanelClass } from './flowWorkspaceMenu';

export type FlowExecuteWorkflowTriggerOption = { id: string; label: string };

const FLOW_EDGE_MARKER = { type: MarkerType.ArrowClosed } as const;

const FLOW_EDITOR_RF_PRO_OPTIONS = { hideAttribution: true } as const;
const FLOW_EDITOR_DEFAULT_EDGE_OPTIONS = {
  type: FLOW_RF_LABELED_EDGE_TYPE,
  style: { stroke: '#a8b0bd', strokeWidth: 1.5 },
  markerEnd: FLOW_EDGE_MARKER,
} as const;

function CanvasZoomControls({
  addFooterPadding,
  runButton,
}: {
  addFooterPadding: boolean;
  runButton?: React.ReactNode;
}) {
  const { setViewport, getNodes, zoomIn, zoomOut, zoomTo } = useReactFlow();
  const nodesInitialized = useNodesInitialized();
  const width = useStore((s) => s.width);
  const height = useStore((s) => s.height);
  const didInitialFitRef = useRef(false);

  const onZoomToFit = useCallback(async () => {
    const nodes = getNodes().filter((n) => !n.hidden);
    if (!nodes.length || width === 0 || height === 0) return;

    // Reserve space: zoom panel bottom-left + optional execute bottom-center (~one row tall).
    const footerHeightPx = addFooterPadding ? 120 : 90;
    const bounds = getNodesBounds(nodes);
    const next = getViewportForBounds(bounds, width, Math.max(1, height - footerHeightPx), 0.15, 1, 0.2);
    await setViewport(next, { duration: 200 });
  }, [addFooterPadding, getNodes, height, setViewport, width]);

  useEffect(() => {
    if (!nodesInitialized) return;
    if (didInitialFitRef.current) return;
    didInitialFitRef.current = true;
    void onZoomToFit();
  }, [nodesInitialized, onZoomToFit]);

  return (
    <>
      <Panel position="bottom-left" className="!mb-3 !ml-3">
        <div className="flex items-center gap-1 rounded-lg bg-white/95 p-1 shadow-md backdrop-blur-sm">
          <button
            type="button"
            onClick={() => void onZoomToFit()}
            title="Zoom to fit"
            aria-label="Zoom to fit"
            className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
          >
            <ArrowsPointingOutIcon className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={() => void zoomIn({ duration: 120 })}
            title="Zoom in"
            aria-label="Zoom in"
            className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
          >
            <MagnifyingGlassPlusIcon className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={() => void zoomOut({ duration: 120 })}
            title="Zoom out"
            aria-label="Zoom out"
            className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
          >
            <MagnifyingGlassMinusIcon className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={() => void zoomTo(1, { duration: 120 })}
            title="Reset zoom"
            aria-label="Reset zoom"
            className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
          >
            <ArrowUturnLeftIcon className="h-5 w-5" />
          </button>
        </div>
      </Panel>
      {runButton ? (
        <Panel position="bottom-center" className="!mb-3">
          {runButton}
        </Panel>
      ) : null}
    </>
  );
}

function escapeRegexLiteral(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function makeUniqueNodeName(base: string, existingNames: string[]): string {
  const trimmed = base.trim();
  const safeBase = trimmed.length ? trimmed : 'Node';
  const set = new Set(existingNames.map((n) => n.trim()).filter(Boolean));
  if (!set.has(safeBase)) return safeBase;

  const re = new RegExp(`^${escapeRegexLiteral(safeBase)}(?:\\s+(\\d+))?$`);
  let maxSuffix = 0;
  for (const n of set) {
    const m = re.exec(n);
    if (!m) continue;
    const suffix = m[1] ? Number(m[1]) : 0;
    if (Number.isFinite(suffix) && suffix > maxSuffix) maxSuffix = suffix;
  }
  return `${safeBase} ${maxSuffix + 1}`;
}

function uuid(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : String(Date.now());
}

function initialParametersForNodeType(typeKey: string): Record<string, unknown> {
  if (typeKey === 'flows.trigger.webhook') {
    return { webhook_leaf: uuid() };
  }
  return {};
}

function parametersForPalettePlacement(placement: FlowPalettePlacement): Record<string, unknown> {
  return {
    ...initialParametersForNodeType(placement.typeKey),
    ...(placement.parameters ?? {}),
  };
}

function baseNameForPalettePlacement(
  placement: FlowPalettePlacement,
  nodeTypesByKey: Record<string, FlowNodeType>,
): string {
  if (placement.nameHint?.trim()) return placement.nameHint.trim();
  const nt = nodeTypesByKey[placement.typeKey];
  return nt?.label ? `${nt.label}` : placement.typeKey;
}

function parseHandleIndex(handle: string | null | undefined, prefix: string): number | null {
  if (!handle) return null;
  if (!handle.startsWith(prefix)) return null;
  const idx = Number(handle.slice(prefix.length));
  return Number.isFinite(idx) ? idx : null;
}

function toCanvasEdges(edges: Edge[]): Edge[] {
  return edges.map((e) => ({
    ...e,
    type: e.type && e.type !== 'default' ? e.type : FLOW_RF_LABELED_EDGE_TYPE,
    markerEnd: e.markerEnd ?? FLOW_EDGE_MARKER,
  }));
}

/** Lives inside `<ReactFlow>`; forwards `screenToFlowPosition` to a ref for drop / palette placement. */
function ScreenToFlowPointBridge({
  targetRef,
}: {
  targetRef: React.MutableRefObject<((p: { x: number; y: number }) => { x: number; y: number }) | null>;
}) {
  const { screenToFlowPosition } = useReactFlow();
  useEffect(() => {
    targetRef.current = screenToFlowPosition;
  }, [screenToFlowPosition, targetRef]);
  return null;
}

const FlowEditor: React.FC<{
  nodeTypes: FlowNodeType[];
  nodes: Node<FlowRfNodeData>[];
  edges: Edge[];
  onNodesChange: (next: Node<FlowRfNodeData>[]) => void;
  onEdgesChange: (next: Edge[]) => void;
  onExecute?: () => void;
  /** When multiple triggers exist, dropdown entries run from each trigger (`onExecute` is unused). */
  executeWorkflowTriggers?: FlowExecuteWorkflowTriggerOption[];
  /** When set, shown in the footer run button as the last chosen trigger. */
  executeWorkflowSelectedTriggerLabel?: string | null;
  /** Last trigger used for footer “quick run”; fallback to first trigger when unset. */
  executeWorkflowPreferredTriggerId?: string | null;
  onExecuteFromWorkflowTrigger?: (triggerId: string) => void;
  onStartWebhookTestListen?: (leaf: string) => void | Promise<void>;
  onStopWebhookTestListen?: (leaf: string) => void | Promise<void>;
  webhookTestListeningLeaf?: string | null;
  webhookTestListenBusy?: boolean;
  onTestScheduleTrigger?: (triggerNodeId: string) => void | Promise<void>;
  scheduleTestBusy?: boolean;
  onTestPollTrigger?: (triggerNodeId: string) => void | Promise<void>;
  pollTestBusy?: boolean;
  /** Flow id for execution-scoped binary download URLs in the node modal. */
  flowId?: string | null;
  /**
   * Saved flow revision id for pin-binary uploads (`flow_pins` keys are keyed by this rev).
   * Do not derive from executions; pin blobs are revision-scoped. Parent should pass null until known.
   */
  flowRevidForPins?: string | null;
  /** Latest execution to drive Input / Output columns in the node modal (e.g. from logs panel). */
  executionForIo?: FlowExecution | null;
  /** Revision pin data keyed by node id. */
  pinData?: FlowPinData | null;
  onPinDataChange?: (next: FlowPinData | null) => void;
  /** When set, opens the node config modal for the given node id. */
  openConfigNodeId?: string | null;
  onOpenConfigNodeIdChange?: (next: string | null) => void;
  /** Execute step (partial run): parent supplies API call with saved revision id. */
  onExecuteStep?: (args: { targetNodeId: string; seedRunData: Record<string, unknown> }) => void | Promise<void>;
  /** Org API for flow credential pickers in the node modal. */
  flowOrgApi?: DocRouterOrgApi | null;
}> = ({
  nodeTypes,
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onExecute,
  executeWorkflowTriggers = [],
  executeWorkflowSelectedTriggerLabel = null,
  executeWorkflowPreferredTriggerId = null,
  onExecuteFromWorkflowTrigger,
  onStartWebhookTestListen,
  onStopWebhookTestListen,
  webhookTestListeningLeaf = null,
  webhookTestListenBusy = false,
  onTestScheduleTrigger,
  scheduleTestBusy = false,
  onTestPollTrigger,
  pollTestBusy = false,
  flowId = null,
  flowRevidForPins = null,
  executionForIo,
  pinData,
  onPinDataChange,
  openConfigNodeId,
  onOpenConfigNodeIdChange,
  onExecuteStep,
  flowOrgApi = null,
}) => {
  const { rfCanvasNodeTypes, rfCanvasEdgeTypes } = useStableFlowRfCanvasRegistration();
  const [nodePaletteOpen, setNodePaletteOpen] = useState(false);
  const [paletteDrilledSection, setPaletteDrilledSection] = useState<FlowPaletteSectionId | null>(null);
  const [paletteDrilledNodeTypeKey, setPaletteDrilledNodeTypeKey] = useState<string | null>(null);
  const [paletteSearching, setPaletteSearching] = useState(false);
  const [configModalNodeId, setConfigModalNodeId] = useState<string | null>(null);
  const [executeStepBusy, setExecuteStepBusy] = useState(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const nodeTypesByKey = useMemo(() => Object.fromEntries(nodeTypes.map((nt) => [nt.key, nt])), [nodeTypes]);

  const paletteDrillHeading = useMemo(() => {
    if (paletteSearching) return null;
    if (paletteDrilledNodeTypeKey) {
      const nt = nodeTypesByKey[paletteDrilledNodeTypeKey];
      return nt?.label ?? paletteDrilledNodeTypeKey;
    }
    if (paletteDrilledSection === null) return null;
    const inSection = nodeTypes.filter(
      (nt) => paletteSectionForNodeType(nt) === paletteDrilledSection,
    );
    if (inSection.length === 0) return null;
    const label = paletteSectionLabel(paletteDrilledSection);
    return `${label} (${inSection.length})`;
  }, [paletteDrilledNodeTypeKey, paletteDrilledSection, paletteSearching, nodeTypes, nodeTypesByKey]);

  const paletteDrillSubtitle = useMemo(() => {
    if (paletteSearching) return null;
    if (paletteDrilledNodeTypeKey) {
      const nt = nodeTypesByKey[paletteDrilledNodeTypeKey];
      if (!nt) return null;
      return `Actions (${paletteActionsForNodeType(nt).length})`;
    }
    if (paletteDrilledSection !== null) return paletteSectionDescription(paletteDrilledSection);
    return null;
  }, [paletteDrilledNodeTypeKey, paletteDrilledSection, paletteSearching, nodeTypesByKey]);

  const onPaletteSearchActiveChange = useCallback((active: boolean) => {
    setPaletteSearching(active);
    if (active) {
      setPaletteDrilledSection(null);
      setPaletteDrilledNodeTypeKey(null);
    }
  }, []);

  const onPaletteDrilledSectionChange = useCallback((next: FlowPaletteSectionId | null) => {
    setPaletteDrilledSection(next);
    setPaletteDrilledNodeTypeKey(null);
  }, []);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const screenToFlowPointRef = useRef<((p: { x: number; y: number }) => { x: number; y: number }) | null>(null);
  const pendingEdgeInsertRef = useRef<EdgeInsertPayload | null>(null);
  const pendingOutputAppendRef = useRef<OutputAppendPayload | null>(null);
  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;
  const renameAnchorRef = useRef<Map<string, string>>(new Map());
  const renameDebounceRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const runData = executionForIo?.run_data as Record<string, unknown> | undefined;

  const flowBlobDownloadContext = useMemo((): FlowExecutionBlobContext | null => {
    const eid = executionForIo?.execution_id?.trim();
    const oid = flowOrgApi?.organizationId?.trim();
    const fid = flowId?.trim();
    if (!eid || !oid || !fid) return null;
    return { organizationId: oid, flowId: fid, executionId: eid };
  }, [executionForIo?.execution_id, flowId, flowOrgApi?.organizationId]);

  const flowRevisionPinBlobContext = useMemo((): FlowRevisionPinBlobContext | null => {
    const revid = flowRevidForPins?.trim();
    const oid = flowOrgApi?.organizationId?.trim();
    const fid = flowId?.trim();
    if (!revid || !oid || !fid) return null;
    return { organizationId: oid, flowId: fid, flowRevid: revid };
  }, [flowRevidForPins, flowId, flowOrgApi?.organizationId]);
  const canvasEdges = useMemo(
    () => edgesWithRunDataItemCounts(toCanvasEdges(edges), runData, pinData ?? undefined),
    [edges, runData, pinData],
  );

  const nodesReachFromTriggers = useMemo(
    () => triggerReachabilityFromGraph(nodes.map((n) => n.data.flowNode), edges, nodeTypesByKey).reachable,
    [edges, nodeTypesByKey, nodes],
  );

  const nodesWithPinnedFlag = useMemo(() => {
    // Keep node identity stable; only enrich the `data` payload for rendering.
    return nodes.map((n) => ({
      ...n,
      data: {
        ...n.data,
        pinned: Boolean(pinData?.[n.id]),
        reachableFromTriggers: nodesReachFromTriggers.has(n.id),
      },
    }));
  }, [nodes, nodesReachFromTriggers, pinData]);

  useEffect(() => {
    if (configModalNodeId && !nodes.some((n) => n.id === configModalNodeId)) {
      setConfigModalNodeId(null);
    }
  }, [configModalNodeId, nodes]);

  useEffect(() => {
    if (!openConfigNodeId) return;
    if (configModalNodeId === openConfigNodeId) return;
    if (!nodes.some((n) => n.id === openConfigNodeId)) return;
    setConfigModalNodeId(openConfigNodeId);
    const alreadySelected = nodes.some((n) => n.id === openConfigNodeId && n.selected);
    if (!alreadySelected) {
      onNodesChange(nodes.map((n) => ({ ...n, selected: n.id === openConfigNodeId })));
    }
  }, [configModalNodeId, nodes, onNodesChange, openConfigNodeId]);

  useEffect(() => {
    if (nodePaletteOpen) {
      const t = window.setTimeout(() => searchInputRef.current?.focus(), 100);
      return () => clearTimeout(t);
    }
  }, [nodePaletteOpen]);

  const closePalette = useCallback(() => {
    pendingEdgeInsertRef.current = null;
    pendingOutputAppendRef.current = null;
    setPaletteDrilledSection(null);
    setPaletteDrilledNodeTypeKey(null);
    setPaletteSearching(false);
    setNodePaletteOpen(false);
  }, []);

  const openPalette = useCallback(() => {
    pendingEdgeInsertRef.current = null;
    pendingOutputAppendRef.current = null;
    setNodePaletteOpen(true);
  }, []);

  useEffect(() => {
    if (!nodePaletteOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closePalette();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [nodePaletteOpen, closePalette]);

  useEffect(() => {
    return () => {
      for (const t of renameDebounceRef.current.values()) clearTimeout(t);
      renameDebounceRef.current.clear();
      renameAnchorRef.current.clear();
    };
  }, []);

  const flushRenameRewrite = useCallback(
    (nodeId: string) => {
      const anchor = renameAnchorRef.current.get(nodeId);
      renameAnchorRef.current.delete(nodeId);
      const tid = renameDebounceRef.current.get(nodeId);
      if (tid) {
        clearTimeout(tid);
        renameDebounceRef.current.delete(nodeId);
      }
      if (anchor === undefined) return;
      const latest = nodesRef.current.find((n) => n.id === nodeId);
      if (!latest) return;
      const finalDisplay = flowCanvasDisplayName(latest.data.flowNode);
      if (anchor === finalDisplay) return;
      onNodesChange(rewriteRfNodesDisplayRefsRename(nodesRef.current, anchor, finalDisplay));
    },
    [onNodesChange],
  );

  const onConnect = useCallback(
    (params: Connection) => {
      const outIdx = parseHandleIndex(params.sourceHandle, 'out-');
      const inIdx = parseHandleIndex(params.targetHandle, 'in-');
      if (outIdx == null || inIdx == null) return;

      const src = nodes.find((n) => n.id === params.source);
      const dst = nodes.find((n) => n.id === params.target);
      const srcType = src ? nodeTypesByKey[src.data.flowNode.type] : undefined;
      const dstType = dst ? nodeTypesByKey[dst.data.flowNode.type] : undefined;

      if (outIdx < 0 || (srcType && outIdx >= (srcType.outputs ?? 0))) return;
      const maxIn = inputHandleCount(dstType);
      if (inIdx < 0 || inIdx >= maxIn) return;

      const connectionType = outputPortType(srcType, outIdx);
      if (!portTypesCompatible(connectionType, inputPortType(dstType, inIdx))) return;

      const duplicate = edges.some(
        (e) =>
          e.source === params.source &&
          e.target === params.target &&
          (e.sourceHandle ?? '') === (params.sourceHandle ?? '') &&
          (e.targetHandle ?? '') === (params.targetHandle ?? ''),
      );
      if (duplicate) return;

      onEdgesChange(
        addEdge(
          {
            ...params,
            type: FLOW_RF_LABELED_EDGE_TYPE,
            style: { stroke: '#a8b0bd', strokeWidth: 1.5 },
            markerEnd: FLOW_EDGE_MARKER,
            data: { connectionType },
          },
          edges,
        ),
      );
    },
    [edges, nodeTypesByKey, nodes, onEdgesChange],
  );

  const isValidConnection = useCallback(
    (connection: Connection) => {
      const outIdx = parseHandleIndex(connection.sourceHandle, 'out-');
      const inIdx = parseHandleIndex(connection.targetHandle, 'in-');
      if (outIdx == null || inIdx == null) return false;

      const src = nodes.find((n) => n.id === connection.source);
      const dst = nodes.find((n) => n.id === connection.target);
      const srcType = src ? nodeTypesByKey[src.data.flowNode.type] : undefined;
      const dstType = dst ? nodeTypesByKey[dst.data.flowNode.type] : undefined;

      if (outIdx < 0 || (srcType && outIdx >= (srcType.outputs ?? 0))) return false;
      if (inIdx < 0 || inIdx >= inputHandleCount(dstType)) return false;

      return portTypesCompatible(outputPortType(srcType, outIdx), inputPortType(dstType, inIdx));
    },
    [nodeTypesByKey, nodes],
  );

  const onNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodesChange(nodes.map((n) => (n.id === node.id ? { ...n, selected: true } : { ...n, selected: false })));
      setConfigModalNodeId(node.id);
    },
    [nodes, onNodesChange],
  );

  const onPatchNodeById = useCallback(
    (id: string, patch: Partial<FlowNode>) => {
      if (!id) return;
      const prevRf = nodes.find((n) => n.id === id);
      if (patch.name !== undefined && prevRf && !renameAnchorRef.current.has(id)) {
        renameAnchorRef.current.set(id, flowCanvasDisplayName(prevRf.data.flowNode));
      }

      const next = nodes.map((n) => {
        if (n.id !== id) return n;
        const flowNode = { ...n.data.flowNode, ...patch, parameters: patch.parameters ?? n.data.flowNode.parameters };
        return {
          ...n,
          data: {
            ...n.data,
            flowNode,
            nodeType: n.data.nodeType ?? nodeTypesByKey[flowNode.type],
          },
        };
      });
      onNodesChange(next);

      if (patch.name !== undefined && prevRf) {
        const prevTimer = renameDebounceRef.current.get(id);
        if (prevTimer) clearTimeout(prevTimer);
        renameDebounceRef.current.set(
          id,
          setTimeout(() => {
            renameDebounceRef.current.delete(id);
            flushRenameRewrite(id);
          }, 350),
        );
      }
    },
    [flushRenameRewrite, nodeTypesByKey, nodes, onNodesChange],
  );

  const handleRfNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const removedIds = changes
        .filter((c): c is NodeChange & { type: 'remove'; id: string } => c.type === 'remove')
        .map((c) => c.id);
      for (const rid of removedIds) {
        const tid = renameDebounceRef.current.get(rid);
        if (tid) clearTimeout(tid);
        renameDebounceRef.current.delete(rid);
        renameAnchorRef.current.delete(rid);
      }
      const applied = applyNodeChanges(changes, nodes);
      if (removedIds.length === 0) {
        onNodesChange(applied);
        return;
      }
      let next = applied;
      for (const rid of removedIds) {
        const victim = nodes.find((n) => n.id === rid);
        const d = victim ? flowCanvasDisplayName(victim.data.flowNode) : '';
        if (d.length > 0) {
          next = rewriteRfNodesDisplayRefsRemove(next, d);
        }
      }
      onNodesChange(next);
    },
    [nodes, onNodesChange],
  );

  const insertNodeOnSplitEdge = useCallback(
    (pending: EdgeInsertPayload, placement: FlowPalettePlacement): boolean => {
      const { typeKey } = placement;
      const nt = nodeTypesByKey[typeKey];
      if (!nt) return false;
      if (inputHandleCount(nt) < 1 || (nt.outputs ?? 0) < 1) return false;

      if (!edges.some((e) => e.id === pending.edgeId)) return false;

      const originalEdge = edges.find((e) => e.id === pending.edgeId);
      const connectionType: FlowConnectionType = originalEdge
        ? edgeConnectionType(originalEdge)
        : 'main';

      const srcNode = nodes.find((n) => n.id === pending.source);
      const dstNode = nodes.find((n) => n.id === pending.target);
      if (!srcNode?.data.flowNode || !dstNode?.data.flowNode) return false;

      const sh = pending.sourceHandle ?? 'out-0';
      const th = pending.targetHandle ?? 'in-0';
      const outIdx = parseHandleIndex(sh, 'out-');
      const inIdx = parseHandleIndex(th, 'in-');
      if (outIdx == null || inIdx == null) return false;

      const srcType = srcNode.data.nodeType ?? nodeTypesByKey[srcNode.data.flowNode.type];
      const dstType = dstNode.data.nodeType ?? nodeTypesByKey[dstNode.data.flowNode.type];
      if (outIdx < 0 || (srcType && outIdx >= (srcType.outputs ?? 0))) return false;
      if (inIdx < 0 || inIdx >= inputHandleCount(dstType)) return false;
      if (
        !portTypesCompatible(connectionType, inputPortType(nt, 0)) ||
        !portTypesCompatible(outputPortType(nt, 0), connectionType)
      ) {
        return false;
      }

      const newId = uuid();
      const pos = snapToFlowGrid({ x: pending.flowPosition.x, y: pending.flowPosition.y });
      const baseName = baseNameForPalettePlacement(placement, nodeTypesByKey);
      const uniqueName = makeUniqueNodeName(
        baseName,
        nodes.map((n) => n.data.flowNode.name),
      );
      const flowNode: FlowNode = {
        id: newId,
        name: uniqueName,
        type: typeKey,
        position: [pos.x, pos.y],
        parameters: parametersForPalettePlacement(placement),
        disabled: false,
        on_error: 'stop',
        notes: null,
      };
      const newNode: Node<FlowRfNodeData> = {
        id: newId,
        type: 'flow-node',
        position: pos,
        selected: true,
        data: { flowNode, nodeType: nt },
      };

      const rest = edges.filter((e) => e.id !== pending.edgeId);
      const edgeBase = {
        type: FLOW_RF_LABELED_EDGE_TYPE,
        style: { stroke: '#a8b0bd', strokeWidth: 1.5 } as const,
        markerEnd: FLOW_EDGE_MARKER,
      };
      const e1: Edge = {
        id: uuid(),
        source: pending.source,
        target: newId,
        sourceHandle: sh,
        targetHandle: 'in-0',
        data: { connectionType },
        ...edgeBase,
      };
      const e2: Edge = {
        id: uuid(),
        source: newId,
        target: pending.target,
        sourceHandle: 'out-0',
        targetHandle: th,
        data: { connectionType },
        ...edgeBase,
      };

      onNodesChange([...nodes.map((n) => ({ ...n, selected: false })), newNode]);
      onEdgesChange([...rest, e1, e2]);
      setConfigModalNodeId(newId);
      return true;
    },
    [edges, nodeTypesByKey, nodes, onEdgesChange, onNodesChange],
  );

  const appendNodeAfterOutput = useCallback(
    (pending: OutputAppendPayload, placement: FlowPalettePlacement): boolean => {
      const { typeKey } = placement;
      const nt = nodeTypesByKey[typeKey];
      if (!nt) return false;
      if (inputHandleCount(nt) < 1 || (nt.outputs ?? 0) < 1) return false;

      const srcNode = nodes.find((n) => n.id === pending.source);
      if (!srcNode?.data.flowNode) return false;

      const sh = pending.sourceHandle ?? 'out-0';
      const outIdx = parseHandleIndex(sh, 'out-');
      if (outIdx == null || outIdx < 0) return false;
      const srcType = srcNode.data.nodeType ?? nodeTypesByKey[srcNode.data.flowNode.type];
      if (srcType && outIdx >= (srcType.outputs ?? 0)) return false;

      const dx = FLOW_CANVAS_GRID_PX * 8;
      const pos = snapToFlowGrid({ x: srcNode.position.x + dx, y: srcNode.position.y });
      const newId = uuid();
      const baseName = baseNameForPalettePlacement(placement, nodeTypesByKey);
      const uniqueName = makeUniqueNodeName(
        baseName,
        nodes.map((n) => n.data.flowNode.name),
      );
      const flowNode: FlowNode = {
        id: newId,
        name: uniqueName,
        type: typeKey,
        position: [pos.x, pos.y],
        parameters: parametersForPalettePlacement(placement),
        disabled: false,
        on_error: 'stop',
        notes: null,
      };
      const newNode: Node<FlowRfNodeData> = {
        id: newId,
        type: 'flow-node',
        position: pos,
        selected: true,
        data: { flowNode, nodeType: nt },
      };

      const edgeBase = {
        type: FLOW_RF_LABELED_EDGE_TYPE,
        style: { stroke: '#a8b0bd', strokeWidth: 1.5 } as const,
        markerEnd: FLOW_EDGE_MARKER,
      };
      const e1: Edge = {
        id: uuid(),
        source: pending.source,
        target: newId,
        sourceHandle: sh,
        targetHandle: 'in-0',
        ...edgeBase,
      };

      onNodesChange([...nodes.map((n) => ({ ...n, selected: false })), newNode]);
      onEdgesChange([...edges, e1]);
      setConfigModalNodeId(newId);
      return true;
    },
    [edges, nodeTypesByKey, nodes, onEdgesChange, onNodesChange],
  );

  const addNodeFromPalettePlacement = useCallback(
    (placement: FlowPalettePlacement) => {
      const pendingEdge = pendingEdgeInsertRef.current;
      if (pendingEdge) {
        pendingEdgeInsertRef.current = null;
        const ok = insertNodeOnSplitEdge(pendingEdge, placement);
        if (ok) {
          closePalette();
          return;
        }
        pendingEdgeInsertRef.current = pendingEdge;
        return;
      }

      const pendingAppend = pendingOutputAppendRef.current;
      if (pendingAppend) {
        pendingOutputAppendRef.current = null;
        const ok = appendNodeAfterOutput(pendingAppend, placement);
        if (ok) {
          closePalette();
          return;
        }
        pendingOutputAppendRef.current = pendingAppend;
        return;
      }

      const stf = screenToFlowPointRef.current;
      const el = wrapperRef.current;
      if (!stf || !el) return;

      const { typeKey } = placement;
      const r = el.getBoundingClientRect();
      const p = snapToFlowGrid(stf({ x: r.left + r.width / 2, y: r.top + r.height / 2 }));
      const nt = nodeTypesByKey[typeKey];
      const id = uuid();
      const baseName = baseNameForPalettePlacement(placement, nodeTypesByKey);
      const uniqueName = makeUniqueNodeName(
        baseName,
        nodes.map((n) => n.data.flowNode.name),
      );
      const flowNode: FlowNode = {
        id,
        name: uniqueName,
        type: typeKey,
        position: [p.x, p.y],
        parameters: parametersForPalettePlacement(placement),
        disabled: false,
        on_error: 'stop',
        notes: null,
      };
      const newNode: Node<FlowRfNodeData> = {
        id,
        type: 'flow-node',
        position: p,
        selected: true,
        data: { flowNode, nodeType: nt },
      };
      onNodesChange([...nodes.map((n) => ({ ...n, selected: false })), newNode]);
      setConfigModalNodeId(id);
      closePalette();
    },
    [appendNodeAfterOutput, closePalette, insertNodeOnSplitEdge, nodeTypesByKey, nodes, onNodesChange],
  );

  /** Palette is over a full-screen backdrop while open; drops must be handled there, not only on the pane below. */
  const handlePaletteNodeDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const typeKey =
        event.dataTransfer.getData('application/flow-node-type') ||
        event.dataTransfer.getData('text/plain');
      if (!typeKey) return;
      const placement = parseFlowNodeDragPayload(typeKey, event.dataTransfer);

      const pendingEdge = pendingEdgeInsertRef.current;
      if (pendingEdge) {
        pendingEdgeInsertRef.current = null;
        const ok = insertNodeOnSplitEdge(pendingEdge, placement);
        if (ok) {
          closePalette();
          return;
        }
        pendingEdgeInsertRef.current = pendingEdge;
        return;
      }

      const pendingAppend = pendingOutputAppendRef.current;
      if (pendingAppend) {
        pendingOutputAppendRef.current = null;
        const ok = appendNodeAfterOutput(pendingAppend, placement);
        if (ok) {
          closePalette();
          return;
        }
        pendingOutputAppendRef.current = pendingAppend;
        return;
      }

      const stf = screenToFlowPointRef.current;
      if (!stf) return;
      const p = snapToFlowGrid(stf({ x: event.clientX, y: event.clientY }));
      const nt = nodeTypesByKey[placement.typeKey];
      const id = uuid();
      const baseName = baseNameForPalettePlacement(placement, nodeTypesByKey);
      const uniqueName = makeUniqueNodeName(
        baseName,
        nodes.map((n) => n.data.flowNode.name),
      );
      const flowNode: FlowNode = {
        id,
        name: uniqueName,
        type: placement.typeKey,
        position: [p.x, p.y],
        parameters: parametersForPalettePlacement(placement),
        disabled: false,
        on_error: 'stop',
        notes: null,
      };
      const newNode: Node<FlowRfNodeData> = {
        id,
        type: 'flow-node',
        position: p,
        selected: true,
        data: { flowNode, nodeType: nt },
      };
      onNodesChange([...nodes.map((n) => ({ ...n, selected: false })), newNode]);
      setConfigModalNodeId(id);
      closePalette();
    },
    [appendNodeAfterOutput, closePalette, insertNodeOnSplitEdge, nodeTypesByKey, nodes, onNodesChange],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
  }, []);

  const configRf = useMemo(() => {
    const n = nodes.find((x) => x.id === configModalNodeId);
    if (!n) return { node: null as FlowNode | null, nodeType: null as FlowNodeType | null };
    return { node: n.data.flowNode, nodeType: nodeTypesByKey[n.data.flowNode.type] ?? n.data.nodeType ?? null };
  }, [configModalNodeId, nodeTypesByKey, nodes]);

  const runExecuteStepForNode = useCallback(
    async (targetNodeId: string) => {
      if (!onExecuteStep) return;
      setExecuteStepBusy(true);
      try {
        await onExecuteStep({
          targetNodeId,
          seedRunData: { ...(runData ?? {}) },
        });
      } finally {
        setExecuteStepBusy(false);
      }
    },
    [onExecuteStep, runData],
  );

  const onExecuteStepClick = useCallback(async () => {
    if (!configModalNodeId) return;
    await runExecuteStepForNode(configModalNodeId);
  }, [configModalNodeId, runExecuteStepForNode]);

  const hoverExecuteWorkflowFromTrigger = useMemo(() => {
    const multi = executeWorkflowTriggers.length > 1;
    if (multi) {
      if (!onExecuteFromWorkflowTrigger) return undefined;
      return (triggerNodeId: string) => void onExecuteFromWorkflowTrigger(triggerNodeId);
    }
    if (!onExecute) return undefined;
    return (triggerNodeId: string) => {
      void triggerNodeId;
      void onExecute();
    };
  }, [executeWorkflowTriggers.length, onExecute, onExecuteFromWorkflowTrigger]);

  const canvasActions = useMemo(
    () => ({
      onExecuteNodeStep: onExecuteStep ? runExecuteStepForNode : undefined,
      executeStepBusy,
      onToggleNodeDisabled: (nodeId: string) => {
        onNodesChange(
          nodes.map((n) => {
            if (n.id !== nodeId) return n;
            const fn = n.data.flowNode;
            return {
              ...n,
              data: {
                ...n.data,
                flowNode: { ...fn, disabled: !fn.disabled },
                nodeType: n.data.nodeType ?? nodeTypesByKey[fn.type],
              },
            };
          }),
        );
      },
      onDeleteNode: (nodeId: string) => {
        const tid = renameDebounceRef.current.get(nodeId);
        if (tid) clearTimeout(tid);
        renameDebounceRef.current.delete(nodeId);
        renameAnchorRef.current.delete(nodeId);
        const victim = nodes.find((n) => n.id === nodeId);
        const removedDisplay = victim ? flowCanvasDisplayName(victim.data.flowNode) : '';
        const remaining = nodes.filter((n) => n.id !== nodeId);
        const nextNodes =
          removedDisplay.length > 0 ? rewriteRfNodesDisplayRefsRemove(remaining, removedDisplay) : remaining;
        onNodesChange(nextNodes);
        onEdgesChange(edges.filter((e) => e.source !== nodeId && e.target !== nodeId));
      },
      onOpenNodeSettings: (nodeId: string) => {
        onNodesChange(nodes.map((n) => ({ ...n, selected: n.id === nodeId })));
        setConfigModalNodeId(nodeId);
      },
      onDeleteEdge: (edgeId: string) => {
        onEdgesChange(edges.filter((e) => e.id !== edgeId));
      },
      onBeginInsertOnEdge: (payload: EdgeInsertPayload) => {
        pendingOutputAppendRef.current = null;
        pendingEdgeInsertRef.current = payload;
        setNodePaletteOpen(true);
      },
      onBeginAppendFromOutput: (payload: OutputAppendPayload) => {
        pendingEdgeInsertRef.current = null;
        pendingOutputAppendRef.current = payload;
        setNodePaletteOpen(true);
      },
      onHoverExecuteWorkflowFromTrigger: hoverExecuteWorkflowFromTrigger,
    }),
    [
      edges,
      executeStepBusy,
      hoverExecuteWorkflowFromTrigger,
      nodeTypesByKey,
      nodes,
      onEdgesChange,
      onExecuteStep,
      onNodesChange,
      runExecuteStepForNode,
    ],
  );

  const footerExecuteSubLabel = useMemo(() => {
    const chosen = (executeWorkflowSelectedTriggerLabel || '').trim();
    if (chosen) return `from ${chosen}`;
    const first = executeWorkflowTriggers[0];
    const fallback = ((first?.label || first?.id) ?? '').trim();
    return fallback ? `from ${fallback}` : 'from trigger';
  }, [executeWorkflowSelectedTriggerLabel, executeWorkflowTriggers]);

  const preferredFooterTriggerId = useMemo(() => {
    const cand = (executeWorkflowPreferredTriggerId || '').trim();
    if (cand && executeWorkflowTriggers.some((t) => t.id === cand)) return cand;
    return executeWorkflowTriggers[0]?.id ?? '';
  }, [executeWorkflowPreferredTriggerId, executeWorkflowTriggers]);

  return (
    <div className="docrouter-flow-canvas flex h-full min-h-[20rem] w-full min-w-0 flex-col overflow-hidden rounded-lg border border-[#e2e4e8] bg-[#f7f7f9]">
      <div
        ref={wrapperRef}
        className="relative h-full min-h-[12rem] min-w-0"
        onDrop={handlePaletteNodeDrop}
        onDragOver={onDragOver}
      >
        <FlowCanvasActionsProvider value={canvasActions}>
          <FlowExecutionVisualProvider execution={executionForIo}>
            <ReactFlow
              className="h-full w-full"
              nodes={nodesWithPinnedFlag}
              edges={canvasEdges}
              nodeTypes={rfCanvasNodeTypes}
              edgeTypes={rfCanvasEdgeTypes}
              onNodesChange={handleRfNodesChange}
              onEdgesChange={(changes: EdgeChange[]) => {
                onEdgesChange(applyEdgeChanges(changes, edges));
              }}
              onConnect={onConnect}
              isValidConnection={isValidConnection}
              onNodeDoubleClick={onNodeDoubleClick}
              snapToGrid
              snapGrid={[FLOW_CANVAS_GRID_PX, FLOW_CANVAS_GRID_PX]}
              proOptions={FLOW_EDITOR_RF_PRO_OPTIONS}
              minZoom={0.15}
              maxZoom={1.5}
              defaultEdgeOptions={FLOW_EDITOR_DEFAULT_EDGE_OPTIONS}
              connectionLineStyle={{ stroke: '#94a3b8', strokeWidth: 1.5 }}
              elevateEdgesOnSelect
            >
              <ScreenToFlowPointBridge targetRef={screenToFlowPointRef} />
              <Background color="#b8c0cc" gap={FLOW_CANVAS_GRID_PX} size={1.2} variant={BackgroundVariant.Dots} />
              <Controls className="!shadow-md" position="bottom-left" showZoom={false} showFitView={false} showInteractive={false} />
              <CanvasZoomControls
                addFooterPadding={Boolean(onExecute || executeWorkflowTriggers.length > 1)}
                runButton={
                  executeWorkflowTriggers.length > 1 && onExecuteFromWorkflowTrigger ? (
                    <div className="inline-flex shrink-0 overflow-hidden rounded-md shadow-md ring-1 ring-black/10">
                      <button
                        type="button"
                        aria-label={`${FLOW_EXECUTE_FLOW_LABEL} (${footerExecuteSubLabel})`}
                        disabled={!preferredFooterTriggerId}
                        onClick={() => {
                          if (!preferredFooterTriggerId) return;
                          void onExecuteFromWorkflowTrigger(preferredFooterTriggerId);
                        }}
                        className={`${flowRunButtonCanvasClass} gap-3 rounded-none px-5 py-2.5 text-left`}
                      >
                        <PlayIcon className="h-4 w-4 shrink-0" aria-hidden />
                        <span className="flex flex-col items-start leading-tight">
                          <span className="whitespace-nowrap">{FLOW_EXECUTE_FLOW_LABEL}</span>
                          <span className="text-[11px] font-semibold opacity-95">{footerExecuteSubLabel}</span>
                        </span>
                      </button>
                      <Menu as="div" className="relative shrink-0 self-stretch text-left">
                        <MenuButton
                          type="button"
                          aria-label="Choose which trigger starts the workflow"
                          className="inline-flex h-full min-h-full min-w-[2.75rem] items-center justify-center border-l border-white/30 bg-primary-600 px-3 text-white transition hover:bg-primary-700 active:scale-[0.99]"
                        >
                          <ChevronDownIcon className="h-4 w-4" aria-hidden />
                        </MenuButton>
                        <MenuItems
                          anchor="top end"
                          modal={false}
                          className={`${flowWorkspaceMenuPanelClass} mt-2 min-w-[12rem]`}
                        >
                          {executeWorkflowTriggers.map((t) => (
                            <MenuItem key={t.id}>
                              {({ focus }) => (
                                <button
                                  type="button"
                                  className={`${flowWorkspaceDropdownItemSimpleClass} flex w-full items-center gap-2 ${focus ? 'bg-gray-100' : ''}`}
                                  onClick={() => onExecuteFromWorkflowTrigger(t.id)}
                                >
                                  <span className="whitespace-normal text-left">{`From ${t.label.trim() ? t.label : t.id}`}</span>
                                </button>
                              )}
                            </MenuItem>
                          ))}
                        </MenuItems>
                      </Menu>
                    </div>
                  ) : onExecute ? (
                    <button
                      type="button"
                      onClick={onExecute}
                      className={flowRunButtonCanvasClass}
                    >
                      <PlayIcon className="h-4 w-4" aria-hidden />
                      {FLOW_EXECUTE_FLOW_LABEL}
                    </button>
                  ) : undefined
                }
              />
            </ReactFlow>
          </FlowExecutionVisualProvider>
        </FlowCanvasActionsProvider>

        {nodes.length === 0 && (
          <div className="pointer-events-none absolute inset-0 z-[5] flex items-center justify-center">
            <button
              type="button"
              onClick={openPalette}
              className="pointer-events-auto flex h-[100px] w-[100px] flex-col items-center justify-center rounded-xl border-2 border-dashed border-[#b8c0cc] bg-white/90 px-2 text-center text-sm font-semibold text-[#5a6270] shadow-sm transition hover:border-sky-400 hover:text-sky-800"
            >
              Add first step
            </button>
          </div>
        )}

        <div className="pointer-events-auto absolute right-2 top-1/2 z-10 flex -translate-y-1/2 flex-col gap-0.5 rounded-lg border border-[#d8dde4] bg-white/95 p-0.5 shadow-md backdrop-blur-sm">
          <button
            type="button"
            onClick={openPalette}
            title="Add node"
            aria-label="Add node"
            className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
          >
            <PlusIcon className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={openPalette}
            title="Search nodes"
            aria-label="Search nodes"
            className="rounded-md p-1.5 text-gray-700 transition hover:bg-gray-100"
          >
            <MagnifyingGlassIcon className="h-5 w-5" />
          </button>
          <button
            type="button"
            disabled
            title="Coming soon"
            aria-label="Duplicate (coming soon)"
            className="cursor-not-allowed rounded-md p-1.5 text-gray-400"
          >
            <Square2StackIcon className="h-5 w-5" />
          </button>
        </div>
      </div>

      <FlowNodeConfigModal
        open={configModalNodeId != null && configRf.node != null}
        onClose={() => {
          setConfigModalNodeId(null);
          onOpenConfigNodeIdChange?.(null);
        }}
        node={configRf.node}
        nodeType={configRf.nodeType}
        allNodes={nodes.map((n) => n.data.flowNode)}
        nodeTypes={nodeTypes}
        edges={edges}
        runData={runData}
        pinData={pinData}
        onPinDataChange={onPinDataChange}
        onSelectNode={(nodeId) => {
          onNodesChange(nodes.map((n) => ({ ...n, selected: n.id === nodeId })));
          setConfigModalNodeId(nodeId);
          onOpenConfigNodeIdChange?.(nodeId);
        }}
        onChange={(patch) => {
          if (configModalNodeId) onPatchNodeById(configModalNodeId, patch);
        }}
        onExecuteStep={onExecuteStep ? onExecuteStepClick : undefined}
        executeStepBusy={executeStepBusy}
        onStartWebhookTestListen={onStartWebhookTestListen}
        onStopWebhookTestListen={onStopWebhookTestListen}
        webhookTestListening={Boolean((webhookTestListeningLeaf ?? '').trim())}
        webhookTestListeningLeaf={webhookTestListeningLeaf}
        webhookTestListenBusy={webhookTestListenBusy}
        onTestScheduleTrigger={onTestScheduleTrigger}
        scheduleTestBusy={scheduleTestBusy}
        onTestPollTrigger={onTestPollTrigger}
        pollTestBusy={pollTestBusy}
        flowOrgApi={flowOrgApi}
        flowBlobDownloadContext={flowBlobDownloadContext}
        flowRevisionPinBlobContext={flowRevisionPinBlobContext}
        flowId={flowId}
        flowRevidForPins={flowRevidForPins}
      />

      {nodePaletteOpen && (
        <>
          <div
            className="fixed inset-0 z-[150] bg-black/20"
            onClick={closePalette}
            onDragOver={onDragOver}
            onDrop={handlePaletteNodeDrop}
            aria-hidden
          />
          <aside
            className="fixed right-0 top-0 z-[160] flex h-full w-[min(100vw,385px)] min-w-0 flex-col border-l border-[#dfe3e9] bg-[#fafbfc] shadow-xl"
            role="dialog"
            aria-modal
            aria-labelledby="flow-node-palette-title"
          >
            <header className="shrink-0 border-b border-[#dfe3e9] bg-[#f3f6f9] px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 flex-1 items-start gap-2">
                  {paletteDrillHeading !== null ? (
                    <>
                      <button
                        type="button"
                        onClick={() => {
                          if (paletteDrilledNodeTypeKey) setPaletteDrilledNodeTypeKey(null);
                          else setPaletteDrilledSection(null);
                        }}
                        aria-label="Back"
                        className="-ml-1 -mt-0.5 shrink-0 rounded-md p-1.5 text-[#5d656e] transition hover:bg-white/70"
                      >
                        <ChevronLeftIcon className="h-5 w-5" />
                      </button>
                      <div className="min-w-0">
                        <h2
                          id="flow-node-palette-title"
                          className="text-base font-bold leading-snug tracking-tight text-[#22262b]"
                        >
                          {paletteDrillHeading}
                        </h2>
                        {paletteDrillSubtitle && (
                          <p className="mt-1 text-sm font-normal leading-snug text-[#5d656e]">
                            {paletteDrillSubtitle}
                          </p>
                        )}
                      </div>
                    </>
                  ) : (
                    <div className="min-w-0">
                      <h2
                        id="flow-node-palette-title"
                        className="text-base font-bold leading-snug tracking-tight text-[#22262b]"
                      >
                        Add a step
                      </h2>
                      <p className="mt-1 text-sm font-normal leading-snug text-[#5d656e]">
                        Choose a trigger or action, drag it onto the canvas, or double-click to place it.
                      </p>
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={closePalette}
                  aria-label="Close"
                  className="-mr-1 -mt-0.5 shrink-0 rounded-md p-1.5 text-[#5d656e] transition hover:bg-white/70"
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>
              </div>
            </header>
            <div className="min-h-0 flex-1">
              <FlowNodePalette
                nodeTypes={nodeTypes}
                embedInDrawer
                drilledSection={paletteDrilledSection}
                onDrilledSectionChange={onPaletteDrilledSectionChange}
                drilledNodeTypeKey={paletteDrilledNodeTypeKey}
                onDrilledNodeTypeKeyChange={setPaletteDrilledNodeTypeKey}
                onSearchActiveChange={onPaletteSearchActiveChange}
                searchInputRef={searchInputRef}
                onNodeTypeDoubleClick={addNodeFromPalettePlacement}
              />
            </div>
          </aside>
        </>
      )}
    </div>
  );
};

export default FlowEditor;
