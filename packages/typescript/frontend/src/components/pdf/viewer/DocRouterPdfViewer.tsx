import { useEffect } from 'react';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import type { HighlightInfo } from '@/types/index';
import { useDocRouterPdfDocument } from '@/hooks/useDocRouterPdfDocument';
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

/**
 * Doc-router shell: API loader + PdfViewerCore (Track B). Overlays and full toolbar land in later phases.
 */
export default function DocRouterPdfViewer({
  organizationId,
  id,
  highlightInfo: _highlightInfo,
  initialShowBoundingBoxes: _initialShowBoundingBoxes,
  onPdfDocumentReady,
  onViewerPageChange,
  onViewerFileNameChange,
}: DocRouterPdfViewerProps) {
  const { loading, fetchError, fileUrl, documentState, fileName } = useDocRouterPdfDocument(
    organizationId,
    id,
  );
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
      onPageChange={onViewerPageChange}
      onDocumentReady={onPdfDocumentReady}
      loadingOverlay={loading ? 'Loading PDF…' : undefined}
    />
  );
}
