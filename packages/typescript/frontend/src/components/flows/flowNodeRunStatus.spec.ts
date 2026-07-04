import { describe, expect, it } from 'vitest';
import {
  applyExecutionStatusToNodes,
  getNodeBatchProgressFromRunData,
  getNodeRunStatusFromRunData,
} from './flowNodeRunStatus';
import type { FlowRfNodeData } from './flowRf';
import type { Node } from 'reactflow';

const node = (id: string): Node<FlowRfNodeData> => ({
  id,
  position: { x: 0, y: 0 },
  data: {
    flowNode: { id, type: 'docrouter.ocr', name: 'OCR', parameters: {} },
    nodeType: null,
  },
});

describe('getNodeRunStatusFromRunData', () => {
  it('maps partial status', () => {
    const runData = { n1: { status: 'partial' } };
    expect(getNodeRunStatusFromRunData(runData, 'n1')).toBe('partial');
  });
});

describe('getNodeBatchProgressFromRunData', () => {
  it('returns progress while running', () => {
    const runData = {
      n1: { status: 'running', items_total: 331, items_completed: 149, data: { main: [Array(149).fill({})] } },
    };
    expect(getNodeBatchProgressFromRunData(runData, 'n1')).toEqual({ completed: 149, total: 331 });
  });

  it('returns progress for partial interrupted node', () => {
    const runData = {
      n1: { status: 'partial', items_total: 331, items_completed: 149, data: { main: [Array(149).fill({})] } },
    };
    expect(getNodeBatchProgressFromRunData(runData, 'n1')).toEqual({ completed: 149, total: 331 });
  });

  it('returns progress on error with incomplete items', () => {
    const runData = {
      n1: { status: 'error', items_total: 10, items_completed: 7, data: { main: [Array(7).fill({})] } },
    };
    expect(getNodeBatchProgressFromRunData(runData, 'n1')).toEqual({ completed: 7, total: 10 });
  });

  it('hides pill on clean success', () => {
    const runData = {
      n1: { status: 'success', items_total: 10, items_completed: 10, data: { main: [Array(10).fill({})] } },
    };
    expect(getNodeBatchProgressFromRunData(runData, 'n1')).toBeNull();
  });
});

describe('applyExecutionStatusToNodes', () => {
  it('sets batch progress on node data', () => {
    const runData = {
      n1: { status: 'running', items_total: 5, items_completed: 2, data: { main: [[{}, {}]] } },
    };
    const out = applyExecutionStatusToNodes([node('n1')], runData);
    expect(out[0]?.data.executionNodeStatus).toBe('running');
    expect(out[0]?.data.executionBatchProgress).toEqual({ completed: 2, total: 5 });
  });
});
