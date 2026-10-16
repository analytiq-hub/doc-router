import { describe, expect, it } from 'vitest';
import {
  CAP_CONFIG_READ,
  CAP_CONFIG_WRITE,
  CAP_DOCUMENTS_READ,
  CAP_DOCUMENTS_WRITE,
  CAP_ORG_ADMIN,
  CAP_RUNS_EXECUTE,
  hasOrgCapability,
} from './orgCapabilities';

describe('hasOrgCapability', () => {
  it('returns false for null, undefined, or empty capabilities', () => {
    expect(hasOrgCapability(null, CAP_CONFIG_WRITE)).toBe(false);
    expect(hasOrgCapability(undefined, CAP_CONFIG_WRITE)).toBe(false);
    expect(hasOrgCapability([], CAP_CONFIG_WRITE)).toBe(false);
  });

  it('matches exact capability strings', () => {
    const viewerLike = [CAP_DOCUMENTS_READ, CAP_CONFIG_READ];
    expect(hasOrgCapability(viewerLike, CAP_DOCUMENTS_READ)).toBe(true);
    expect(hasOrgCapability(viewerLike, CAP_CONFIG_READ)).toBe(true);
    expect(hasOrgCapability(viewerLike, CAP_DOCUMENTS_WRITE)).toBe(false);
    expect(hasOrgCapability(viewerLike, CAP_CONFIG_WRITE)).toBe(false);
    expect(hasOrgCapability(viewerLike, CAP_RUNS_EXECUTE)).toBe(false);
    expect(hasOrgCapability(viewerLike, CAP_ORG_ADMIN)).toBe(false);
  });

  it('reflects operator union (read + documents.write + runs.execute)', () => {
    const operatorLike = [
      CAP_DOCUMENTS_READ,
      CAP_CONFIG_READ,
      CAP_DOCUMENTS_WRITE,
      CAP_RUNS_EXECUTE,
    ];
    expect(hasOrgCapability(operatorLike, CAP_DOCUMENTS_WRITE)).toBe(true);
    expect(hasOrgCapability(operatorLike, CAP_RUNS_EXECUTE)).toBe(true);
    expect(hasOrgCapability(operatorLike, CAP_CONFIG_WRITE)).toBe(false);
  });

  it('reflects builder including config.write', () => {
    const builderLike = [
      CAP_DOCUMENTS_READ,
      CAP_CONFIG_READ,
      CAP_DOCUMENTS_WRITE,
      CAP_RUNS_EXECUTE,
      CAP_CONFIG_WRITE,
    ];
    expect(hasOrgCapability(builderLike, CAP_CONFIG_WRITE)).toBe(true);
    expect(hasOrgCapability(builderLike, CAP_ORG_ADMIN)).toBe(false);
  });
});
