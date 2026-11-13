import type { OCRBlock } from '@docrouter/sdk';
import type { HighlightInfo } from '@/hooks/useOCRBlocks';
import type { PageRect } from '@/lib/pdfGeometry';
import { getTextractNormalizedBox, ocrBlockPageNum } from '@/utils/ocr-utils';
import type { PdfSearchHit } from '@/utils/pdfTextSearch';

const HIGHLIGHT_PAD = 0.01;

function textractToRects(blocks: OCRBlock[], labelWords: boolean): PageRect[] {
  const out: PageRect[] = [];
  for (const block of blocks) {
    const box = getTextractNormalizedBox(block);
    if (!box) continue;
    const pad = HIGHLIGHT_PAD;
    out.push({
      page: ocrBlockPageNum(block),
      left: Math.max(0, box.Left - pad),
      top: Math.max(0, box.Top - pad),
      width: Math.min(1, box.Width + pad * 2),
      height: Math.min(1, box.Height + pad * 2),
      ...(labelWords && block.Text ? { label: block.Text } : {}),
    });
  }
  return out;
}

function pdfHitsToRects(hits: PdfSearchHit[]): PageRect[] {
  return hits.map((hit) => ({
    page: hit.page,
    left: hit.left,
    top: hit.top,
    width: hit.width,
    height: hit.height,
  }));
}

/** Extraction / forms find highlights → orchestrator overlay rects. */
export function highlightInfoToPageRects(highlightInfo: HighlightInfo | undefined): PageRect[] {
  if (!highlightInfo) return [];
  const blocks = highlightInfo.blocks ?? [];
  const pdfHits = highlightInfo.pdfFallbackHits ?? [];
  if (blocks.length) return textractToRects(blocks, false);
  return pdfHitsToRects(pdfHits);
}

/** OCR WORD (fallback LINE) blocks for bbox mode. */
export function ocrBlocksToBboxRects(blocks: OCRBlock[] | null): PageRect[] {
  if (!blocks?.length) return [];
  const words = blocks.filter((b) => b.BlockType === 'WORD');
  const draw = words.length ? words : blocks.filter((b) => b.BlockType === 'LINE');
  return textractToRects(draw, true);
}
