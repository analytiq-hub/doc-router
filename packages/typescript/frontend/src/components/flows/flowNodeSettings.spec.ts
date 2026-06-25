import { describe, expect, it } from 'vitest';
import {
  FLOW_NODE_BATCH_SIZE_DEFAULT,
  FLOW_NODE_BATCH_SIZE_MAX,
  FLOW_NODE_BATCH_SIZE_MIN,
  nodeTypeSupportsBatchSize,
  resolveFlowNodeBatchSize,
} from './flowNodeSettings';

describe('resolveFlowNodeBatchSize', () => {
  it('defaults to sequential when unset', () => {
    expect(resolveFlowNodeBatchSize({})).toBe(FLOW_NODE_BATCH_SIZE_DEFAULT);
  });

  it('uses configured value within bounds', () => {
    expect(resolveFlowNodeBatchSize({ batch_size: 4 })).toBe(4);
    expect(resolveFlowNodeBatchSize({ batch_size: 999 })).toBe(FLOW_NODE_BATCH_SIZE_MAX);
    expect(resolveFlowNodeBatchSize({ batch_size: 0 })).toBe(FLOW_NODE_BATCH_SIZE_MIN);
  });

  it('accepts legacy item_concurrency', () => {
    expect(resolveFlowNodeBatchSize({ item_concurrency: 3 })).toBe(3);
  });
});

describe('nodeTypeSupportsBatchSize', () => {
  it('is true only when supports_batch_size is set on the node type', () => {
    expect(nodeTypeSupportsBatchSize({ supports_batch_size: true })).toBe(true);
    expect(nodeTypeSupportsBatchSize({ supports_batch_size: false })).toBe(false);
    expect(nodeTypeSupportsBatchSize({ batch_execute_inputs: true })).toBe(false);
    expect(nodeTypeSupportsBatchSize({})).toBe(false);
    expect(nodeTypeSupportsBatchSize(null)).toBe(false);
  });
});
