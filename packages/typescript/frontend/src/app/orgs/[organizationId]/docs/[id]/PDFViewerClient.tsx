"use client"

import dynamic from 'next/dynamic';
import { Box } from '@mui/material';
import {
  Panel,
  PanelGroup,
  PanelResizeHandle,
  type ImperativePanelGroupHandle,
} from 'react-resizable-panels';
import { useState, useEffect, useLayoutEffect, useRef, Suspense } from 'react';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import PDFSidebar from '@/components/PDFSidebar';
import type { HighlightInfo } from '@/types/index';
import { EXTRACTION_HIGHLIGHT_AUTO_CLEAR_MS } from '@/constants/extractionHighlight';

const PDFViewer = dynamic(() => import('@/components/PDFViewer'), {
  ssr: false,
})

interface PDFViewerClientProps {
  organizationId: string;
  id: string;
}

/** Percent widths for mounted panels (sidebar, pdf); must sum to 100. */
function getDocViewerPanelLayout(L: boolean, P: boolean): number[] {
  if (L && P) return [40, 60];
  if (L && !P) return [100];
  if (!L && P) return [100];
  return [100];
}

export default function PDFViewerClient({ organizationId, id }: PDFViewerClientProps) {
  const [showLeftPanel, setShowLeftPanel] = useState(true);
  const [showPdfPanel, setShowPdfPanel] = useState(true);
  const [showChatPanel, setShowChatPanel] = useState(false);
  const [highlightInfo, setHighlightInfo] = useState<HighlightInfo | undefined>();
  const [pdfDocument, setPdfDocument] = useState<PDFDocumentProxy | null>(null);
  const panelGroupRef = useRef<ImperativePanelGroupHandle>(null);

  useEffect(() => {
    window.pdfViewerControls = {
      showLeftPanel,
      setShowLeftPanel,
      showPdfPanel,
      setShowPdfPanel,
      showChatPanel,
      setShowChatPanel
    };

    const event = new Event('pdfviewercontrols');
    window.dispatchEvent(event);

    return () => {
      delete window.pdfViewerControls;
    };
  }, [showLeftPanel, showPdfPanel, showChatPanel]);

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

  const panelLayout = getDocViewerPanelLayout(showLeftPanel, showPdfPanel);
  let layoutIdx = 0;
  const leftPanelSize = showLeftPanel ? panelLayout[layoutIdx++] : undefined;
  const mainPanelSize = showPdfPanel ? panelLayout[layoutIdx++] : undefined;

  useLayoutEffect(() => {
    panelGroupRef.current?.setLayout(getDocViewerPanelLayout(showLeftPanel, showPdfPanel));
  }, [showLeftPanel, showPdfPanel]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <PanelGroup
            ref={panelGroupRef}
            id={`doc-viewer-panels-${id}`}
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
                        id={id}
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
                    id={id}
                    highlightInfo={highlightInfo}
                    onPdfDocumentReady={setPdfDocument}
                  />
                </Box>
              </Panel>
            )}
          </PanelGroup>
        </Box>
      </Box>
  );
}
