import { useCallback, useEffect, useMemo, useState } from 'react';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import { toast } from 'sonner';
import type { HighlightInfo } from '@/types/index';
import { DocRouterOrgApi } from '@/utils/api';
import { useDocRouterPdfDocument } from '@/hooks/useDocRouterPdfDocument';
import { useDocRouterHighlightNavigation } from '@/hooks/useDocRouterHighlightNavigation';
import { useDocRouterOcrBbox } from '@/hooks/useDocRouterOcrBbox';
import { useDocRouterOcrOutput } from '@/hooks/useDocRouterOcrOutput';
import { useDocRouterOverlays } from '@/hooks/useDocRouterOverlays';
import { PdfViewerCore } from '@/components/pdf/viewer/PdfViewerCore';
import { DocRouterMenuExtras } from '@/components/pdf/viewer/docRouterMenuExtras';
import { DocRouterOcrOutputPanel } from '@/components/pdf/viewer/DocRouterOcrOutputPanel';
import { ErrorAlert } from '@/components/ErrorAlert';
import { toastActionError } from '@/utils/toastActionError';
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
  const api = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const { loading, fetchError, fileUrl, documentState, setDocumentState, fileName } = useDocRouterPdfDocument(
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

  const { showBoundingBoxes, toggleBoundingBoxes, ocrBlocksForBoxes, resetOcrBlocksForBoxes } =
    useDocRouterOcrBbox(organizationId, id, fileName, documentState, initialShowBoundingBoxes);

  const ocrOutput = useDocRouterOcrOutput(organizationId, id, fileName);

  const boxes = useDocRouterOverlays(highlightInfo, showBoundingBoxes, ocrBlocksForBoxes);
  const pageNavigation = useDocRouterHighlightNavigation(highlightInfo, currentPage);

  const handleRerunOcr = useCallback(async () => {
    try {
      await api.runOCR({ documentId: id });
      resetOcrBlocksForBoxes();
      setDocumentState('ocr_processing');
      toast.info('OCR requeued');
    } catch (err) {
      toastActionError('Failed to rerun OCR', err);
    }
  }, [api, id, resetOcrBlocksForBoxes, setDocumentState]);

  const menuExtras = (
    <DocRouterMenuExtras
      fileName={fileName}
      showBoundingBoxes={showBoundingBoxes}
      ocrPanelOpen={ocrOutput.ocrPanelKind != null}
      onToggleBoundingBoxes={() => void toggleBoundingBoxes()}
      onOpenOcrOutput={ocrOutput.openOcrOutput}
      onDownloadOcrJson={ocrOutput.downloadOcrJson}
      onRerunOcr={handleRerunOcr}
    />
  );

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
    <>
      <PdfViewerCore
        url={fileUrl}
        fileName={fileName}
        onPageChange={onPageChange}
        onDocumentReady={onPdfDocumentReady}
        boxes={boxes}
        pageNavigation={pageNavigation}
        menuExtras={menuExtras}
        loading={loading ? 'Loading PDF…' : undefined}
      />
      {ocrOutput.ocrPanelKind ? (
        <DocRouterOcrOutputPanel
          documentId={id}
          fileName={fileName}
          kind={ocrOutput.ocrPanelKind}
          metadataType={ocrOutput.ocrMetadataType}
          onClose={() => ocrOutput.setOcrPanelKind(null)}
          onKindChange={ocrOutput.setOcrPanelKind}
          onDownload={ocrOutput.downloadPanelExport}
          text={{ loading: ocrOutput.ocrLoading, error: ocrOutput.ocrError, content: ocrOutput.ocrText }}
          markdown={{
            loading: ocrOutput.ocrMarkdownLoading,
            error: ocrOutput.ocrMarkdownError,
            content: ocrOutput.ocrMarkdown,
          }}
          html={{ loading: ocrOutput.ocrHtmlLoading, error: ocrOutput.ocrHtmlError, content: ocrOutput.ocrHtml }}
        />
      ) : null}
    </>
  );
}
