'use client'

import { use, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import type { FlowNodeType, FlowRevision } from '@docrouter/sdk';
import FlowToolbar from '@/components/flows/FlowToolbar';
import FlowEditor from '@/components/flows/FlowEditor';
import { revisionToRF, rfToConnections } from '@/components/flows/flowRf';
import { useFlowApi } from '@/components/flows/useFlowApi';
import { applyEdgeChanges, applyNodeChanges, type Edge, type EdgeChange, type Node, type NodeChange } from 'reactflow';

export default function FlowDetailPage({
  params,
}: {
  params: Promise<{ organizationId: string; flowId: string }>;
}) {
  const { organizationId, flowId } = use(params);
  const api = useFlowApi(organizationId);
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = searchParams.get('tab') || 'editor';

  const [flowName, setFlowName] = useState<string>('Flow');
  const [flowActive, setFlowActive] = useState<boolean>(false);
  const [latestFlowRevid, setLatestFlowRevid] = useState<string>('');

  const [nodeTypes, setNodeTypes] = useState<FlowNodeType[]>([]);
  const nodeTypesByKey = useMemo(() => Object.fromEntries(nodeTypes.map((nt) => [nt.key, nt])), [nodeTypes]);

  const [revision, setRevision] = useState<FlowRevision | null>(null);
  const [rfNodes, setRfNodes] = useState<Node[]>([]);
  const [rfEdges, setRfEdges] = useState<Edge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string>('');

  const handleTabChange = (next: string) => {
    router.push(`/orgs/${organizationId}/flows/${flowId}?tab=${next}`);
  };

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        setMessage('');
        const [flowItem, nts] = await Promise.all([
          api.getFlow(flowId),
          api.listFlowNodeTypes(),
        ]);
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
          setRfNodes(nodes);
          setRfEdges(edges);
          setIsDirty(false);
          return;
        }

        // New flow (no revisions): start empty with a manual trigger node.
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
        setRfNodes(nodes);
        setRfEdges(edges);
        setIsDirty(true);
      } catch (err: any) {
        setMessage(err?.message || 'Failed to load flow');
      }
    };
    void load();
    return () => {
      mounted = false;
    };
  }, [api, flowId]);

  const onSelectedNodeIdChange = useCallback((id: string | null) => {
    setSelectedNodeId(id);
  }, []);

  const onNodesChange = useCallback((next: Node[]) => {
    setRfNodes(next);
    setIsDirty(true);
  }, []);

  const onEdgesChange = useCallback((next: Edge[]) => {
    setRfEdges(next);
    setIsDirty(true);
  }, []);

  const onReactFlowNodesChange = useCallback((changes: NodeChange[]) => {
    setRfNodes((prev) => {
      const next = applyNodeChanges(changes, prev);
      if (changes.some((c) => c.type !== 'select')) setIsDirty(true);
      return next;
    });
  }, []);

  const onReactFlowEdgesChange = useCallback((changes: EdgeChange[]) => {
    setRfEdges((prev) => {
      const next = applyEdgeChanges(changes, prev);
      if (changes.some((c) => c.type !== 'select')) setIsDirty(true);
      return next;
    });
  }, []);

  const onSave = useCallback(async () => {
    if (!revision) return;
    try {
      setIsSaving(true);
      setMessage('');
      const nodes = rfNodes.map((n: any) => ({
        ...(n.data.flowNode as any),
        id: n.id,
        position: [Math.round(n.position.x), Math.round(n.position.y)],
      }));
      const connections = rfToConnections(rfEdges as any);
      const res = await api.saveRevision(flowId, {
        base_flow_revid: latestFlowRevid || '',
        name: flowName,
        nodes,
        connections,
        settings: revision.settings || {},
        pin_data: revision.pin_data ?? null,
      });
      setFlowName(res.flow.name);
      setFlowActive(Boolean(res.flow.active));
      const newRevid = res.revision?.flow_revid ?? '';
      setLatestFlowRevid(newRevid);
      if (res.revision) {
        setRevision(res.revision);
      }
      setIsDirty(false);
    } catch (err: any) {
      setMessage(err?.message || 'Failed to save');
    } finally {
      setIsSaving(false);
    }
  }, [api, flowId, flowName, latestFlowRevid, rfEdges, rfNodes, revision]);

  const onRun = useCallback(async () => {
    try {
      setMessage('');
      await api.runFlow(flowId, {});
      handleTabChange('executions');
    } catch (err: any) {
      setMessage(err?.message || 'Failed to run');
    }
  }, [api, flowId]);

  const onActivate = useCallback(async () => {
    try {
      setMessage('');
      await api.activateFlow(flowId);
      const flowItem = await api.getFlow(flowId);
      setFlowActive(Boolean(flowItem.flow.active));
      setLatestFlowRevid(flowItem.latest_revision?.flow_revid ?? '');
    } catch (err: any) {
      setMessage(err?.message || 'Failed to activate');
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
    } catch (err: any) {
      setMessage(err?.message || 'Failed to deactivate');
    }
  }, [api, flowId]);

  return (
    <div className="p-4">
      <div className="max-w-4xl mx-auto">
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

        <div className="border-b border-gray-200 mb-3">
          <div className="flex gap-8">
            <button
              onClick={() => handleTabChange('editor')}
              className={`pb-3 px-1 relative font-semibold text-base ${
                tab === 'editor'
                  ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Editor
            </button>
            <button
              onClick={() => handleTabChange('executions')}
              className={`pb-3 px-1 relative font-semibold text-base ${
                tab === 'executions'
                  ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Executions
            </button>
          </div>
        </div>

        <div role="tabpanel" hidden={tab !== 'editor'}>
          {tab === 'editor' && (
            <div className="bg-white rounded-lg">
              <FlowToolbar
                name={flowName}
                active={flowActive}
                isDirty={isDirty}
                isSaving={isSaving}
                onSave={onSave}
                onRun={onRun}
                onActivate={onActivate}
                onDeactivate={onDeactivate}
              />
              <FlowEditor
                nodeTypes={nodeTypes}
                nodes={rfNodes as any}
                edges={rfEdges as any}
                selectedNodeId={selectedNodeId}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onSelectedNodeIdChange={onSelectedNodeIdChange}
              />
            </div>
          )}
        </div>

        <div role="tabpanel" hidden={tab !== 'executions'}>
          {tab === 'executions' && (
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="text-sm text-gray-600">Phase 3: execution history UI goes here.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

