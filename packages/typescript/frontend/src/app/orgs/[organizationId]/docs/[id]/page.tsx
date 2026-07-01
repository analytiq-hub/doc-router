"use client"

import { use } from 'react';
import dynamic from 'next/dynamic';
import { useSearchParams } from 'next/navigation';
import { Box } from '@mui/material';
import {
  Panel,
  PanelGroup,
  PanelResizeHandle,
  type ImperativePanelGroupHandle,
} from 'react-resizable-panels';
import { useState, useEffect, useLayoutEffect, useRef, Suspense } from 'react';
import PDFSidebar from '@/components/PDFSidebar';

const AGENT_PANEL_BREAKPOINT = 640;
const AgentTab = dynamic(() => import('@/components/agent/AgentTab'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center">Loading agent...</div>
});
import type { HighlightInfo } from '@/types/index';
import type { PDFViewerControlsType } from '@/components/Layout';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import { EXTRACTION_HIGHLIGHT_AUTO_CLEAR_MS } from '@/constants/extractionHighlight';

const PDFViewer = dynamic(() => import('@/components/PDFViewer'), {
  ssr: false,
})

interface PageProps {
  params: Promise<{
    organizationId: string;
    id: string;
  }>;
}

/** Percent widths for mounted panels (sidebar, pdf, chat); must sum to 100. */
function getDocPagePanelLayout(L: boolean, P: boolean, C: boolean): number[] {
  if (L && P && C) return [25, 45, 30];
  if (L && P && !C) return [30, 70];
  if (L && !P && C) return [40, 60];
  if (L && !P && !C) return [100];
  if (!L && P && C) return [65, 35];
  if (!L && P && !C) return [100];
  if (!L && !P && C) return [100];
  return [100];
}

const PDFViewerPage = ({ params }: PageProps) => {
  const { organizationId, id } = use(params);
  const searchParams = useSearchParams();
  const showBoundingBoxesFromUrl = searchParams.has('bbox');
  const [showLeftPanel, setShowLeftPanel] = useState(true);
  const [showPdfPanel, setShowPdfPanel] = useState(true);
  const [showChatPanel, setShowChatPanel] = useState(true);
  const [highlightInfo, setHighlightInfo] = useState<HighlightInfo | undefined>();
  const [pdfDocument, setPdfDocument] = useState<PDFDocumentProxy | null>(null);
  const [isSmallScreen, setIsSmallScreen] = useState(false);
  const panelGroupRef = useRef<ImperativePanelGroupHandle>(null);

  useEffect(() => {
    const check = () => setIsSmallScreen(window.innerWidth <= AGENT_PANEL_BREAKPOINT);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  useEffect(() => {
    if (isSmallScreen) setShowChatPanel(false);
  }, [isSmallScreen]);

  useEffect(() => {
    const controls: PDFViewerControlsType = {
      showLeftPanel,
      setShowLeftPanel,
      showPdfPanel,
      setShowPdfPanel,
      showChatPanel,
      setShowChatPanel,
      isSmallScreen
    };
    window.pdfViewerControls = controls;

    const event = new Event('pdfviewercontrols');
    window.dispatchEvent(event);

    return () => {
      delete window.pdfViewerControls;
    };
  }, [showLeftPanel, showPdfPanel, showChatPanel, isSmallScreen]);

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
  }, [id]);

  const panelLayout = getDocPagePanelLayout(showLeftPanel, showPdfPanel, showChatPanel);
  let layoutIdx = 0;
  const leftPanelSize = showLeftPanel ? panelLayout[layoutIdx++] : undefined;
  const mainPanelSize = showPdfPanel ? panelLayout[layoutIdx++] : undefined;
  const rightPanelSize = showChatPanel ? panelLayout[layoutIdx++] : undefined;

  useLayoutEffect(() => {
    panelGroupRef.current?.setLayout(
      getDocPagePanelLayout(showLeftPanel, showPdfPanel, showChatPanel),
    );
  }, [showLeftPanel, showPdfPanel, showChatPanel]);

  if (!id) return <div>No PDF ID provided</div>;
  const pdfId = Array.isArray(id) ? id[0] : id;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <PanelGroup
            ref={panelGroupRef}
            id={`doc-page-panels-${pdfId}`}
            direction="horizontal"
            style={{ width: '100%', height: '100%' }}
          >
            {showLeftPanel && (
              <>
                <Panel id="doc-sidebar" defaultSize={leftPanelSize!} minSize={15} order={1}>
                  <Box sx={{ height: '100%', overflow: 'auto' }}>
                    <Suspense fallback={<div className="h-64 flex items-center justify-center">Loading sidebar...</div>}>
                      <PDFSidebar 
                        organizationId={organizationId} 
                        id={pdfId}
                        pdfDocument={pdfDocument}
                        onHighlight={setHighlightInfo}
                      />
                    </Suspense>
                  </Box>
                </Panel>
                <PanelResizeHandle style={{ width: '4px', background: '#e0e0e0', cursor: 'col-resize' }} />
              </>
            )}

            {showPdfPanel && (
              <Panel id="doc-pdf" defaultSize={mainPanelSize!} minSize={20} order={2}>
                <Box sx={{ height: '100%', overflow: 'hidden', minWidth: 0 }}>
                  <PDFViewer 
                    organizationId={organizationId} 
                    id={pdfId}
                    highlightInfo={highlightInfo}
                    initialShowBoundingBoxes={showBoundingBoxesFromUrl}
                    onPdfDocumentReady={setPdfDocument}
                  />
                </Box>
              </Panel>
            )}

            {showChatPanel && (
              <>
                <PanelResizeHandle style={{ width: '4px', background: '#e0e0e0', cursor: 'col-resize' }} />
                <Panel id="doc-chat" defaultSize={rightPanelSize!} minSize={20} order={3}>
                  <Box sx={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <AgentTab organizationId={organizationId} documentId={pdfId} />
                  </Box>
                </Panel>
              </>
            )}
          </PanelGroup>
        </Box>
      </Box>
  );
};

export default PDFViewerPage;
