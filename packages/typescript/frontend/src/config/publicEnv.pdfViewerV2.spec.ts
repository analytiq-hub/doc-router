import { afterEach, describe, expect, it, vi } from 'vitest';
import { publicPdfViewerV2 } from '@/config/publicEnv';

describe('publicPdfViewerV2', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('is true when unset (v2 default)', () => {
    vi.stubEnv('VITE_PDF_VIEWER_V2', '');
    expect(publicPdfViewerV2()).toBe(true);
  });

  it('is false when explicitly disabled', () => {
    vi.stubEnv('VITE_PDF_VIEWER_V2', '0');
    expect(publicPdfViewerV2()).toBe(false);
  });

  it('is true for 1 or true', () => {
    vi.stubEnv('VITE_PDF_VIEWER_V2', '1');
    expect(publicPdfViewerV2()).toBe(true);
    vi.stubEnv('VITE_PDF_VIEWER_V2', 'true');
    expect(publicPdfViewerV2()).toBe(true);
  });
});
