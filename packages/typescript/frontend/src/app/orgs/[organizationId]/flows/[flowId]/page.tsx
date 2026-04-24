'use client';

import { use, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import type { FlowExecution, FlowNodeType, FlowRevision, FlowRfEdge, FlowRfNode } from '@docrouter/sdk';
import FlowToolbar from '@/components/flows/FlowToolbar';
import FlowEditor from '@/components/flows/FlowEditor';
import FlowCanvasViewTabs, { type FlowCanvasView } from '@/components/flows/FlowCanvasViewTabs';
import FlowLogsPanel from '@/components/flows/FlowLogsPanel';
import { revisionContentFingerprint, revisionToRF, rfToRevision, type FlowRfNodeData } from '@/components/flows/flowRf';
import { useFlowApi } from '@/components/flows/useFlowApi';
import type { Edge, Node } from 'reactflow';
import FlowExecutionsView from '@/components/flows/FlowExecutionsView';

function tabFromQuery(value: string | null): FlowCanvasView {
  return value === 'executions' ? 'executions' : 'editor';
}

export default function FlowDetailPage({
  params,
}: {
  params: Promise<{ organizationId: string; flowId: string }>;
}) {
  const { organizationId, flowId } = use(params);
  const api = useFlowApi(organizationId);
  const router = useRouter();
  const searchParams = useSearchParams();
  const view = tabFromQuery(searchParams.get('tab'));
  const [flowName, setFlowName] = useState<string>('Flow');
  const [flowActive, setFlowActive] = useState<boolean>(false);
  const [latestFlowRevid, setLatestFlowRevid] = useState<string>('');

  const [nodeTypes, setNodeTypes] = useState<FlowNodeType[]>([]);

  const [revision, setRevision] = useState<FlowRevision | null>(null);
  const [rfNodes, setRfNodes] = useState<Node[]>([]);
  const [rfEdges, setRfEdges] = useState<Edge[]>([]);
  const [executionForIo, setExecutionForIo] = useState<FlowExecution | null>(null);
  const [savedContentFingerprint, setSavedContentFingerprint] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string>('');
  const [logsFocusExecutionId, setLogsFocusExecutionId] = useState<string | null>(null);

  const handleViewChange = useCallback(
    (next: FlowCanvasView) => {
      router.push(`/orgs/${organizationId}/flows/${flowId}?tab=${next}`);
    },
    [flowId, organizationId, router],
  );

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
        setLatestFlowRevid(flowItem.latest_revision?.flow_revid ?? '');
        setNodeTypes(nts.items);

        const latest = flowItem.latest_revision?.flow_revid ?? '';
        if (latest) {
          const rev = await api.getRevision(flowId, latest);
          if (!mounted) return;
          setRevision(rev);
          const { nodes, edges } = revisionToRF(rev, Object.fromEntries(nts.items.map((x) => [x.key, x])));
          setRfNodes(nodes as Node[]);
          setRfEdges(edges as Edge[]);
          setSavedContentFingerprint(
            revisionContentFingerprint(
              flowItem.flow.name,
              nodes,
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
              position: [100, 100],
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
        setRfNodes(nodes as Node[]);
        setRfEdges(edges as Edge[]);
        setSavedContentFingerprint(
          revisionContentFingerprint(flowItem.flow.name, nodes, edges, blank),
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
      const newRevid = res.revision?.flow_revid ?? '';
      setLatestFlowRevid(newRevid);
      if (res.revision) {
        setRevision(res.revision);
        setSavedContentFingerprint(
          revisionContentFingerprint(res.flow.name, rfNodes as FlowRfNode[], rfEdges as FlowRfEdge[], res.revision),
        );
      } else {
        if (graphFingerprint) setSavedContentFingerprint(graphFingerprint);
      }
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setIsSaving(false);
    }
  }, [api, flowId, flowName, latestFlowRevid, rfEdges, rfNodes, revision, graphFingerprint]);

  const onRun = useCallback(async () => {
    try {
      setMessage('');
      const rev = latestFlowRevid || undefined;
      const out = await api.runFlow(flowId, { flow_revid: rev, document_id: undefined });
      if (out.execution_id) {
        setLogsFocusExecutionId(out.execution_id);
      }
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Failed to run');
    }
  }, [api, flowId, latestFlowRevid]);

  const onActivate = useCallback(async () => {
    try {
      setMessage('');
      await api.activateFlow(flowId);
      const flowItem = await api.getFlow(flowId);
      setFlowActive(Boolean(flowItem.flow.active));
      setLatestFlowRevid(flowItem.latest_revision?.flow_revid ?? '');
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Failed to activate');
    }
  }, [api, flowId]);

  const onDeactivate = useCallback(async () => {
    const ok = window.confirm('Deactivate this flow?');
    if (!ok) return;
    try {
      setMessage('');
      await api.deactivateFlow(flowId);
      const flowItem = await api.getFlow(flowId);
      setFlowActive(Boolean(flowItem.flow.active));
      setLatestFlowRevid(flowItem.latest_revision?.flow_revid ?? '');
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Failed to deactivate');
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
          <FlowCanvasViewTabs value={view} onChange={handleViewChange} />

          {view === 'editor' && (
            /* Fixed height: React Flow needs a non-zero parent (see error #004). h-full inside scroll areas often resolves to 0. */
            <div className="flex h-[max(32rem,calc(100dvh-12.5rem))] min-h-[32rem] flex-col">
              <FlowToolbar
                name={flowName}
                onNameChange={setFlowName}
                active={flowActive}
                isDirty={isDirty}
                isSaving={isSaving}
                onSave={onSave}
                onRun={onRun}
                onActivate={onActivate}
                onDeactivate={onDeactivate}
              />
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div className="min-h-0 min-w-0 flex-1 overflow-hidden p-0 sm:p-1">
                  <FlowEditor
                    nodeTypes={nodeTypes}
                    nodes={rfNodes as Node<FlowRfNodeData>[]}
                    edges={rfEdges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onExecute={onRun}
                    executionForIo={executionForIo}
                  />
                </div>
                <FlowLogsPanel
                  orgApi={api}
                  flowId={flowId}
                  focusExecutionId={logsFocusExecutionId}
                  onClearFocus={() => setLogsFocusExecutionId(null)}
                  onExecutionChange={setExecutionForIo}
                  graphNodes={rfNodes as Node<FlowRfNodeData>[]}
                  graphEdges={rfEdges}
                />
              </div>
            </div>
          )}

          {view === 'executions' && (
            <FlowExecutionsView
              orgApi={api}
              flowId={flowId}
              nodeTypes={nodeTypes}
              fallbackNodes={rfNodes as Node<FlowRfNodeData>[]}
              fallbackEdges={rfEdges}
            />
          )}
        </div>
      </div>
    </div>
  );
}
