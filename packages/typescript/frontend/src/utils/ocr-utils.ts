import type { OCRBlock } from '@docrouter/sdk';

/**
 * Flatten OCR blocks from the API or cached state: always a `OCRBlock[]`.
 * Handles a Textract envelope `{ Blocks: [...] }`, JSON strings, and stale `@docrouter/sdk` dist
 * that still returns the raw envelope from `getOCRBlocks`.
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

/**
 * 1-based page index from a Textract block (API may omit `Page` on some blocks; default 1).
 */
export function ocrBlockPageNum(block: Pick<OCRBlock, 'Page'>): number {
  const p = block.Page as unknown;
  if (typeof p === 'number' && Number.isFinite(p)) return Math.max(1, Math.trunc(p));
  if (typeof p === 'string') {
    const n = parseInt(p, 10);
    if (!Number.isNaN(n)) return Math.max(1, n);
  }
  return 1;
}

export type TextractNormalizedBox = { Left: number; Top: number; Width: number; Height: number };

/**
 * Normalized 0–1 Textract bounding box, from BoundingBox or derived from Polygon.
 */
export function getTextractNormalizedBox(block: Pick<OCRBlock, 'Geometry'>): TextractNormalizedBox | null {
  const g = block.Geometry;
  if (!g) return null;
  const bb = g.BoundingBox;
  if (
    bb &&
    typeof bb.Left === 'number' &&
    typeof bb.Top === 'number' &&
    typeof bb.Width === 'number' &&
    typeof bb.Height === 'number'
  ) {
    return bb;
  }
  const poly = g.Polygon;
  if (poly && poly.length >= 2) {
    const xs = poly.map((p) => p.X);
    const ys = poly.map((p) => p.Y);
    const left = Math.min(...xs);
    const top = Math.min(...ys);
    const right = Math.max(...xs);
    const bottom = Math.max(...ys);
    return {
      Left: left,
      Top: top,
      Width: Math.max(0, right - left),
      Height: Math.max(0, bottom - top),
    };
  }
  return null;
}

/**
 * Check if OCR is supported for a file based on its extension.
 * Matches the backend logic in packages/python/analytiq_data/common/doc.py
 * 
 * @param fileName - The file name (with extension)
 * @returns true if OCR is supported, false otherwise
 */
export function isOCRSupported(fileName: string | null | undefined): boolean {
  if (!fileName) return false;
  
  const lastDotIndex = fileName.lastIndexOf('.');
  if (lastDotIndex === -1) return false;
  
  const ext = fileName.substring(lastDotIndex).toLowerCase();
  
  // OCR not supported for structured data files and text files
  const skipExtensions = ['.csv', '.xls', '.xlsx', '.txt', '.md'];
  return !skipExtensions.includes(ext);
}

/**
 * Check if an error is a 404 "OCR ... not found" from the API (OCR not run yet or still processing).
 * Use this to avoid logging these as console errors and to show a user-friendly message.
 */
export function isOcrNotReadyError(err: unknown): boolean {
  const apiErr = err as Error & { status?: number };
  return (
    apiErr?.status === 404 &&
    typeof apiErr?.message === 'string' &&
    /OCR .* not found/i.test(apiErr.message)
  );
}
