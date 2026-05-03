'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import type { FlowExecution, FlowNodeType, FlowPinData, FlowRevision, FlowRfEdge, FlowRfNode } from '@docrouter/sdk';
import FlowToolbar from '@/components/flows/FlowToolbar';
import FlowEditor from '@/components/flows/FlowEditor';
import FlowCanvasViewTabs, { FlowWorkspaceTabStraddle, type FlowCanvasView } from '@/components/flows/FlowCanvasViewTabs';
import { FLOW_WORKSPACE_HEADER_HEIGHT_CLASS, FLOW_WORKSPACE_TITLE_READ_CLASS } from '@/components/flows/flowUiClasses';
import FlowLogsPanel from '@/components/flows/FlowLogsPanel';
import { snapRfNodesPositions } from '@/components/flows/canvasGrid';
import { revisionContentFingerprint, revisionToRF, rfToRevision, type FlowRfNodeData } from '@/components/flows/flowRf';
import { useFlowApi } from '@/components/flows/useFlowApi';
import type { Edge, Node } from 'reactflow';
import FlowExecutionsView from '@/components/flows/FlowExecutionsView';
import { Panel, PanelGroup, PanelResizeHandle, type ImperativePanelGroupHandle } from 'react-resizable-panels';

const LOGS_COLLAPSED_PCT = 8;
const LOGS_MIN_EXPANDED_PCT = LOGS_COLLAPSED_PCT;
const LOGS_MAX_EXPANDED_PCT = 90;
const LOGS_STORAGE_KEY = 'docrouter.flow.logsPanel.expandedPct';

function tabFromQuery(value: string | null): FlowCanvasView {
  return value === 'executions' ? 'executions' : 'editor';
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
  const logsPanelGroupRef = useRef<ImperativePanelGroupHandle | null>(null);
  /** Latest graph + revision for async pin persist (queues so rapid toggles don’t 409). */
  const persistCtxRef = useRef({
    revision,
    rfNodes,
    rfEdges,
    flowName,
    latestFlowRevid,
  });
  persistCtxRef.current = { revision, rfNodes, rfEdges, flowName, latestFlowRevid };
  const pinPersistChain = useRef(Promise.resolve());
  const [logsExpanded, setLogsExpanded] = useState(false);
  const [logsExpandedPct, setLogsExpandedPct] = useState<number>(() => {
    if (typeof window === 'undefined') return 50;
    const raw = window.localStorage.getItem(LOGS_STORAGE_KEY);
    const n = raw ? Number(raw) : NaN;
    if (!Number.isFinite(n)) return 50;
    return Math.min(LOGS_MAX_EXPANDED_PCT, Math.max(LOGS_MIN_EXPANDED_PCT, n));
  });

  const handleViewChange = useCallback(
    (next: FlowCanvasView) => {
      router.push(`/orgs/${organizationId}/flows/${flowId}?tab=${next}`);
    },
    [flowId, organizationId, router],
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

  const isDirty = useMemo(() => {
    if (graphFingerprint == null || savedContentFingerprint == null) return false;
    if (!latestFlowRevid) return true;
    return graphFingerprint !== savedContentFingerprint;
  }, [graphFingerprint, latestFlowRevid, savedContentFingerprint]);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        setMessage('');
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

        const triggerType = nts.items.find((x) => x.is_trigger)?.key ?? 'flows.trigger.manual';
        const triggerLabel = nts.items.find((x) => x.key === triggerType)?.label ?? 'Manual Trigger';
        const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : 't1';
        const blank: FlowRevision = {
          flow_revid: '',
          flow_id: flowId,
          flow_version: 0,
          graph_hash: '',
          nodes: [
            {
              id,
              name: triggerLabel,
              type: triggerType,
              position: [120, 120],
              parameters: {},
              disabled: false,
              on_error: 'stop',
              notes: null,
            },
          ],
          connections: {},
          settings: {},
          pin_data: null,
          engine_version: 1,
        };
        setRevision(blank);
        const { nodes, edges } = revisionToRF(blank, Object.fromEntries(nts.items.map((x) => [x.key, x])));
        const snapped = snapRfNodesPositions(nodes as Node<FlowRfNodeData>[]);
        setRfNodes(snapped as Node[]);
        setRfEdges(edges as Edge[]);
        setSavedContentFingerprint(
          revisionContentFingerprint(flowItem.flow.name, snapped, edges, blank),
        );
      } catch (err: unknown) {
        setMessage(err instanceof Error ? err.message : 'Failed to load flow');
      }
    };
    void load();
    return () => {
      mounted = false;
    };
  }, [api, flowId]);

  const onNodesChange = useCallback((next: Node[]) => {
    setRfNodes(next);
  }, []);

  const onEdgesChange = useCallback((next: Edge[]) => {
    setRfEdges(next);
  }, []);

  const onSave = useCallback(async () => {
    if (!revision) return;
    try {
      setIsSaving(true);
      setMessage('');
      const body = rfToRevision(rfNodes as FlowRfNode[], rfEdges as FlowRfEdge[], revision, flowName);
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
  }, [api, flowId, flowName, latestFlowRevid, rfEdges, rfNodes, revision]);

  /** Persist pin/unpin immediately so server matches the editor (no separate Save), like common workflow tooling. */
  const persistPinDataToServer = useCallback(
    async (mergedRevision: FlowRevision, pinData: FlowPinData | null) => {
      const ctx = persistCtxRef.current;
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
    [api, flowId],
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

      pinPersistChain.current = pinPersistChain.current.then(async () => {
        try {
          await persistPinDataToServer(mergedForSave, next);
        } catch (err: unknown) {
          setMessage(err instanceof Error ? err.message : 'Failed to save pins');
          setRevision((cur) => (cur ? { ...cur, pin_data: rollbackPins } : cur));
        }
      });
    },
    [persistPinDataToServer, revision],
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

  const onRun = useCallback(async () => {
    const revision_snapshot = buildRevisionSnapshotForRun();
    if (!revision_snapshot) return;
    try {
      setMessage('');
      const rid = latestFlowRevid?.trim();
      const out = await api.runFlow(flowId, {
        flow_revid: rid || undefined,
        document_id: undefined,
        revision_snapshot,
      });
      if (out.execution_id) {
        setLogsFocusExecutionId(out.execution_id);
      }
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Failed to run');
    }
  }, [api, buildRevisionSnapshotForRun, flowId, latestFlowRevid]);

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
        if (out.execution_id) {
          setLogsFocusExecutionId(out.execution_id);
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
                  onSave={onSave}
                  onActivate={onActivate}
                  onDeactivate={onDeactivate}
                  onDownloadFlowJson={() => void onDownloadFlowJson()}
                />
                <FlowWorkspaceTabStraddle>
                  <FlowCanvasViewTabs value={view} onChange={handleViewChange} />
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
                        nodeTypes={nodeTypes}
                        nodes={rfNodes as Node<FlowRfNodeData>[]}
                        edges={rfEdges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onExecute={onRun}
                        onExecuteStep={onExecuteFlowStep}
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
                        flowId={flowId}
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
                  <FlowCanvasViewTabs value={view} onChange={handleViewChange} />
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
