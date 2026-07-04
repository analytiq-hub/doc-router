import { describe, expect, it } from 'vitest';
import type { FlowExecution } from '@docrouter/sdk';
import {
  batchItemsRemainingFromExecution,
  executionHasResumableBatch,
  resumeExecutionLabel,
} from './flowResume';

const baseExecution = (runData: Record<string, unknown>): FlowExecution =>
  ({
    execution_id: 'e1',
    flow_id: 'f1',
    status: 'error',
    completed_nodes: ['t1'],
    run_data: runData,
  }) as FlowExecution;

describe('executionHasResumableBatch', () => {
  it('detects partial batch nodes', () => {
    expect(
      executionHasResumableBatch({
        ocr1: { status: 'partial', items_total: 10, items_completed: 4, data: { main: [[{}]] } },
      }),
    ).toBe(true);
  });
});

describe('resumeExecutionLabel', () => {
  it('shows remaining item count when partial', () => {
    const ex = baseExecution({
      llm1: { status: 'error', items_total: 13, items_completed: 10, data: { main: [Array(10).fill({})] } },
    });
    expect(resumeExecutionLabel(ex)).toBe('Resume (3 items remaining)');
    expect(batchItemsRemainingFromExecution(ex)).toBe(3);
  });
});
