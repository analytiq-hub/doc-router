"use client"

import { use } from 'react';
import dynamic from 'next/dynamic';
import { Box } from '@mui/material';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { useState, useEffect } from 'react';
const PDFSidebar = dynamic(() => import('@/components/PDFSidebar'), {
  ssr: false,
  loading: () => <div className="h-64 flex items-center justify-center">Loading sidebar...</div>
});
import type { HighlightInfo } from '@/types/index';

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
  const [showLeftPanel, setShowLeftPanel] = useState(true);
  const [showPdfPanel, setShowPdfPanel] = useState(true);
  const [highlightInfo, setHighlightInfo] = useState<HighlightInfo | undefined>();
  
  useEffect(() => {
    window.pdfViewerControls = {
      showLeftPanel,
      setShowLeftPanel,
      showPdfPanel,
      setShowPdfPanel
    };

    const event = new Event('pdfviewercontrols');
    window.dispatchEvent(event);

    return () => {
      delete window.pdfViewerControls;
    };
  }, [showLeftPanel, showPdfPanel]);

  useEffect(() => {
    console.log('Page - highlightedBlocks changed:', highlightInfo);
  }, [highlightInfo]);

  const getPanelSizes = () => {
    if (!showLeftPanel) {
      return {
        left: 0,
        main: 100
      };
    }

    return {
      left: 40,
      main: 60
    };
  };

  const panelSizes = getPanelSizes();

  if (!id) return <div>No PDF ID provided</div>;
  const pdfId = Array.isArray(id) ? id[0] : id;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <PanelGroup direction="horizontal" style={{ width: '100%', height: '100%' }}>
          {showLeftPanel && (
            <>
              <Panel defaultSize={panelSizes.left}>
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
            <Panel defaultSize={panelSizes.main}>
              <Box sx={{ height: '100%', overflow: 'hidden' }}>
                <PDFViewer 
                  organizationId={organizationId} 
                  id={pdfId}
                  highlightInfo={highlightInfo}
                />
              </Box>
            </Panel>
          )}
        </PanelGroup>
      </Box>
    </Box>
  );
};

export default PDFViewerPage;
