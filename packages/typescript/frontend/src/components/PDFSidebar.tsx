import React, { useState, useEffect, useMemo } from 'react';
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
import { DocRouterOrgApi } from '@/utils/api';

interface Props {
  organizationId: string;
  id: string;
  onHighlight: (highlight: HighlightInfo) => void;
  onClearHighlight?: () => void;
}

type SidebarMode = 'extraction' | 'forms';

const PDFSidebar = ({ organizationId, id, onHighlight, onClearHighlight }: Props) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [activeMode, setActiveMode] = useState<SidebarMode>('extraction');
  const [documentName, setDocumentName] = useState<string>('');

  useEffect(() => {
    const fetchDocumentName = async () => {
      try {
        const response = await docRouterOrgApi.getDocument({
          documentId: id,
          fileType: "pdf"
        });
        setDocumentName(response.document_name);
      } catch (error) {
        console.error('Error fetching document name:', error);
        setDocumentName('Untitled Document');
      }
    };

    fetchDocumentName();
  }, [organizationId, id, docRouterOrgApi]);

  return (
    <div className="w-full h-full flex flex-col border-r border-black/10">
      {/* Header with document name and tabs */}
      <div className="h-12 min-h-[48px] flex items-center justify-between px-4 bg-gray-100 text-black font-bold border-b border-black/10">
        <div className="flex items-center gap-4">
          <div className="w-[200px] flex justify-end">
            <span className="text-sm font-bold text-gray-900 truncate max-w-[180px] block">
              {documentName || 'Loading...'}
            </span>
          </div>
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