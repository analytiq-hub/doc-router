import type { Node } from 'reactflow';
import type { FlowRfNodeData } from './flowRf';
import {
  batchItemsCompletedFromEntry,
  flowRunDataEntry,
} from './flowRunDataEntry';

/**
 * `run_data[node_id]` as produced by the flow engine (see `analytiq_data/flows/engine.py`).
 */
export type EngineNodeRunStatus = 'success' | 'error' | 'skipped' | 'stopped' | 'running' | 'partial' | string;

export type NodeRunStatusBadge = 'success' | 'error' | 'skipped' | 'stopped' | 'running' | 'partial' | null;

export type NodeBatchProgress = {
  completed: number;
  total: number;
};

export function getNodeRunStatusFromRunData(
  runData: Record<string, unknown> | null | undefined,
  nodeId: string,
): NodeRunStatusBadge {
  const s = flowRunDataEntry(runData, nodeId)?.status;
  if (s === 'success') return 'success';
  if (s === 'error') return 'error';
  if (s === 'skipped') return 'skipped';
  if (s === 'stopped') return 'stopped';
  if (s === 'running') return 'running';
  if (s === 'partial') return 'partial';
  return null;
}

export function getNodeBatchProgressFromRunData(
  runData: Record<string, unknown> | null | undefined,
  nodeId: string,
): NodeBatchProgress | null {
  const rec = flowRunDataEntry(runData, nodeId);
  if (!rec) return null;

  const total =
    typeof rec.items_total === 'number' && rec.items_total > 0
      ? rec.items_total
      : null;
  if (total == null) return null;

  const completed = batchItemsCompletedFromEntry(rec);
  if (completed == null) return null;

  const status = rec.status as EngineNodeRunStatus | undefined;
  const showWhileRunning = status === 'running' || status === 'partial';
  const incomplete = completed < total;
  if (!showWhileRunning && !incomplete) return null;
  if (status === 'success' && completed >= total) return null;

  return { completed, total };
}

export type FlowRfNodeDataWithRun = FlowRfNodeData & {
  /** Set when visualizing a past execution (Executions tab) or derived from latest run_data in the editor. */
  executionNodeStatus?: NodeRunStatusBadge;
  /** Batch OCR/LLM progress pill (`completed/total`) when a node run is partial or in progress. */
  executionBatchProgress?: NodeBatchProgress;
  /** True when the node has pinned output in the current revision. */
  pinned?: boolean;
  /** Editor: false when no directed path exists from any trigger to this node. Omitted elsewhere. */
  reachableFromTriggers?: boolean;
  /** Subtitle for Flow Tool / Execute Flow when `target_flow_id` is set. */
  targetFlowSubtitle?: string;
};

export function applyExecutionStatusToNodes(
  nodes: Node<FlowRfNodeData>[],
  runData: Record<string, unknown> | undefined,
): Node<FlowRfNodeDataWithRun>[] {
  return nodes.map((n) => {
    const st = getNodeRunStatusFromRunData(runData, n.id);
    const batchProgress = getNodeBatchProgressFromRunData(runData, n.id);
    return {
      ...n,
      data: {
        ...n.data,
        executionNodeStatus: st ?? undefined,
        executionBatchProgress: batchProgress ?? undefined,
      },
    };
  });
}
