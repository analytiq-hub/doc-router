import type { FlowNodeType } from '@docrouter/sdk';

/** Default batch size for nodes that process input items (1 = sequential). */
export const FLOW_NODE_BATCH_SIZE_DEFAULT = 1;

export const FLOW_NODE_BATCH_SIZE_MIN = 1;

export const FLOW_NODE_BATCH_SIZE_MAX = 256;

export function nodeTypeSupportsBatchSize(
  nodeType: FlowNodeType | null | undefined,
): boolean {
  return Boolean(nodeType?.supports_batch_size);
}

export function resolveFlowNodeBatchSize(
  node: { batch_size?: unknown; item_concurrency?: unknown } | null | undefined,
): number {
  const raw = node?.batch_size ?? node?.item_concurrency;
  if (raw == null || raw === '') return FLOW_NODE_BATCH_SIZE_DEFAULT;
  const value = typeof raw === 'number' ? raw : Number.parseInt(String(raw), 10);
  if (!Number.isFinite(value)) return FLOW_NODE_BATCH_SIZE_DEFAULT;
  return Math.min(
    FLOW_NODE_BATCH_SIZE_MAX,
    Math.max(FLOW_NODE_BATCH_SIZE_MIN, Math.trunc(value)),
  );
}
