import { describe, expect, it } from 'vitest';
import type { OCRBlock } from '@docrouter/sdk';
import { highlightInfoToPageRects, ocrBlocksToBboxRects } from '@/lib/docRouterPdfOverlays';

describe('docRouterPdfOverlays', () => {
  it('maps Textract blocks to PageRect', () => {
    const block = {
      BlockType: 'WORD',
      Page: 2,
      Text: 'hello',
      Geometry: { BoundingBox: { Left: 0.1, Top: 0.2, Width: 0.3, Height: 0.05 } },
    } as OCRBlock;
    const rects = highlightInfoToPageRects({
      blocks: [block],
      promptId: 'p',
      value: 'hello',
    });
    expect(rects).toHaveLength(1);
    expect(rects[0].page).toBe(2);
    expect(rects[0].left).toBeLessThan(0.11);
    expect(rects[0].width).toBeGreaterThan(0.3);
  });

  it('prefers OCR blocks over pdf fallback hits', () => {
    const rects = highlightInfoToPageRects({
      blocks: [{ BlockType: 'WORD', Page: 1, Geometry: { BoundingBox: { Left: 0, Top: 0, Width: 0.1, Height: 0.1 } } } as OCRBlock],
      promptId: 'p',
      value: 'x',
      pdfFallbackHits: [{ page: 1, left: 0.5, top: 0.5, width: 0.1, height: 0.1 }],
    });
    expect(rects[0].left).toBeLessThan(0.05);
  });

  it('maps bbox words with labels', () => {
    const rects = ocrBlocksToBboxRects([
      { BlockType: 'WORD', Page: 1, Text: 'Tax', Geometry: { BoundingBox: { Left: 0, Top: 0, Width: 0.2, Height: 0.1 } } } as OCRBlock,
    ]);
    expect(rects[0].label).toBe('Tax');
  });
});
