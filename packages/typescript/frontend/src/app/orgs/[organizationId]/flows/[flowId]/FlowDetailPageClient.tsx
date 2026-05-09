'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import type {
  FlowExecution,
  FlowNode,
  FlowNodeType,
  FlowPinData,
  FlowRevision,
  FlowRfEdge,
  FlowRfNode,
  ListNodeTypesResponse,
} from '@docrouter/sdk';
import FlowToolbar from '@/components/flows/FlowToolbar';
import FlowEditor from '@/components/flows/FlowEditor';
import FlowCanvasViewTabs, { FlowWorkspaceTabStraddle, type FlowCanvasView } from '@/components/flows/FlowCanvasViewTabs';
import { FLOW_WORKSPACE_HEADER_HEIGHT_CLASS, FLOW_WORKSPACE_TITLE_READ_CLASS } from '@/components/flows/flowUiClasses';
import FlowLogsPanel from '@/components/flows/FlowLogsPanel';
import { snapRfNodesPositions } from '@/components/flows/canvasGrid';
import { revisionContentFingerprint, revisionToRF, rfToRevision, type FlowRfNodeData } from '@/components/flows/flowRf';
import {
  GRAPH_BLOCKED_MESSAGE,
  MISSING_TRIGGER_MESSAGE,
  triggerReachabilityFromGraph,
} from '@/components/flows/flowTriggerReachability';
import {
  loadFlowNamesTakenLower,
  NEW_FLOW_URL_SEGMENT,
  nextSequentialDisplayName,
} from '@/components/flows/flowDefaultNames';
import { useFlowApi } from '@/components/flows/useFlowApi';
import { getApiErrorMsg } from '@/utils/api';
import type { Edge, Node } from 'reactflow';
import FlowExecutionsView from '@/components/flows/FlowExecutionsView';
import { Panel, PanelGroup, PanelResizeHandle, type ImperativePanelGroupHandle } from 'react-resizable-panels';

const LOGS_COLLAPSED_PCT = 8;
const LOGS_MIN_EXPANDED_PCT = LOGS_COLLAPSED_PCT;
const LOGS_MAX_EXPANDED_PCT = 90;
const LOGS_STORAGE_KEY = 'docrouter.flow.logsPanel.expandedPct';

/** New canvas: no nodes until the user adds a trigger from the palette. */
function emptyEditorRevision(flowIdMeta: string): FlowRevision {
  return {
    flow_revid: '',
    flow_id: flowIdMeta,
    flow_version: 0,
    graph_hash: '',
    nodes: [],
    connections: {},
    settings: {},
    pin_data: null,
    engine_version: 1,
  };
}

function tabFromQuery(value: string | null): FlowCanvasView {
  return value === 'executions' ? 'executions' : 'editor';
}

function flowExecutionIsInFlight(status: FlowExecution['status']): boolean {
  return status === 'queued' || status === 'running';
}

async function sleepMs(ms: number): Promise<void> {
  await new Promise<void>((resolve) => setTimeout(resolve, ms));
}

/** Newest list row for this test leaf, started at/after the current listen session (epoch ms). */
function pickLatestWebhookTestExecutionId(
  items: FlowExecution[],
  flowId: string,
  leaf: string,
  minStartedMs: number,
): string | null {
  const wantLeaf = leaf.trim();
  if (!wantLeaf) return null;
  for (const item of items) {
    if (item.flow_id !== flowId) continue;
    if (item.mode !== 'webhook_test') continue;
    const trig = item.trigger;
    if (!trig || typeof trig !== 'object') continue;
    const wl = (trig as { webhook_leaf?: unknown }).webhook_leaf;
    if (typeof wl !== 'string' || wl.trim() !== wantLeaf) continue;
    const startedRaw = item.started_at;
    const started =
      typeof startedRaw === 'string'
        ? Date.parse(startedRaw)
        : typeof startedRaw === 'number'
          ? startedRaw
          : NaN;
    if (!Number.isFinite(started) || started < minStartedMs) continue;
    const eid = item.execution_id?.trim();
    if (eid) return eid;
  }
  return null;
}

function downloadBlobJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function FlowDetailPageClient({
  organizationId,
  flowId,
}: {
  organizationId: string;
  flowId: string;
}) {
  const api = useFlowApi(organizationId);
  const router = useRouter();
  const searchParams = useSearchParams();
  const view = tabFromQuery(searchParams.get('tab'));
  const proposedNameQuery = searchParams.get('proposedName');
  const isDraftRoute = flowId === NEW_FLOW_URL_SEGMENT;
  const editorFlowId = isDraftRoute ? '' : flowId;
  const [flowName, setFlowName] = useState<string>('Flow');
  const [flowActive, setFlowActive] = useState<boolean>(false);
  const [activeFlowRevid, setActiveFlowRevid] = useState<string | null>(null);
  const [latestFlowRevid, setLatestFlowRevid] = useState<string>('');

  const [nodeTypes, setNodeTypes] = useState<FlowNodeType[]>([]);

  const [revision, setRevision] = useState<FlowRevision | null>(null);
  const [rfNodes, setRfNodes] = useState<Node[]>([]);
  const [rfEdges, setRfEdges] = useState<Edge[]>([]);
  const [executionForIo, setExecutionForIo] = useState<FlowExecution | null>(null);
  const [savedContentFingerprint, setSavedContentFingerprint] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [activationPending, setActivationPending] = useState(false);
  const [message, setMessage] = useState<string>('');
  const [logsFocusExecutionId, setLogsFocusExecutionId] = useState<string | null>(null);
  const [editorOpenConfigNodeId, setEditorOpenConfigNodeId] = useState<string | null>(null);
  /** When set, `/webhook-test/{leaf}` is wired to this editor session (until Stop or TTL on server). */
  const [webhookTestListeningLeaf, setWebhookTestListeningLeaf] = useState<string | null>(null);
  const [webhookTestListenBusy, setWebhookTestListenBusy] = useState(false);
  /** Ignore webhook_test rows started before this listen (ms since epoch). */
  const webhookTestListenEpochMsRef = useRef(0);
  /** Last execution id we surfaced from webhook-test polling (for logs focus). */
  const webhookTestPollChosenIdRef = useRef<string | null>(null);
  const logsPanelGroupRef = useRef<ImperativePanelGroupHandle | null>(null);
  /** Latest graph + revision for async pin persist (queues so rapid toggles don’t 409). */
  const persistCtxRef = useRef({
    revision,
    rfNodes,
    rfEdges,
    flowName,
    latestFlowRevid,
    nodeTypesByKey: {} as Record<string, FlowNodeType | undefined>,
  });
  const nodeTypesByKey = useMemo(() => Object.fromEntries(nodeTypes.map((nt) => [nt.key, nt])), [nodeTypes]);

  persistCtxRef.current = { revision, rfNodes, rfEdges, flowName, latestFlowRevid, nodeTypesByKey };
  const pinPersistChain = useRef(Promise.resolve());
  const [logsExpanded, setLogsExpanded] = useState(false);
  const [logsExpandedPct, setLogsExpandedPct] = useState<number>(() => {
    if (typeof window === 'undefined') return 50;
    const raw = window.localStorage.getItem(LOGS_STORAGE_KEY);
    const n = raw ? Number(raw) : NaN;
    if (!Number.isFinite(n)) return 50;
    return Math.min(LOGS_MAX_EXPANDED_PCT, Math.max(LOGS_MIN_EXPANDED_PCT, n));
  });

  useEffect(() => {
    setWebhookTestListeningLeaf(null);
    setWebhookTestListenBusy(false);
  }, [flowId, organizationId]);

  useEffect(() => {
    if (!isDraftRoute || view !== 'executions') return;
    router.replace(`/orgs/${organizationId}/flows/${NEW_FLOW_URL_SEGMENT}`);
  }, [isDraftRoute, organizationId, router, view]);

  const handleViewChange = useCallback(
    (next: FlowCanvasView) => {
      if (next === 'executions' && isDraftRoute) {
        setMessage('Save the flow once to open executions.');
        return;
      }
      router.push(`/orgs/${organizationId}/flows/${flowId}?tab=${next}`);
    },
    [flowId, isDraftRoute, organizationId, router],
  );

  const onLogsEditNode = useCallback(
    (nodeId: string) => {
      setEditorOpenConfigNodeId(nodeId);
      handleViewChange('editor');
    },
    [handleViewChange],
  );

  const applyLogsLayout = useCallback(
    (nextExpanded: boolean, nextExpandedPct?: number) => {
      const api = logsPanelGroupRef.current;
      if (!api) return;
      if (!nextExpanded) {
        api.setLayout([100 - LOGS_COLLAPSED_PCT, LOGS_COLLAPSED_PCT]);
        return;
      }
      const pct = Math.min(
        LOGS_MAX_EXPANDED_PCT,
        Math.max(LOGS_MIN_EXPANDED_PCT, nextExpandedPct ?? logsExpandedPct),
      );
      api.setLayout([100 - pct, pct]);
    },
    [logsExpandedPct],
  );

  const toggleLogsExpanded = useCallback(() => {
    setLogsExpanded((cur) => {
      const next = !cur;
      // Apply layout immediately after state update.
      queueMicrotask(() => applyLogsLayout(next));
      return next;
    });
  }, [applyLogsLayout]);

  useEffect(() => {
    if (logsFocusExecutionId) {
      setLogsExpanded(true);
      // Ensure the panel opens even if it was collapsed.
      queueMicrotask(() => applyLogsLayout(true));
    }
  }, [applyLogsLayout, logsFocusExecutionId]);

  const graphFingerprint = useMemo(() => {
    if (!revision) return null;
    return revisionContentFingerprint(flowName, rfNodes as FlowRfNode[], rfEdges as FlowRfEdge[], revision);
  }, [flowName, rfNodes, rfEdges, revision]);

  const graphStructurallyValid = useMemo(() => {
    if (rfNodes.length === 0) return true;
    const flowNodes = (rfNodes as Node<FlowRfNodeData>[]).map((x) => x.data.flowNode);
    return triggerReachabilityFromGraph(flowNodes, rfEdges, nodeTypesByKey).allReachable;
  }, [nodeTypesByKey, rfEdges, rfNodes]);

  const executeWorkflowTriggers = useMemo(() => {
    const flowNodes = (rfNodes as Node<FlowRfNodeData>[]).map((x) => x.data.flowNode);
    const triggers = flowNodes.filter((fn) => nodeTypesByKey[fn.type]?.is_trigger);
    triggers.sort((a, b) => {
      const an = (a.name || '').toLowerCase();
      const bn = (b.name || '').toLowerCase();
      if (an !== bn) return an.localeCompare(bn);
      return (a.id || '').localeCompare(b.id || '', 'en');
    });
    return triggers.map((fn) => ({ id: fn.id, label: (fn.name || '').trim() || fn.type }));
  }, [rfNodes, nodeTypesByKey]);

  const [lastRunTriggerId, setLastRunTriggerId] = useState<string | null>(null);
  const lastRunTriggerLabel = useMemo(() => {
    const id = (lastRunTriggerId || '').trim();
    if (!id) return null;
    return executeWorkflowTriggers.find((t) => t.id === id)?.label ?? null;
  }, [executeWorkflowTriggers, lastRunTriggerId]);

  const graphSaveBlockedReason = useMemo(() => {
    if (nodeTypes.length > 0 && executeWorkflowTriggers.length === 0) {
      return MISSING_TRIGGER_MESSAGE;
    }
    return graphStructurallyValid ? null : GRAPH_BLOCKED_MESSAGE;
  }, [
    executeWorkflowTriggers.length,
    graphStructurallyValid,
    nodeTypes.length,
  ]);

  const isDirty = useMemo(() => {
    if (graphFingerprint == null || savedContentFingerprint == null) return false;
    // Draft (/flows/new): no server revision yet — compare fingerprints only so a pristine canvas is not dirty.
    if (isDraftRoute) {
      return graphFingerprint !== savedContentFingerprint;
    }
    if (!latestFlowRevid) return true;
    return graphFingerprint !== savedContentFingerprint;
  }, [graphFingerprint, isDraftRoute, latestFlowRevid, savedContentFingerprint]);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        setMessage('');
        if (isDraftRoute) {
          const fromQuery = (proposedNameQuery ?? '').trim();
          let nts: ListNodeTypesResponse;
          let initialName: string;
          // Quick-create always passes proposedName — skip paging `GET /flows` here (heavy; avoids masking
          // canvas load failures as "Network Error" when listing is slow or fails).
          if (fromQuery) {
            nts = await api.listFlowNodeTypes();
            if (!mounted) return;
            initialName = fromQuery;
          } else {
            const [ntsRes, takenLower] = await Promise.all([
              api.listFlowNodeTypes(),
              loadFlowNamesTakenLower(api).catch(() => new Set<string>()),
            ]);
            if (!mounted) return;
            nts = ntsRes;
            initialName = nextSequentialDisplayName(takenLower, 'My workflow');
          }
          setFlowName(initialName);
          setFlowActive(false);
          setActiveFlowRevid(null);
          setLatestFlowRevid('');
          setNodeTypes(nts.items);

          const blank = emptyEditorRevision('');
          setRevision(blank);
          const { nodes, edges } = revisionToRF(blank, Object.fromEntries(nts.items.map((x) => [x.key, x])));
          const snapped = snapRfNodesPositions(nodes as Node<FlowRfNodeData>[]);
          setRfNodes(snapped as Node[]);
          setRfEdges(edges as Edge[]);
          setSavedContentFingerprint(revisionContentFingerprint(initialName, snapped, edges, blank));
          return;
        }

        const [flowItem, nts] = await Promise.all([api.getFlow(flowId), api.listFlowNodeTypes()]);
        if (!mounted) return;
        setFlowName(flowItem.flow.name);
        setFlowActive(Boolean(flowItem.flow.active));
        setActiveFlowRevid(flowItem.flow.active_flow_revid ?? null);
        setLatestFlowRevid(flowItem.latest_revision?.flow_revid ?? '');
        setNodeTypes(nts.items);

        const latest = flowItem.latest_revision?.flow_revid ?? '';
        if (latest) {
          const rev = await api.getRevision(flowId, latest);
          if (!mounted) return;
          setRevision(rev);
          const { nodes, edges } = revisionToRF(rev, Object.fromEntries(nts.items.map((x) => [x.key, x])));
          const snapped = snapRfNodesPositions(nodes as Node<FlowRfNodeData>[]);
          setRfNodes(snapped as Node[]);
          setRfEdges(edges as Edge[]);
          setSavedContentFingerprint(
            revisionContentFingerprint(
              flowItem.flow.name,
              snapped,
              edges,
              rev,
            ),
          );
          return;
        }

        const blank = emptyEditorRevision(flowId);
        setRevision(blank);
        const { nodes, edges } = revisionToRF(blank, Object.fromEntries(nts.items.map((x) => [x.key, x])));
        const snapped = snapRfNodesPositions(nodes as Node<FlowRfNodeData>[]);
        setRfNodes(snapped as Node[]);
        setRfEdges(edges as Edge[]);
        setSavedContentFingerprint(
          revisionContentFingerprint(flowItem.flow.name, snapped, edges, blank),
        );
      } catch (err: unknown) {
        setMessage(getApiErrorMsg(err) || 'Failed to load flow');
      }
    };
    void load();
    return () => {
      mounted = false;
    };
  }, [api, flowId, isDraftRoute, proposedNameQuery]);

  const onNodesChange = useCallback((next: Node[]) => {
    setRfNodes(next);
  }, []);

  const onEdgesChange = useCallback((next: Edge[]) => {
    setRfEdges(next);
  }, []);

  const onSave = useCallback(async () => {
    if (!revision) return;
    if (nodeTypes.length > 0 && executeWorkflowTriggers.length === 0) {
      setMessage(MISSING_TRIGGER_MESSAGE);
      return;
    }
    if (rfNodes.length > 0 && !graphStructurallyValid) {
      setMessage(GRAPH_BLOCKED_MESSAGE);
      return;
    }
    try {
      setIsSaving(true);
      setMessage('');
      const body = rfToRevision(rfNodes as FlowRfNode[], rfEdges as FlowRfEdge[], revision, flowName);
      if (isDraftRoute) {
        const res = await api.createFlow({
          name: body.name,
          nodes: body.nodes,
          connections: body.connections,
          settings: body.settings,
          pin_data: body.pin_data,
        });
        if (!res.revision) {
          setMessage('Save failed: no revision was created');
          return;
        }
        router.replace(`/orgs/${organizationId}/flows/${res.flow.flow_id}`);
        return;
      }
      const res = await api.saveRevision(flowId, {
        base_flow_revid: latestFlowRevid || '',
        name: body.name,
        nodes: body.nodes,
        connections: body.connections,
        settings: body.settings,
        pin_data: body.pin_data,
      });
      setFlowName(res.flow.name);
      setFlowActive(Boolean(res.flow.active));
      setActiveFlowRevid(res.flow.active_flow_revid ?? null);
      // API returns `revision: null` for a name-only save (graph unchanged); the latest revision id
      // in the database is unchanged — do not clear `latestFlowRevid` or the next save sends an empty
      // base_flow_revid and the server returns 409.
      if (res.revision) {
        setLatestFlowRevid(res.revision.flow_revid);
        setRevision(res.revision);
        setSavedContentFingerprint(
          revisionContentFingerprint(res.flow.name, rfNodes as FlowRfNode[], rfEdges as FlowRfEdge[], res.revision),
        );
      } else {
        setSavedContentFingerprint(
          revisionContentFingerprint(res.flow.name, rfNodes as FlowRfNode[], rfEdges as FlowRfEdge[], revision),
        );
      }
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setIsSaving(false);
    }
  }, [
    api,
    executeWorkflowTriggers.length,
    flowId,
    flowName,
    graphStructurallyValid,
    isDraftRoute,
    latestFlowRevid,
    nodeTypes.length,
    organizationId,
    rfEdges,
    rfNodes,
    revision,
    router,
  ]);

  /** Persist pin/unpin immediately so server matches the editor (no separate Save), like common workflow tooling. */
  const persistPinDataToServer = useCallback(
    async (mergedRevision: FlowRevision, pinData: FlowPinData | null) => {
      if (isDraftRoute) return;
      const ctx = persistCtxRef.current;
      const typeCatalogLoaded = Object.keys(ctx.nodeTypesByKey).length > 0;
      const triggersOnGraph = (
        (ctx.rfNodes as Node<FlowRfNodeData>[]).map((x) => x.data.flowNode) as FlowNode[]
      ).filter((fn) => ctx.nodeTypesByKey[fn.type]?.is_trigger);
      if (typeCatalogLoaded && triggersOnGraph.length === 0) {
        setMessage(MISSING_TRIGGER_MESSAGE);
        throw new Error(MISSING_TRIGGER_MESSAGE);
      }
      if (
        ctx.rfNodes.length > 0 &&
        !triggerReachabilityFromGraph(
          (ctx.rfNodes as Node<FlowRfNodeData>[]).map((x) => x.data.flowNode),
          ctx.rfEdges,
          ctx.nodeTypesByKey,
        ).allReachable
      ) {
        setMessage(GRAPH_BLOCKED_MESSAGE);
        throw new Error(GRAPH_BLOCKED_MESSAGE);
      }
      setIsSaving(true);
      setMessage('');
      try {
        const body = rfToRevision(
          ctx.rfNodes as FlowRfNode[],
          ctx.rfEdges as FlowRfEdge[],
          mergedRevision,
          ctx.flowName,
        );
        const res = await api.saveRevision(flowId, {
          base_flow_revid: ctx.latestFlowRevid || '',
          name: body.name,
          nodes: body.nodes,
          connections: body.connections,
          settings: body.settings,
          pin_data: pinData,
        });
        setFlowName(res.flow.name);
        setFlowActive(Boolean(res.flow.active));
        setActiveFlowRevid(res.flow.active_flow_revid ?? null);
        if (res.revision) {
          setLatestFlowRevid(res.revision.flow_revid);
          setRevision(res.revision);
          setSavedContentFingerprint(
            revisionContentFingerprint(res.flow.name, ctx.rfNodes as FlowRfNode[], ctx.rfEdges as FlowRfEdge[], res.revision),
          );
        } else {
          setSavedContentFingerprint(
            revisionContentFingerprint(res.flow.name, ctx.rfNodes as FlowRfNode[], ctx.rfEdges as FlowRfEdge[], mergedRevision),
          );
        }
      } finally {
        setIsSaving(false);
      }
    },
    [api, flowId, isDraftRoute],
  );

  const onPinDataChange = useCallback(
    (next: FlowPinData | null) => {
      if (!revision) return;
      const prev = revision.pin_data;
      const removed =
        prev && typeof prev === 'object'
          ? Object.keys(prev).filter((id) => next == null || !Object.prototype.hasOwnProperty.call(next, id))
          : [];
      const rollbackPins = prev ?? null;
      const mergedForSave = { ...revision, pin_data: next };

      setRevision({ ...revision, pin_data: next });

      if (removed.length > 0) {
        setExecutionForIo((ex) => {
          if (!ex?.run_data || typeof ex.run_data !== 'object') return ex;
          const rd = { ...(ex.run_data as Record<string, unknown>) };
          for (const id of removed) delete rd[id];
          return { ...ex, run_data: rd };
        });
      }

      if (isDraftRoute) return;

      pinPersistChain.current = pinPersistChain.current.then(async () => {
        try {
          await persistPinDataToServer(mergedForSave, next);
        } catch (err: unknown) {
          setMessage(err instanceof Error ? err.message : 'Failed to save pins');
          setRevision((cur) => (cur ? { ...cur, pin_data: rollbackPins } : cur));
        }
      });
    },
    [isDraftRoute, persistPinDataToServer, revision],
  );

  const buildRevisionSnapshotForRun = useCallback(() => {
    if (!revision) return null;
    const body = rfToRevision(rfNodes as FlowRfNode[], rfEdges as FlowRfEdge[], revision, flowName);
    return {
      nodes: body.nodes,
      connections: body.connections,
      settings: body.settings ?? {},
      pin_data: body.pin_data ?? null,
    };
  }, [revision, rfNodes, rfEdges, flowName]);

  const onRun = useCallback(
    async (startTriggerNodeId?: string) => {
      const revision_snapshot = buildRevisionSnapshotForRun();
      if (!revision_snapshot) return;
      try {
        setMessage('');
        const rid = latestFlowRevid?.trim();
        const multi = executeWorkflowTriggers.length > 1;
        const st = typeof startTriggerNodeId === 'string' ? startTriggerNodeId.trim() : '';
        if (multi && !st) return;
        const out = await api.runFlow(flowId, {
          flow_revid: rid || undefined,
          document_id: undefined,
          ...(multi ? { start_trigger_node_id: st } : {}),
          revision_snapshot,
        });
        if (multi && st) setLastRunTriggerId(st);
        if (out.execution_id) {
          setLogsFocusExecutionId(out.execution_id);
        }
      } catch (err: unknown) {
        setMessage(err instanceof Error ? err.message : 'Failed to run');
      }
    },
    [api, buildRevisionSnapshotForRun, executeWorkflowTriggers, flowId, latestFlowRevid],
  );

  const onStartWebhookTestListen = useCallback(
    async (leaf: string) => {
      const revision_snapshot = buildRevisionSnapshotForRun();
      if (!revision_snapshot) return;
      const s = leaf.trim();
      if (!s) return;
      try {
        setMessage('');
        setWebhookTestListenBusy(true);
        await api.getHttpClient().post(`/v0/orgs/${organizationId}/flows/${flowId}/webhook-test/listen`, {
          webhook_leaf: s,
          revision_snapshot,
        });
        webhookTestListenEpochMsRef.current = Date.now() - 2000;
        webhookTestPollChosenIdRef.current = null;
        setWebhookTestListeningLeaf(s);
      } catch (err: unknown) {
        setMessage(err instanceof Error ? err.message : 'Failed to listen for test event');
      } finally {
        setWebhookTestListenBusy(false);
      }
    },
    [api, buildRevisionSnapshotForRun, flowId, organizationId],
  );

  const webhookTestStopInternal = useCallback(
    async (leaf: string) => {
      const s = leaf.trim();
      await api.getHttpClient().post(`/v0/orgs/${organizationId}/flows/${flowId}/webhook-test/stop`, {
        ...(s ? { webhook_leaf: s } : {}),
      });
    },
    [api, flowId, organizationId],
  );

  const onStopWebhookTestListen = useCallback(
    async (leaf: string) => {
      try {
        setMessage('');
        setWebhookTestListenBusy(true);
        await webhookTestStopInternal(leaf);
        setWebhookTestListeningLeaf(null);
      } catch (err: unknown) {
        setMessage(err instanceof Error ? err.message : 'Failed to stop webhook test listener');
      } finally {
        setWebhookTestListenBusy(false);
      }
    },
    [webhookTestStopInternal],
  );

  // Poll while listening; tear down the listener server-side after the first matching webhook run is seen.
  useEffect(() => {
    const leaf = webhookTestListeningLeaf?.trim();
    if (!leaf) return;

    let cancelled = false;
    const POLL_MS = 900;

    const tick = async () => {
      if (cancelled) return;
      try {
        const res = await api.getHttpClient().get<{ items: FlowExecution[]; total: number }>(
          `/v0/orgs/${organizationId}/executions`,
          { params: { flow_id: flowId, mode: 'webhook_test', limit: 30 } },
        );
        if (cancelled) return;
        const chosen = pickLatestWebhookTestExecutionId(res.items ?? [], flowId, leaf, webhookTestListenEpochMsRef.current);
        if (!chosen) return;
        const ex = await api.getExecution(flowId, chosen);
        if (cancelled) return;
        const isNewRun = chosen !== webhookTestPollChosenIdRef.current;
        if (isNewRun) {
          webhookTestPollChosenIdRef.current = chosen;
          setLogsFocusExecutionId(chosen);
        }
        setExecutionForIo(ex);
        if (isNewRun) {
          try {
            await webhookTestStopInternal(leaf);
            if (!cancelled) setWebhookTestListeningLeaf(null);
          } catch (err: unknown) {
            if (!cancelled) {
              setMessage(err instanceof Error ? err.message : 'Webhook received but failed to stop test listener');
            }
          }
        }
      } catch {
        // transient network / 404 during race
      }
    };

    void tick();
    const intervalId = window.setInterval(() => void tick(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [api, flowId, organizationId, webhookTestListeningLeaf, webhookTestStopInternal]);

  const onExecuteFlowStep = useCallback(
    async ({ targetNodeId, seedRunData }: { targetNodeId: string; seedRunData: Record<string, unknown> }) => {
      const revision_snapshot = buildRevisionSnapshotForRun();
      if (!revision_snapshot) return;
      try {
        setMessage('');
        const rid = latestFlowRevid?.trim();
        const out = await api.runFlow(flowId, {
          flow_revid: rid || undefined,
          document_id: undefined,
          target_node_id: targetNodeId,
          run_data: seedRunData,
          revision_snapshot,
        });
        const execId = out.execution_id?.trim();
        if (!execId) return;

        setLogsFocusExecutionId(execId);

        const POLL_MS = 600;
        const MAX_WAIT_MS = 180_000;
        const deadline = Date.now() + MAX_WAIT_MS;
        let lastEx: FlowExecution | null = null;

        const targetNodeShowsOutcome = (ex: FlowExecution): boolean => {
          const rd = ex.run_data as Record<string, unknown> | undefined;
          if (!rd || typeof rd !== 'object') return false;
          const raw = rd[targetNodeId];
          if (!raw || typeof raw !== 'object') return false;
          const st = (raw as { status?: string }).status;
          if (typeof st !== 'string' || !st.trim()) return false;
          return st !== 'running';
        };

        while (Date.now() < deadline) {
          try {
            lastEx = await api.getExecution(flowId, execId);
            if (!flowExecutionIsInFlight(lastEx.status)) {
              break;
            }
            if (targetNodeShowsOutcome(lastEx)) {
              break;
            }
          } catch {
            // Transient failures: keep polling until deadline.
          }
          await sleepMs(POLL_MS);
        }

        try {
          setExecutionForIo(await api.getExecution(flowId, execId));
        } catch {
          if (lastEx) setExecutionForIo(lastEx);
        }
      } catch (err: unknown) {
        setMessage(err instanceof Error ? err.message : 'Execute step failed');
      }
    },
    [api, buildRevisionSnapshotForRun, flowId, latestFlowRevid],
  );

  const onDownloadFlowJson = useCallback(async () => {
    const rid = (revision?.flow_revid ?? latestFlowRevid ?? '').trim();
    if (!rid) {
      setMessage('Save the flow once to download Flow JSON.');
      return;
    }
    try {
      setMessage('');
      const revDoc = await api.getRevision(flowId, rid);
      downloadBlobJson(`flow_${flowId}_${rid}.json`, revDoc);
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Failed to download Flow JSON');
    }
  }, [api, flowId, latestFlowRevid, revision?.flow_revid]);

  const onActivate = useCallback(async () => {
    setActivationPending(true);
    try {
      setMessage('');
      await api.activateFlow(flowId);
      const flowItem = await api.getFlow(flowId);
      setFlowActive(Boolean(flowItem.flow.active));
      setActiveFlowRevid(flowItem.flow.active_flow_revid ?? null);
      setLatestFlowRevid(flowItem.latest_revision?.flow_revid ?? '');
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Failed to activate');
    } finally {
      setActivationPending(false);
    }
  }, [api, flowId]);

  const onDeactivate = useCallback(async () => {
    const ok = window.confirm('Deactivate this flow?');
    if (!ok) return;
    setActivationPending(true);
    try {
      setMessage('');
      await api.deactivateFlow(flowId);
      const flowItem = await api.getFlow(flowId);
      setFlowActive(Boolean(flowItem.flow.active));
      setActiveFlowRevid(flowItem.flow.active_flow_revid ?? null);
      setLatestFlowRevid(flowItem.latest_revision?.flow_revid ?? '');
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Failed to deactivate');
    } finally {
      setActivationPending(false);
    }
  }, [api, flowId]);

  return (
    <div className="p-4">
      <div className="mx-auto w-full max-w-[1920px]">
        <div className="mb-4">
          <Link
            href={`/orgs/${organizationId}/flows`}
            className="text-sm text-blue-600 hover:text-blue-700"
            prefetch={false}
          >
            ← Back to flows
          </Link>
        </div>
        {message && <div className="mb-3 text-sm text-red-600">{message}</div>}

        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          {view === 'editor' && (
            /* Fixed height: React Flow needs a non-zero parent (see error #004). h-full inside scroll areas often resolves to 0. */
            <div className="flex h-[max(32rem,calc(100dvh-12.5rem))] min-h-[32rem] flex-col">
              <div className="relative z-10 shrink-0 bg-white">
                <FlowToolbar
                  name={flowName}
                  onNameChange={setFlowName}
                  active={flowActive}
                  activeFlowRevid={activeFlowRevid}
                  isDirty={isDirty}
                  isSaving={isSaving}
                  activationPending={activationPending}
                  graphSaveBlockedReason={graphSaveBlockedReason}
                  activateBlockedReason={
                    nodeTypes.length > 0 && executeWorkflowTriggers.length === 0 ? MISSING_TRIGGER_MESSAGE : null
                  }
                  onSave={onSave}
                  onActivate={onActivate}
                  onDeactivate={onDeactivate}
                  onDownloadFlowJson={() => void onDownloadFlowJson()}
                />
                <FlowWorkspaceTabStraddle>
                  <FlowCanvasViewTabs
                    value={view}
                    onChange={handleViewChange}
                    disableExecutionsTab={isDraftRoute}
                  />
                </FlowWorkspaceTabStraddle>
              </div>
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <PanelGroup
                  ref={logsPanelGroupRef}
                  direction="vertical"
                  className="min-h-0 flex-1"
                  onLayout={(sizes) => {
                    const bottom = sizes[1] ?? 0;
                    if (bottom <= LOGS_COLLAPSED_PCT + 0.5) {
                      if (logsExpanded) setLogsExpanded(false);
                      return;
                    }
                    if (!logsExpanded) setLogsExpanded(true);
                    const next = Math.min(LOGS_MAX_EXPANDED_PCT, Math.max(LOGS_MIN_EXPANDED_PCT, bottom));
                    setLogsExpandedPct(next);
                    try {
                      window.localStorage.setItem(LOGS_STORAGE_KEY, String(next));
                    } catch {
                      // ignore
                    }
                  }}
                >
                  <Panel defaultSize={100 - LOGS_COLLAPSED_PCT} minSize={25} className="min-h-0">
                    <div className="h-full min-h-0 min-w-0 overflow-hidden">
                      <FlowEditor
                        flowId={editorFlowId}
                        flowRevidForPins={(revision?.flow_revid ?? latestFlowRevid ?? '').trim() || null}
                        nodeTypes={nodeTypes}
                        nodes={rfNodes as Node<FlowRfNodeData>[]}
                        edges={rfEdges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onExecute={isDraftRoute ? undefined : () => void onRun()}
                        executeWorkflowTriggers={executeWorkflowTriggers}
                        executeWorkflowSelectedTriggerLabel={lastRunTriggerLabel}
                        executeWorkflowPreferredTriggerId={lastRunTriggerId}
                        onExecuteFromWorkflowTrigger={
                          isDraftRoute ? undefined : (id) => void onRun(id)
                        }
                        onStartWebhookTestListen={isDraftRoute ? undefined : onStartWebhookTestListen}
                        onStopWebhookTestListen={isDraftRoute ? undefined : onStopWebhookTestListen}
                        webhookTestListeningLeaf={webhookTestListeningLeaf}
                        webhookTestListenBusy={webhookTestListenBusy}
                        onExecuteStep={isDraftRoute ? undefined : onExecuteFlowStep}
                        executionForIo={executionForIo}
                        pinData={revision?.pin_data ?? null}
                        onPinDataChange={onPinDataChange}
                        openConfigNodeId={editorOpenConfigNodeId}
                        onOpenConfigNodeIdChange={setEditorOpenConfigNodeId}
                        flowOrgApi={api}
                      />
                    </div>
                  </Panel>
                  {logsExpanded ? (
                    <PanelResizeHandle className="h-2 cursor-row-resize bg-[#e8eaed] hover:bg-[#d8dde4]" />
                  ) : (
                    <PanelResizeHandle className="h-px bg-[#e8eaed]" />
                  )}
                  <Panel defaultSize={LOGS_COLLAPSED_PCT} minSize={LOGS_COLLAPSED_PCT} className="min-h-0">
                    <div className="h-full min-h-0">
                      <FlowLogsPanel
                        orgApi={api}
                        flowId={editorFlowId}
                        focusExecutionId={logsFocusExecutionId}
                        onClearFocus={() => setLogsFocusExecutionId(null)}
                        onExecutionChange={setExecutionForIo}
                        onEditNode={onLogsEditNode}
                        expanded={logsExpanded}
                        onToggleExpanded={toggleLogsExpanded}
                        graphNodes={rfNodes as Node<FlowRfNodeData>[]}
                        graphEdges={rfEdges}
                        graphPinData={revision?.pin_data ?? null}
                      />
                    </div>
                  </Panel>
                </PanelGroup>
              </div>
            </div>
          )}

          {view === 'executions' && (
            <div className="flex h-[max(32rem,calc(100dvh-12.5rem))] min-h-[32rem] flex-col bg-white">
              <div className="relative z-10 shrink-0 bg-white">
                <div
                  className={`flex ${FLOW_WORKSPACE_HEADER_HEIGHT_CLASS} shrink-0 items-center border-b border-gray-200 px-3`}
                >
                  <span className={FLOW_WORKSPACE_TITLE_READ_CLASS} title={flowName.trim() || 'Untitled flow'}>
                    {flowName.trim() || 'Untitled flow'}
                  </span>
                </div>
                <FlowWorkspaceTabStraddle>
                  <FlowCanvasViewTabs
                    value={view}
                    onChange={handleViewChange}
                    disableExecutionsTab={isDraftRoute}
                  />
                </FlowWorkspaceTabStraddle>
              </div>
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <FlowExecutionsView
                  suppressTopChrome
                  orgApi={api}
                  flowId={flowId}
                  nodeTypes={nodeTypes}
                  fallbackNodes={rfNodes as Node<FlowRfNodeData>[]}
                  fallbackEdges={rfEdges}
                  onEditFlowNode={onLogsEditNode}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
