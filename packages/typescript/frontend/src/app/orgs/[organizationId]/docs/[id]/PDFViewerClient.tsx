"use client"

import dynamic from 'next/dynamic';
import { Box } from '@mui/material';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { useState, useEffect } from 'react';
import type { PDFDocumentProxy } from 'pdfjs-dist';
const PDFSidebar = dynamic(() => import('@/components/PDFSidebar'), {
  ssr: false,
  loading: () => <div className="h-64 flex items-center justify-center">Loading sidebar...</div>
});
import type { HighlightInfo } from '@/types/index';
import { EXTRACTION_HIGHLIGHT_AUTO_CLEAR_MS } from '@/constants/extractionHighlight';

const PDFViewer = dynamic(() => import('@/components/PDFViewer'), {
  ssr: false,
})

interface PDFViewerClientProps {
  organizationId: string;
  id: string;
}

export default function PDFViewerClient({ organizationId, id }: PDFViewerClientProps) {
  const [showLeftPanel, setShowLeftPanel] = useState(true);
  const [showPdfPanel, setShowPdfPanel] = useState(true);
  const [showChatPanel, setShowChatPanel] = useState(false);
  const [highlightInfo, setHighlightInfo] = useState<HighlightInfo | undefined>();
  const [pdfDocument, setPdfDocument] = useState<PDFDocumentProxy | null>(null);

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

  // Only left + PDF (no agent panel); sizes must sum to 100% for mounted panels.
  const panelDefaultSizes = (() => {
    const L = showLeftPanel;
    const P = showPdfPanel;
    if (L && P) return [40, 60];
    if (L && !P) return [100];
    if (!L && P) return [100];
    return [100];
  })();
  let pi = 0;
  const leftPanelSize = showLeftPanel ? panelDefaultSizes[pi++] : undefined;
  const mainPanelSize = showPdfPanel ? panelDefaultSizes[pi++] : undefined;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <PanelGroup id={`doc-viewer-panels-${id}`} direction="horizontal" style={{ width: '100%', height: '100%' }}>
            {showLeftPanel && (
              <>
                <Panel defaultSize={leftPanelSize!}>
                  <Box sx={{ height: '100%', overflow: 'auto' }}>
                    <PDFSidebar
                      organizationId={organizationId}
                      id={id}
                      pdfDocument={pdfDocument}
                      onHighlight={setHighlightInfo}
                    />
                  </Box>
                </Panel>
                <PanelResizeHandle style={{ width: '4px', background: '#e0e0e0', cursor: 'col-resize' }} />
              </>
            )}

            {showPdfPanel && (
              <Panel defaultSize={mainPanelSize!}>
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
