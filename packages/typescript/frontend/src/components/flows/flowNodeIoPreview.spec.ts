import { describe, expect, it } from 'vitest';
import type { Edge } from 'reactflow';
import type { FlowPinData } from '@docrouter/sdk';
import {
  buildNodeInputPreview,
  buildNodeOutputPreview,
  collectUpstreamClosure,
  edgeItemCountFromRunData,
  runDataMergedWithPins,
  soleInboundParentFromEdges,
  upstreamOutputItemsPreview,
} from './flowNodeIoPreview';

const e = (source: string, target: string, targetHandle?: string | null): Edge => ({
  id: `${source}-${target}`,
  source,
  target,
  ...(targetHandle != null ? { targetHandle } : {}),
});

const runEntry = (items: unknown[]) => ({
  status: 'success',
  data: { main: [items] },
});

describe('soleInboundParentFromEdges', () => {
  it('returns the only source when one edge targets the node', () => {
    expect(soleInboundParentFromEdges('b', [e('a', 'b')])).toBe('a');
  });

  it('returns null for merge (two sources)', () => {
    expect(soleInboundParentFromEdges('m', [e('a', 'm'), e('b', 'm')])).toBeNull();
  });

  it('returns null with no inbound edges', () => {
    expect(soleInboundParentFromEdges('x', [e('x', 'y')])).toBeNull();
  });
});

describe('upstreamOutputItemsPreview', () => {
  it('prefers pin over run_data', () => {
    const pin: FlowPinData = { n1: { main: [[{ json: { v: 2 }, binary: {} }]] } };
    const run = { n1: runEntry([{ json: { v: 1 }, binary: {} }]) };
    expect(upstreamOutputItemsPreview('n1', run, pin)).toEqual([{ v: 2 }]);
  });

  it('uses run_data when not pinned', () => {
    const run = { n1: runEntry([{ json: { a: 1 }, binary: {} }]) };
    expect(upstreamOutputItemsPreview('n1', run, null)).toEqual([{ a: 1 }]);
  });
});

describe('edgeItemCountFromRunData', () => {
  it('counts pinned lane when present', () => {
    const pin: FlowPinData = { s: { main: [[{ json: {}, binary: {} }, { json: {}, binary: {} }]] } };
    expect(edgeItemCountFromRunData({}, 's', pin)).toBe(2);
  });

  it('returns undefined when no run or pin for source', () => {
    expect(edgeItemCountFromRunData({}, 'missing')).toBeUndefined();
  });
});

describe('collectUpstreamClosure', () => {
  it('collects transitive predecessors', () => {
    const edges = [e('t', 'a'), e('a', 'b')];
    expect([...collectUpstreamClosure('b', edges)].sort()).toEqual(['a', 't']);
  });
});

describe('buildNodeInputPreview', () => {
  it('orders immediate parents before their ancestors', () => {
    const edges = [e('t', 'u'), e('u', 'http')];
    const run = {
      t: runEntry([{ json: { x: 1 }, binary: {} }]),
      u: runEntry([{ json: { y: 2 }, binary: {} }]),
    };
    const prev = buildNodeInputPreview('http', edges, run, null);
    expect(prev.message).toBeNull();
    expect(prev.slots.map((s) => s.fromNodeId)).toEqual(['u', 't']);
    expect(prev.slots[0]?.itemsJson).toEqual([{ y: 2 }]);
    expect(prev.slots[0]?.itemsBinaries).toEqual([{}]);
  });

  it('reports disconnected-input message when no slots', () => {
    expect(buildNodeInputPreview('solo', [], null, null).message).toContain('no input connections');
  });

  it('uses self pin when node has no inbound edges', () => {
    const pin: FlowPinData = { solo: { main: [[{ json: { z: 9 }, binary: {} }]] } };
    const prev = buildNodeInputPreview('solo', [], {}, pin);
    expect(prev.slots).toEqual([{ slot: 0, fromNodeId: 'solo', itemsJson: [{ z: 9 }], itemsBinaries: [{}] }]);
  });
});

describe('buildNodeOutputPreview', () => {
  it('returns pinned items without requiring run_data', () => {
    const pin: FlowPinData = { n: { main: [[{ json: { ok: true }, binary: {} }]] } };
    const outPrev = buildNodeOutputPreview('n', null, pin);
    expect(outPrev.itemsJson).toEqual([{ ok: true }]);
    expect(outPrev.itemsBinaries).toEqual([{}]);
  });

  it('prefers terminal run_data over pin for this node output panel', () => {
    const pin: FlowPinData = {
      ocr: { main: [[{ json: { pinned: true }, binary: { pdf: { storage_id: 'files:x.pdf', mime_type: 'application/pdf' } } }]] },
    };
    const run = {
      ocr: runEntry([
        {
          json: { ocr_pages: ['page one'], ocr_provider: 'pymupdf' },
          binary: {
            pdf: { storage_id: 'files:x.pdf', mime_type: 'application/pdf' },
            ocr_json: { storage_id: 'flow_blobs:exec/ocr/0/ocr_json', mime_type: 'application/json', file_name: 'ocr.json' },
          },
        },
      ]),
    };
    const outPrev = buildNodeOutputPreview('ocr', run, pin);
    expect(outPrev.itemsJson).toEqual([{ ocr_pages: ['page one'], ocr_provider: 'pymupdf' }]);
    expect(outPrev.itemsBinaries[0]?.ocr_json).toMatchObject({
      storage_id: 'flow_blobs:exec/ocr/0/ocr_json',
      mime_type: 'application/json',
    });
  });
});

describe('runDataMergedWithPins', () => {
  it('wraps pin outputs as execution run_data entries so preview _node matches INPUT panel', () => {
    const pinData: FlowPinData = {
      up: {
        main: [[{ json: { name: 'https://example.test', code: 1 }, binary: {} }]],
      },
    };
    const merged = runDataMergedWithPins({}, pinData);
    expect(merged.up).toEqual({
      status: 'success',
      data: pinData.up,
    });
  });

  it('prefers pin over existing run_data for the same node id', () => {
    const pinData: FlowPinData = {
      n1: { main: [[{ json: { x: 2 }, binary: {} }]] },
    };
    const merged = runDataMergedWithPins(
      { n1: { status: 'success', data: { main: [[{ json: { x: 1 }, binary: {} }]] } } },
      pinData,
    );
    expect((merged.n1 as { data: { main: unknown } }).data.main[0][0]).toEqual({ json: { x: 2 }, binary: {} });
  });

  it('leaves run_data unchanged when pin_data is absent', () => {
    const rd = { a: { status: 'queued' } };
    expect(runDataMergedWithPins(rd, null)).toEqual(rd);
    expect(runDataMergedWithPins(rd, undefined)).toEqual(rd);
  });
});
