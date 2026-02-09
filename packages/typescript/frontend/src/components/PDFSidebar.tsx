import React, { useState } from 'react';
import dynamic from 'next/dynamic';

const PDFExtractionSidebar = dynamic(() => import('./PDFExtractionSidebar'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center">Loading extraction...</div>
});

const PDFFormSidebar = dynamic(() => import('./PDFFormSidebar'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center">Loading forms...</div>
});

import type { HighlightInfo } from '@/types/index';

interface Props {
  organizationId: string;
  id: string;
  onHighlight: (highlight: HighlightInfo) => void;
  onClearHighlight?: () => void;
}

type SidebarMode = 'extraction' | 'forms';

const PDFSidebar = ({ organizationId, id, onHighlight, onClearHighlight }: Props) => {
  const [activeMode, setActiveMode] = useState<SidebarMode>('extraction');

  return (
    <div className="w-full h-full flex flex-col border-r border-black/10">
      {/* Header with Extraction / Forms tabs only */}
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
          </div>
      </div>
      
      {/* Content area */}
      <div className="flex-grow overflow-hidden">
        {activeMode === 'extraction' ? (
          <PDFExtractionSidebar
            organizationId={organizationId}
            id={id}
            onHighlight={onHighlight}
            onClearHighlight={onClearHighlight}
          />
        ) : (
          <PDFFormSidebar
            organizationId={organizationId}
            id={id}
            onHighlight={onHighlight}
            onClearHighlight={onClearHighlight}
          />
        )}
      </div>
    </div>
  );
};

export default PDFSidebar; 