import type { OCRBlock } from './types';

/**
 * Normalize OCR blocks from the download/blocks API.
 * The backend returns a flat block list, but older responses or caches may still send a
 * Textract envelope `{ Blocks: [...] }`.
 */
export function normalizeOcrBlocksPayload(raw: unknown): OCRBlock[] {
  if (raw == null) return [];
  if (typeof raw === 'string') {
    try {
      return normalizeOcrBlocksPayload(JSON.parse(raw) as unknown);
    } catch {
      return [];
    }
  }
  if (Array.isArray(raw)) return raw as OCRBlock[];
  if (typeof raw === 'object' && raw !== null && 'Blocks' in raw) {
    const inner = (raw as { Blocks: unknown }).Blocks;
    if (Array.isArray(inner)) return inner as OCRBlock[];
    if (inner != null && typeof inner === 'object' && 'Blocks' in (inner as object)) {
      return normalizeOcrBlocksPayload(inner);
    }
  }
  return [];
}
