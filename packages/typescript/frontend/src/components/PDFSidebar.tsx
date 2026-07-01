'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { PDFFormsTabProbe } from './PDFFormsTabProbe';
import { docPageHrefWithSearch, sidebarTabFromQuery, type DocSidebarTab } from '@/utils/docPageUrl';

import type { HighlightInfo } from '@/types/index';
import type { PDFDocumentProxy } from 'pdfjs-dist';

const PDFExtractionSidebar = dynamic(() => import('./PDFExtractionSidebar'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center">Loading extraction...</div>,
});

const PDFFormSidebar = dynamic(() => import('./PDFFormSidebar'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center">Loading forms...</div>,
});

const PDFFlowsSidebar = dynamic(() => import('./PDFFlowsSidebar'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center">Loading flows...</div>,
});

interface Props {
  organizationId: string;
  id: string;
  /** Loaded PDF for embedded-text search when OCR blocks are missing or unmatched. */
  pdfDocument?: PDFDocumentProxy | null;
  onHighlight: (highlight: HighlightInfo) => void;
}

function resolveSidebarMode(
  requested: DocSidebarTab,
  showFlowsTab: boolean,
  showFormsTab: boolean,
  flowsTabKnown: boolean,
  formsTabKnown: boolean,
): DocSidebarTab {
  if (requested === 'flows') {
    if (!flowsTabKnown) return 'extraction';
    return showFlowsTab ? 'flows' : 'extraction';
  }
  if (requested === 'forms') {
    if (!formsTabKnown) return 'extraction';
    return showFormsTab ? 'forms' : 'extraction';
  }
  return 'extraction';
}

const PDFSidebar = ({ organizationId, id, pdfDocument, onHighlight }: Props) => {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const requestedTab = sidebarTabFromQuery(searchParams.get('tab'));

  const [showFlowsTab, setShowFlowsTab] = useState(false);
  const [showFormsTab, setShowFormsTab] = useState(false);
  const [flowsTabKnown, setFlowsTabKnown] = useState(false);
  const [formsTabKnown, setFormsTabKnown] = useState(false);

  const activeMode = useMemo(
    () => resolveSidebarMode(requestedTab, showFlowsTab, showFormsTab, flowsTabKnown, formsTabKnown),
    [requestedTab, showFlowsTab, showFormsTab, flowsTabKnown, formsTabKnown],
  );

  const handleFlowsHasFlows = useCallback((hasFlows: boolean) => {
    setShowFlowsTab(hasFlows);
    setFlowsTabKnown(true);
  }, []);

  const handleFormsHasForms = useCallback((hasForms: boolean) => {
    setShowFormsTab(hasForms);
    setFormsTabKnown(true);
  }, []);

  useEffect(() => {
    setShowFlowsTab(false);
    setShowFormsTab(false);
    setFlowsTabKnown(false);
    setFormsTabKnown(false);
  }, [id]);

  useEffect(() => {
    if (requestedTab === 'flows' && flowsTabKnown && !showFlowsTab) {
      router.replace(docPageHrefWithSearch(pathname, 'extraction', searchParams));
    }
    if (requestedTab === 'forms' && formsTabKnown && !showFormsTab) {
      router.replace(docPageHrefWithSearch(pathname, 'extraction', searchParams));
    }
  }, [
    requestedTab,
    flowsTabKnown,
    formsTabKnown,
    showFlowsTab,
    showFormsTab,
    pathname,
    router,
    searchParams.toString(),
  ]);

  const tabHref = useCallback(
    (mode: DocSidebarTab) => docPageHrefWithSearch(pathname, mode, searchParams),
    [pathname, searchParams],
  );

  const tabLinkClass = (mode: DocSidebarTab) =>
    `px-3 py-1 text-sm rounded transition-colors ${
      activeMode === mode
        ? 'bg-white text-gray-900 shadow-sm'
        : 'text-gray-600 hover:text-gray-900'
    }`;

  return (
    <div className="w-full h-full flex flex-col border-r border-black/10">
      <PDFFormsTabProbe
        organizationId={organizationId}
        documentId={id}
        onHasForms={handleFormsHasForms}
      />

      <div className="h-12 min-h-[48px] flex items-center px-4 bg-gray-100 text-black font-bold border-b border-black/10">
        <div className="flex bg-gray-200 rounded-md p-1">
          <Link href={tabHref('extraction')} replace scroll={false} className={tabLinkClass('extraction')}>
            Extraction
          </Link>
          {showFlowsTab ? (
            <Link href={tabHref('flows')} replace scroll={false} className={tabLinkClass('flows')}>
              Flows
            </Link>
          ) : null}
          {showFormsTab ? (
            <Link href={tabHref('forms')} replace scroll={false} className={tabLinkClass('forms')}>
              Forms
            </Link>
          ) : null}
        </div>
      </div>

      <div
        className={activeMode === 'flows' ? 'flex-grow overflow-hidden' : 'hidden'}
        aria-hidden={activeMode !== 'flows'}
      >
        <PDFFlowsSidebar
          organizationId={organizationId}
          id={id}
          panelActive={activeMode === 'flows'}
          onHasFlows={handleFlowsHasFlows}
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
        ) : activeMode === 'forms' && showFormsTab ? (
          <PDFFormSidebar
            organizationId={organizationId}
            id={id}
            pdfDocument={pdfDocument}
            onHighlight={onHighlight}
            onHasForms={handleFormsHasForms}
          />
        ) : null}
      </div>
    </div>
  );
};

export default PDFSidebar;
