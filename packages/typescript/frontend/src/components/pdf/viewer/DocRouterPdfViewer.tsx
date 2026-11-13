import { useCallback, useEffect, useState } from 'react';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import type { HighlightInfo } from '@/types/index';
import { useDocRouterPdfDocument } from '@/hooks/useDocRouterPdfDocument';
import { useDocRouterHighlightNavigation } from '@/hooks/useDocRouterHighlightNavigation';
import { useDocRouterOcrBbox } from '@/hooks/useDocRouterOcrBbox';
import { useDocRouterOverlays } from '@/hooks/useDocRouterOverlays';
import { PdfViewerCore } from '@/components/pdf/viewer/PdfViewerCore';
import { ErrorAlert } from '@/components/ErrorAlert';
import { cn } from 'cn';

export type DocRouterPdfViewerProps = {
  organizationId: string;
  id: string;
  highlightInfo?: HighlightInfo;
  initialShowBoundingBoxes?: boolean;
  onPdfDocumentReady?: (pdf: PDFDocumentProxy) => void;
  onViewerPageChange?: (page: number) => void;
  onViewerFileNameChange?: (fileName: string | null) => void;
};

export default function DocRouterPdfViewer({
  organizationId,
  id,
  highlightInfo,
  initialShowBoundingBoxes = false,
  onPdfDocumentReady,
  onViewerPageChange,
  onViewerFileNameChange,
}: DocRouterPdfViewerProps) {
  const { loading, fetchError, fileUrl, documentState, fileName } = useDocRouterPdfDocument(
    organizationId,
    id,
  );

  const [currentPage, setCurrentPage] = useState(1);
  const onPageChange = useCallback(
    (page: number) => {
      setCurrentPage(page);
      onViewerPageChange?.(page);
    },
    [onViewerPageChange],
  );

  const { showBoundingBoxes, ocrBlocksForBoxes } = useDocRouterOcrBbox(
    organizationId,
    id,
    fileName,
    documentState,
    initialShowBoundingBoxes,
  );

  const boxes = useDocRouterOverlays(highlightInfo, showBoundingBoxes, ocrBlocksForBoxes);
  const pageNavigation = useDocRouterHighlightNavigation(highlightInfo, currentPage);

  useEffect(() => {
    setCurrentPage(1);
  }, [id]);

  useEffect(() => {
    onViewerFileNameChange?.(fileName ? fileName : null);
  }, [fileName, onViewerFileNameChange]);

  const processing =
    documentState === 'ocr_processing' || documentState === 'llm_processing';

  if (fetchError) {
    return (
      <div className="p-4">
        <ErrorAlert error={fetchError} />
      </div>
    );
  }

  if (loading && !fileUrl) {
    return (
      <div className={cn('flex h-full items-center justify-center text-sm text-muted-foreground')}>
        Loading PDF…
      </div>
    );
  }

  if (!fileUrl) {
    if (processing) {
      return (
        <div className={cn('flex h-full items-center justify-center px-4 text-center text-sm text-muted-foreground')}>
          Document is being processed. PDF will appear when ready.
        </div>
      );
    }
    return (
      <div className={cn('flex h-full items-center justify-center px-4 text-center text-sm text-destructive')}>
        No PDF file available.
      </div>
    );
  }

  return (
    <PdfViewerCore
      url={fileUrl}
      fileName={fileName}
      onPageChange={onPageChange}
      onDocumentReady={onPdfDocumentReady}
      boxes={boxes}
      pageNavigation={pageNavigation}
      loading={loading ? 'Loading PDF…' : undefined}
    />
  );
}
