import { describe, expect, it } from 'vitest';
import { isFetchableExecutionBlobStorageId } from './flowExecutionBlob';

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
