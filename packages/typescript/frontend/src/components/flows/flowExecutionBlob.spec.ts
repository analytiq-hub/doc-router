import { describe, expect, it } from 'vitest';
import {
  canFetchFlowBinaryRef,
  isFetchableExecutionBlobStorageId,
  isFetchableRevisionPinBlobStorageId,
} from './flowExecutionBlob';

describe('isFetchableExecutionBlobStorageId', () => {
  it('accepts flow_blobs, flow_pins, and files prefixes', () => {
    expect(isFetchableExecutionBlobStorageId('flow_blobs:abc')).toBe(true);
    expect(isFetchableExecutionBlobStorageId('flow_pins:abc')).toBe(true);
    expect(isFetchableExecutionBlobStorageId('files:64f3a1b2.pdf')).toBe(true);
  });

  it('rejects empty and unknown prefixes', () => {
    expect(isFetchableExecutionBlobStorageId('')).toBe(false);
    expect(isFetchableExecutionBlobStorageId(null)).toBe(false);
    expect(isFetchableExecutionBlobStorageId('s3:bucket/key')).toBe(false);
  });
});

describe('isFetchableRevisionPinBlobStorageId', () => {
  it('accepts flow_pins and files prefixes', () => {
    expect(isFetchableRevisionPinBlobStorageId('flow_pins:abc')).toBe(true);
    expect(isFetchableRevisionPinBlobStorageId('files:64f3a1b2.pdf')).toBe(true);
  });

  it('rejects flow_blobs and unknown prefixes', () => {
    expect(isFetchableRevisionPinBlobStorageId('flow_blobs:abc')).toBe(false);
    expect(isFetchableRevisionPinBlobStorageId('s3:bucket/key')).toBe(false);
  });
});

describe('canFetchFlowBinaryRef', () => {
  const executionCtx = { organizationId: 'org', flowId: 'flow', executionId: 'exec' };
  const pinCtx = { organizationId: 'org', flowId: 'flow', flowRevid: 'rev' };

  it('uses execution context for flow_blobs', () => {
    expect(canFetchFlowBinaryRef('flow_blobs:exec/x', executionCtx, pinCtx)).toBe(true);
    expect(canFetchFlowBinaryRef('flow_blobs:exec/x', null, pinCtx)).toBe(false);
  });

  it('uses pin context for flow_pins when execution is absent', () => {
    expect(canFetchFlowBinaryRef('flow_pins:pin/rev/n', null, pinCtx)).toBe(true);
  });

  it('prefers pin context for flow_pins when both contexts exist', () => {
    expect(canFetchFlowBinaryRef('flow_pins:pin/rev/n', executionCtx, pinCtx)).toBe(true);
  });

  it('uses execution context for flow_blobs even when pin context exists', () => {
    expect(canFetchFlowBinaryRef('flow_blobs:exec/x', executionCtx, pinCtx)).toBe(true);
  });

  it('does not use execution-only path for flow_pins without pin or execution context', () => {
    expect(canFetchFlowBinaryRef('flow_pins:pin/rev/n', null, null)).toBe(false);
  });

  it('uses pin context for files when execution is absent', () => {
    expect(canFetchFlowBinaryRef('files:doc.pdf', null, pinCtx)).toBe(true);
  });
});
