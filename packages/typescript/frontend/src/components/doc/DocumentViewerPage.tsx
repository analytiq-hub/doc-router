'use client';

import dynamic from '@/utils/dynamicImport';
import { useSearchParams } from '@/utils/appRouter';
import {
  Panel,
  PanelGroup,
  PanelResizeHandle,
  type ImperativePanelGroupHandle,
} from 'react-resizable-panels';
import { useState, useEffect, useLayoutEffect, useRef, useCallback, type SetStateAction } from 'react';
import type { HighlightInfo } from '@/types/index';
import type { PDFViewerControlsType } from '@/components/Layout';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import { EXTRACTION_HIGHLIGHT_AUTO_CLEAR_MS } from '@/constants/extractionHighlight';
import { cn } from 'cn';
import { MuiPdfThemeIsland } from '@/components/pdf/MuiPdfThemeIsland';
import { publicPdfViewerV2 } from '@/config/publicEnv';
import { sidebarTabFromQuery } from '@/utils/docPageUrl';

const AGENT_PANEL_BREAKPOINT = 640;

const pdfViewerV2 = publicPdfViewerV2();

const PDFViewer = dynamic(
  () =>
    pdfViewerV2
      ? import('@/components/pdf/viewer/DocRouterPdfViewer')
      : import('@/components/PDFViewer'),
  { ssr: false },
);

const PDFSidebar = dynamic(() => import('@/components/PDFSidebar'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading panel…</div>
  ),
});

export type DocumentViewerPageProps = {
  organizationId: string;
  id: string;
};

/** Percent widths for mounted panels (pdf, right panel); must sum to 100. */
function getDocPagePanelLayout(showPdf: boolean, showRight: boolean): number[] {
  if (showPdf && showRight) return [58, 42];
  if (showPdf && !showRight) return [100];
  if (!showPdf && showRight) return [100];
  return [100];
}

const panelShell = 'flex h-full min-h-0 min-w-0 flex-col overflow-hidden';

export default function DocumentViewerPage({ organizationId, id }: DocumentViewerPageProps) {
  const searchParams = useSearchParams();
  const showBoundingBoxesFromUrl = searchParams.has('bbox');
  const rightPanelTab = sidebarTabFromQuery(searchParams.get('tab'));

  const [showPdfPanel, setShowPdfPanel] = useState(true);
  const [showRightPanel, setShowRightPanel] = useState(true);
  const [highlightInfo, setHighlightInfo] = useState<HighlightInfo | undefined>();
  const [pdfDocument, setPdfDocument] = useState<PDFDocumentProxy | null>(null);
  const [pdfPage, setPdfPage] = useState(1);
  const [viewerFileName, setViewerFileName] = useState<string | null>(null);
  const [isSmallScreen, setIsSmallScreen] = useState(false);
  const panelGroupRef = useRef<ImperativePanelGroupHandle>(null);

  const onViewerPageChange = useCallback((page: number) => setPdfPage(page), []);
  const onViewerFileNameChange = useCallback((name: string | null) => setViewerFileName(name), []);

  /** react-resizable-panels requires at least one child; auto-show the other pane when hiding the last one. */
  const setShowPdfPanelGuarded = useCallback((update: SetStateAction<boolean>) => {
    setShowPdfPanel((pdf) => {
      const next = typeof update === 'function' ? update(pdf) : update;
      if (!next) {
        setShowRightPanel((right) => (right ? right : true));
      }
      return next;
    });
  }, []);

  const setShowRightPanelGuarded = useCallback((update: SetStateAction<boolean>) => {
    setShowRightPanel((right) => {
      const next = typeof update === 'function' ? update(right) : update;
      if (!next) {
        setShowPdfPanel((pdf) => (pdf ? pdf : true));
      }
      return next;
    });
  }, []);

  useEffect(() => {
    const check = () => setIsSmallScreen(window.innerWidth <= AGENT_PANEL_BREAKPOINT);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  useEffect(() => {
    if (isSmallScreen) setShowRightPanel(false);
  }, [isSmallScreen]);

  useEffect(() => {
    const controls: PDFViewerControlsType = {
      showRightPanel,
      setShowRightPanel: setShowRightPanelGuarded,
      showPdfPanel,
      setShowPdfPanel: setShowPdfPanelGuarded,
      isSmallScreen,
      rightPanelTab,
    };
    window.pdfViewerControls = controls;

    const event = new Event('pdfviewercontrols');
    window.dispatchEvent(event);

    return () => {
      delete window.pdfViewerControls;
    };
  }, [
    showRightPanel,
    showPdfPanel,
    isSmallScreen,
    rightPanelTab,
    setShowPdfPanelGuarded,
    setShowRightPanelGuarded,
  ]);

  useEffect(() => {
    const has =
      (highlightInfo?.blocks?.length ?? 0) > 0 ||
      (highlightInfo?.pdfFallbackHits?.length ?? 0) > 0;
    if (!has) return;
    const timerId = window.setTimeout(() => {
      setHighlightInfo(undefined);
    }, EXTRACTION_HIGHLIGHT_AUTO_CLEAR_MS);
    return () => window.clearTimeout(timerId);
  }, [highlightInfo]);

  useEffect(() => {
    setHighlightInfo(undefined);
    setPdfPage(1);
    setViewerFileName(null);
  }, [id]);

  const panelLayout = getDocPagePanelLayout(showPdfPanel, showRightPanel);
  let layoutIdx = 0;
  const pdfPanelSize = showPdfPanel ? panelLayout[layoutIdx++] : undefined;
  const rightPanelSize = showRightPanel ? panelLayout[layoutIdx++] : undefined;

  useLayoutEffect(() => {
    const panelCount = (showPdfPanel ? 1 : 0) + (showRightPanel ? 1 : 0);
    if (panelCount === 0) return;
    const layout = getDocPagePanelLayout(showPdfPanel, showRightPanel);
    if (layout.length !== panelCount) return;
    panelGroupRef.current?.setLayout(layout);
  }, [showPdfPanel, showRightPanel]);

  if (!id) return <div>No PDF ID provided</div>;
  const pdfId = Array.isArray(id) ? id[0] : id;

  const pageBody = (
    <div className={cn('flex min-h-0 flex-1 flex-col overflow-hidden')}>
        <div className="flex min-h-0 flex-1 overflow-hidden">
          <PanelGroup
            ref={panelGroupRef}
            id={`doc-page-panels-${pdfId}`}
            direction="horizontal"
            className="h-full w-full"
          >
            {showPdfPanel && (
              <Panel
                id="doc-pdf"
                defaultSize={pdfPanelSize!}
                minSize={25}
                order={1}
                className="flex min-h-0 min-w-0 flex-col overflow-hidden"
              >
                <div className={panelShell}>
                  <PDFViewer
                    organizationId={organizationId}
                    id={pdfId}
                    highlightInfo={highlightInfo}
                    initialShowBoundingBoxes={showBoundingBoxesFromUrl}
                    onPdfDocumentReady={setPdfDocument}
                    onViewerPageChange={onViewerPageChange}
                    onViewerFileNameChange={onViewerFileNameChange}
                  />
                </div>
              </Panel>
            )}

            {showPdfPanel && showRightPanel && (
              <PanelResizeHandle className="w-1 cursor-col-resize bg-border" />
            )}

            {showRightPanel && (
              <Panel
                id="doc-sidebar"
                defaultSize={rightPanelSize!}
                minSize={22}
                order={2}
                className="flex min-h-0 min-w-0 flex-col overflow-hidden"
              >
                <div className={cn(panelShell, 'overflow-hidden')}>
                  <PDFSidebar
                    organizationId={organizationId}
                    id={pdfId}
                    pdfDocument={pdfDocument}
                    onHighlight={setHighlightInfo}
                    pdfPage={pdfPage}
                    fileName={viewerFileName}
                  />
                </div>
              </Panel>
            )}
          </PanelGroup>
        </div>
    </div>
  );

  if (pdfViewerV2) return pageBody;
  return <MuiPdfThemeIsland>{pageBody}</MuiPdfThemeIsland>;
}
