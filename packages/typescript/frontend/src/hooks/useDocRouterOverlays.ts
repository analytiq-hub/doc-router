import { useMemo } from 'react';
import type { OCRBlock } from '@docrouter/sdk';
import type { HighlightInfo } from '@/hooks/useOCRBlocks';
import type { PageRect } from '@/lib/pdfGeometry';
import { highlightInfoToPageRects, ocrBlocksToBboxRects } from '@/lib/docRouterPdfOverlays';

export function useDocRouterOverlays(
  highlightInfo: HighlightInfo | undefined,
  showBoundingBoxes: boolean,
  ocrBlocksForBoxes: OCRBlock[] | null,
): PageRect[] {
  return useMemo(() => {
    const highlight = highlightInfoToPageRects(highlightInfo);
    const bbox = showBoundingBoxes ? ocrBlocksToBboxRects(ocrBlocksForBoxes) : [];
    return [...highlight, ...bbox];
  }, [highlightInfo, showBoundingBoxes, ocrBlocksForBoxes]);
}
