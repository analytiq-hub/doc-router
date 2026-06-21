import React, { useCallback, useState } from 'react';
import dynamic from 'next/dynamic';

const PDFExtractionSidebar = dynamic(() => import('./PDFExtractionSidebar'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center">Loading extraction...</div>
});

const PDFFormSidebar = dynamic(() => import('./PDFFormSidebar'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center">Loading forms...</div>
});

const PDFFlowsSidebar = dynamic(() => import('./PDFFlowsSidebar'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center">Loading flows...</div>
});

import type { HighlightInfo } from '@/types/index';
import type { PDFDocumentProxy } from 'pdfjs-dist';

interface Props {
  organizationId: string;
  id: string;
  /** Loaded PDF for embedded-text search when OCR blocks are missing or unmatched. */
  pdfDocument?: PDFDocumentProxy | null;
  onHighlight: (highlight: HighlightInfo) => void;
}

type SidebarMode = 'extraction' | 'forms' | 'flows';

const PDFSidebar = ({ organizationId, id, pdfDocument, onHighlight }: Props) => {
  const [activeMode, setActiveMode] = useState<SidebarMode>('extraction');
  const [showFlowsTab, setShowFlowsTab] = useState(false);

  const handleFlowsHasResults = useCallback((hasResults: boolean) => {
    setShowFlowsTab(hasResults);
    setActiveMode((cur) => {
      if (!hasResults && cur === 'flows') return 'extraction';
      return cur;
    });
  }, []);

  return (
    <div className="w-full h-full flex flex-col border-r border-black/10">
      <div className="h-12 min-h-[48px] flex items-center px-4 bg-gray-100 text-black font-bold border-b border-black/10">
        <div className="flex bg-gray-200 rounded-md p-1">
            <button
              onClick={() => setActiveMode('extraction')}
              className={`px-3 py-1 text-sm rounded transition-colors ${
                activeMode === 'extraction'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Extraction
            </button>
            <button
              onClick={() => setActiveMode('forms')}
              className={`px-3 py-1 text-sm rounded transition-colors ${
                activeMode === 'forms'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Forms
            </button>
            {showFlowsTab ? (
              <button
                onClick={() => setActiveMode('flows')}
                className={`px-3 py-1 text-sm rounded transition-colors ${
                  activeMode === 'flows'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Flows
              </button>
            ) : null}
          </div>
      </div>

      <div className={activeMode === 'flows' ? 'flex-grow overflow-hidden' : 'hidden'}>
        <PDFFlowsSidebar
          organizationId={organizationId}
          id={id}
          onHasResults={handleFlowsHasResults}
        />
      </div>

      <div className={activeMode === 'flows' ? 'hidden' : 'flex-grow overflow-hidden'}>
        {activeMode === 'extraction' ? (
          <PDFExtractionSidebar
            organizationId={organizationId}
            id={id}
            pdfDocument={pdfDocument}
            onHighlight={onHighlight}
          />
        ) : (
          <PDFFormSidebar
            organizationId={organizationId}
            id={id}
            pdfDocument={pdfDocument}
            onHighlight={onHighlight}
          />
        )}
      </div>
    </div>
  );
};

export default PDFSidebar;
