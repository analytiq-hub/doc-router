import type { Node } from 'reactflow';
import type { FlowRfNodeData } from './flowRf';

/**
 * `run_data[node_id]` as produced by the flow engine (see `analytiq_data/flows/engine.py`).
 */
export type EngineNodeRunStatus = 'success' | 'error' | 'skipped' | 'stopped' | string;

export type NodeRunStatusBadge = 'success' | 'error' | 'skipped' | null;

export function getNodeRunStatusFromRunData(
  runData: Record<string, unknown> | null | undefined,
  nodeId: string,
): NodeRunStatusBadge {
  if (!runData) return null;
  const rec = runData[nodeId] as { status?: EngineNodeRunStatus } | undefined;
  const s = rec?.status;
  if (s === 'success') return 'success';
  if (s === 'error') return 'error';
  if (s === 'skipped') return 'skipped';
  return null;
}

export type FlowRfNodeDataWithRun = FlowRfNodeData & {
  /** Set when visualizing a past execution (Executions tab). */
  executionNodeStatus?: NodeRunStatusBadge;
};

export function applyExecutionStatusToNodes(
  nodes: Node<FlowRfNodeData>[],
  runData: Record<string, unknown> | undefined,
): Node<FlowRfNodeDataWithRun>[] {
  return nodes.map((n) => {
    const st = getNodeRunStatusFromRunData(runData, n.id);
    return {
      ...n,
      data: {
        ...n.data,
        executionNodeStatus: st ?? undefined,
      },
    };
  });
}
