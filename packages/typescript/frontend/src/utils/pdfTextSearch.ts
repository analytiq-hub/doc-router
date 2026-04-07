import { Util } from 'pdfjs-dist';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import type { TextItem } from 'pdfjs-dist/types/src/display/api';
import type { PageViewport } from 'pdfjs-dist/types/src/display/display_utils';

export type PdfSearchHit = {
  page: number;
  /** Normalized 0–1 relative to page viewport (same convention as OCR overlay) */
  left: number;
  top: number;
  width: number;
  height: number;
};

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function itemToBounds(item: TextItem, viewport: PageViewport) {
  const tx = Util.transform(viewport.transform, item.transform);
  const fontHeight = Math.hypot(tx[2], tx[3]);
  const left = tx[4];
  const top = tx[5] - fontHeight;
  const scaleX = Math.hypot(tx[0], tx[1]);
  const width = item.width * scaleX;
  const height = fontHeight;
  return { left, top, width, height };
}

function mergeRects(
  rects: { left: number; top: number; width: number; height: number }[],
): { left: number; top: number; width: number; height: number } | null {
  if (rects.length === 0) return null;
  const minL = Math.min(...rects.map((r) => r.left));
  const minT = Math.min(...rects.map((r) => r.top));
  const maxR = Math.max(...rects.map((r) => r.left + r.width));
  const maxB = Math.max(...rects.map((r) => r.top + r.height));
  return { left: minL, top: minT, width: maxR - minL, height: maxB - minT };
}

function toNormalized(
  rect: { left: number; top: number; width: number; height: number },
  viewport: PageViewport,
): Pick<PdfSearchHit, 'left' | 'top' | 'width' | 'height'> {
  return {
    left: rect.left / viewport.width,
    top: rect.top / viewport.height,
    width: rect.width / viewport.width,
    height: rect.height / viewport.height,
  };
}

/** PDF.js throws this when the document/worker was torn down while async work was in flight. */
export function isPdfDocumentDetachedError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const msg = err.message ?? String(err);
  return (
    msg.includes('messageHandler') ||
    msg.includes('sendWithPromise') ||
    msg.includes('Worker was destroyed') ||
    msg.includes('Worker has been destroyed') ||
    msg.includes('Transport destroyed') ||
    msg.includes('Document has been destroyed')
  );
}

/**
 * Find all occurrences of `query` in the PDF text layer (embedded text only; scanned pages without a text layer won't match).
 */
export async function searchPdf(
  pdf: PDFDocumentProxy,
  query: string,
  caseSensitive: boolean,
  signal?: AbortSignal,
): Promise<PdfSearchHit[]> {
  const q = query.trim();
  if (!q) return [];

  const escaped = escapeRegExp(q);
  const flags = caseSensitive ? 'g' : 'gi';
  const hits: PdfSearchHit[] = [];

  for (let p = 1; p <= pdf.numPages; p++) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    try {
      const page = await pdf.getPage(p);
      const viewport = page.getViewport({ scale: 1 });
      const textContent = await page.getTextContent();
      const items = textContent.items.filter((x): x is TextItem => 'str' in x && typeof (x as TextItem).str === 'string');

      let fullText = '';
      const ranges: { start: number; end: number; itemIndex: number }[] = [];
      for (let i = 0; i < items.length; i++) {
        const start = fullText.length;
        fullText += items[i].str;
        ranges.push({ start, end: fullText.length, itemIndex: i });
      }

      const re = new RegExp(escaped, flags);
      let m: RegExpExecArray | null;
      while ((m = re.exec(fullText)) !== null) {
        const start = m.index;
        const end = start + m[0].length;
        if (end <= start) break;

        const overlapping = ranges.filter((r) => r.end > start && r.start < end);
        const rects = overlapping.map((r) => itemToBounds(items[r.itemIndex], viewport));
        const merged = mergeRects(rects);
        if (merged) {
          const n = toNormalized(merged, viewport);
          hits.push({ page: p, ...n });
        }
      }
    } catch (err) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      if (isPdfDocumentDetachedError(err)) return [];
      throw err;
    }
  }

  return hits;
}
