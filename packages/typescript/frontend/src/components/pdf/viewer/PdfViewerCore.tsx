import 'pdfjs-dist/web/pdf_viewer.css';

import {
  AnnotationEditorType,
  AnnotationMode,
  getDocument,
  GlobalWorkerOptions,
  type PDFDocumentProxy,
} from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { EventBus, PDFLinkService, PDFViewer } from 'pdfjs-dist/web/pdf_viewer.mjs';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ErrorAlert } from '@/components/ErrorAlert';
import { ensurePdfjsWorker } from '@/utils/pdfjsWorker';
import { cn } from 'cn';

GlobalWorkerOptions.workerSrc = workerUrl;

const MAX_CANVAS_PIXELS = 16 * 1024 * 1024;

export type PdfViewerCoreProps = {
  url: string;
  fileName?: string;
  onPageChange?: (page: number) => void;
  onDocumentReady?: (pdf: PDFDocumentProxy) => void;
  loadingOverlay?: ReactNode;
  className?: string;
};

/** Phase 0 spike: PDF.js viewer, scroll sync, minimal toolbar (full orchestrator port in Phase 2). */
export function PdfViewerCore({
  url,
  fileName,
  onPageChange,
  onDocumentReady,
  loadingOverlay,
  className,
}: PdfViewerCoreProps) {
  const container = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<PDFViewer | null>(null);
  const eventBusRef = useRef<EventBus | null>(null);
  const onDocumentReadyRef = useRef(onDocumentReady);
  const onPageChangeRef = useRef(onPageChange);

  const [pdfjsReady, setPdfjsReady] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [current, setCurrent] = useState(1);
  const [pageInput, setPageInput] = useState('1');
  const [totalPages, setTotalPages] = useState(0);

  useEffect(() => {
    onDocumentReadyRef.current = onDocumentReady;
    onPageChangeRef.current = onPageChange;
  }, [onDocumentReady, onPageChange]);

  useEffect(() => {
    let cancelled = false;
    void ensurePdfjsWorker().then(() => {
      if (!cancelled) setPdfjsReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    onPageChangeRef.current?.(current);
  }, [current]);

  useEffect(() => {
    const element = container.current;
    if (!element || !pdfjsReady) return;

    const focus = element.focus.bind(element);
    element.focus = (options?: FocusOptions) => focus({ ...options, preventScroll: true });

    const eventBus = new EventBus();
    const linkService = new PDFLinkService({ eventBus });
    const viewer = new PDFViewer({
      container: element,
      eventBus,
      linkService,
      annotationMode: AnnotationMode.ENABLE_FORMS,
      annotationEditorMode: AnnotationEditorType.NONE,
      maxCanvasPixels: MAX_CANVAS_PIXELS,
      enableDetailCanvas: true,
      removePageBorders: true,
    });
    linkService.setViewer(viewer);
    viewerRef.current = viewer;
    eventBusRef.current = eventBus;

    eventBus.on('pagechanging', ({ pageNumber }: { pageNumber: number }) => {
      setCurrent(pageNumber);
      setPageInput(String(pageNumber));
    });

    return () => {
      viewer.setDocument(null as unknown as PDFDocumentProxy);
      viewerRef.current = null;
      eventBusRef.current = null;
      Reflect.deleteProperty(element, 'focus');
    };
  }, [pdfjsReady]);

  useEffect(() => {
    if (!pdfjsReady) return;
    let cancelled = false;
    setError(null);
    setReady(false);
    setTotalPages(0);

    const task = getDocument({
      url,
      withCredentials: false,
      disableRange: true,
      disableAutoFetch: false,
      enableXfa: false,
    });

    task.promise
      .then((loaded) => {
        if (cancelled) return;
        const viewer = viewerRef.current;
        const eventBus = eventBusRef.current;
        if (!viewer || !eventBus) return;

        setTotalPages(loaded.numPages);
        onDocumentReadyRef.current?.(loaded);

        eventBus.on(
          'pagesinit',
          () => {
            if (cancelled) return;
            viewer.currentScaleValue = 'page-width';
            setReady(true);
          },
          { once: true },
        );

        viewer.setDocument(loaded);
        (viewer.linkService as PDFLinkService).setDocument(loaded);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e);
      });

    return () => {
      cancelled = true;
      void task.destroy();
    };
  }, [url, pdfjsReady]);

  useEffect(() => {
    const element = container.current;
    if (!element || !ready || typeof ResizeObserver === 'undefined') return;
    const viewer = viewerRef.current;
    if (viewer) viewer.currentScaleValue = 'page-width';
    const observer = new ResizeObserver(() => {
      if (viewerRef.current) viewerRef.current.currentScaleValue = 'page-width';
    });
    observer.observe(element, { box: 'border-box' });
    return () => observer.disconnect();
  }, [ready]);

  const goTo = useCallback((page: number) => {
    const viewer = viewerRef.current;
    if (!viewer || totalPages < 1) return;
    const target = Math.min(totalPages, Math.max(1, Math.round(page)));
    viewer.currentPageNumber = target;
    setCurrent(target);
    setPageInput(String(target));
  }, [totalPages]);

  const commitPageInput = useCallback(() => {
    const parsed = Number.parseInt(pageInput, 10);
    if (Number.isFinite(parsed)) goTo(parsed);
    else setPageInput(String(current));
  }, [pageInput, current, goTo]);

  return (
    <div className={cn('@container flex h-full min-h-0 flex-col', className)}>
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b bg-card px-3 py-1.5 text-sm">
        <p className="min-w-0 flex-1 truncate font-medium" title={fileName}>
          {fileName || 'PDF'}
        </p>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Previous page"
            disabled={!ready || current <= 1}
            onClick={() => goTo(current - 1)}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <Input
            aria-label="Page number"
            className="h-8 w-14 text-center tabular-nums"
            value={pageInput}
            disabled={!ready}
            onChange={(e) => setPageInput(e.target.value)}
            onBlur={commitPageInput}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                commitPageInput();
              }
            }}
          />
          <span className="text-muted-foreground tabular-nums">/ {totalPages || '—'}</span>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Next page"
            disabled={!ready || current >= totalPages}
            onClick={() => goTo(current + 1)}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      {error ? (
        <div className="p-3">
          <ErrorAlert error={error} />
        </div>
      ) : null}

      <div className="relative min-h-0 flex-1 bg-muted">
        <div
          ref={container}
          className="pdf-viewer-scroller absolute inset-0 overflow-auto overscroll-contain"
        >
          <div className="pdfViewer" />
        </div>
        {!ready && !error ? (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
            {loadingOverlay ?? 'Loading PDF…'}
          </div>
        ) : null}
      </div>
    </div>
  );
}
