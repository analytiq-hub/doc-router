"use client"

import { use } from 'react';
import dynamic from 'next/dynamic';
import { useSearchParams } from 'next/navigation';
import { Box } from '@mui/material';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { useState, useEffect } from 'react';

const AGENT_PANEL_BREAKPOINT = 640;
const PDFSidebar = dynamic(() => import('@/components/PDFSidebar'), {
  ssr: false,
  loading: () => <div className="h-64 flex items-center justify-center">Loading sidebar...</div>
});
const AgentTab = dynamic(() => import('@/components/agent/AgentTab'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center">Loading agent...</div>
});
import type { HighlightInfo } from '@/types/index';
import type { PDFViewerControlsType } from '@/components/Layout';

const PDFViewer = dynamic(() => import('@/components/PDFViewer'), {
  ssr: false,
})

interface PageProps {
  params: Promise<{
    organizationId: string;
    id: string;
  }>;
}

const PDFViewerPage = ({ params }: PageProps) => {
  const { organizationId, id } = use(params);
  const searchParams = useSearchParams();
  const showBoundingBoxesFromUrl = searchParams.has('bbox');
  const [showLeftPanel, setShowLeftPanel] = useState(true);
  const [showPdfPanel, setShowPdfPanel] = useState(true);
  const [showChatPanel, setShowChatPanel] = useState(true);
  const [highlightInfo, setHighlightInfo] = useState<HighlightInfo | undefined>();
  const [isSmallScreen, setIsSmallScreen] = useState(false);

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

  // Three panels: extraction (left) | PDF (center) | agent (right, optional)
  const getDefaultSizes = () => {
    if (!showLeftPanel && !showChatPanel) return { left: 0, main: 100, right: 0 };
    if (!showLeftPanel) return { left: 0, main: 65, right: 35 };
    if (!showChatPanel) return { left: 30, main: 70, right: 0 };
    return { left: 25, main: 45, right: 30 };
  };

  const defaultSizes = getDefaultSizes();

  if (!id) return <div>No PDF ID provided</div>;
  const pdfId = Array.isArray(id) ? id[0] : id;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <PanelGroup id={`doc-page-panels-${pdfId}`} direction="horizontal" style={{ width: '100%', height: '100%' }}>
            {showLeftPanel && (
              <>
                <Panel defaultSize={defaultSizes.left} minSize={15} order={1}>
                  <Box sx={{ height: '100%', overflow: 'auto' }}>
                    <PDFSidebar 
                      organizationId={organizationId} 
                      id={pdfId}
                      onHighlight={setHighlightInfo}
                      onClearHighlight={() => setHighlightInfo(undefined)}
                    />
                  </Box>
                </Panel>
                <PanelResizeHandle style={{ width: '4px', background: '#e0e0e0', cursor: 'col-resize' }} />
              </>
            )}

            {showPdfPanel && (
              <Panel defaultSize={defaultSizes.main} minSize={20} order={2}>
                <Box sx={{ height: '100%', overflow: 'hidden' }}>
                  <PDFViewer 
                    organizationId={organizationId} 
                    id={pdfId}
                    highlightInfo={highlightInfo}
                    initialShowBoundingBoxes={showBoundingBoxesFromUrl}
                  />
                </Box>
              </Panel>
            )}

            {showChatPanel && (
              <>
                <PanelResizeHandle style={{ width: '4px', background: '#e0e0e0', cursor: 'col-resize' }} />
                <Panel defaultSize={defaultSizes.right} minSize={20} order={3}>
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
