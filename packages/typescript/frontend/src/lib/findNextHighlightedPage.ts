import type { OCRBlock } from '@docrouter/sdk';
import type { HighlightInfo } from '@/hooks/useOCRBlocks';
import { ocrBlockPageNum } from '@/utils/ocr-utils';
import type { PdfSearchHit } from '@/utils/pdfTextSearch';

/** Next page for extraction/forms highlight cycling (legacy PDFViewer behavior). */
export function findNextHighlightedPage(
  highlightInfo: HighlightInfo | undefined,
  currentPage: number,
  isSameSearch: boolean,
): number | null {
  const blocks = highlightInfo?.blocks ?? [];
  const pdfHits = highlightInfo?.pdfFallbackHits ?? [];
  if (!blocks.length && !pdfHits.length) return null;

  const startPage = isSameSearch ? currentPage + 1 : currentPage;

  if (blocks.length) {
    const nextBlock = blocks
      .filter((block: OCRBlock) => ocrBlockPageNum(block) >= startPage)
      .sort((a, b) => ocrBlockPageNum(a) - ocrBlockPageNum(b))[0];

    if (nextBlock) return ocrBlockPageNum(nextBlock);

    const firstBlock = [...blocks].sort((a, b) => ocrBlockPageNum(a) - ocrBlockPageNum(b))[0];
    return firstBlock ? ocrBlockPageNum(firstBlock) : null;
  }

  const pages = [...new Set(pdfHits.map((h: PdfSearchHit) => h.page))].sort((a, b) => a - b);
  const after = pages.find((p) => p >= startPage);
  if (after !== undefined) return after;
  return pages[0] ?? null;
}
