'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import dynamic from '@/utils/dynamicImport';
import { usePathname, useRouter, useSearchParams } from '@/utils/appRouter';
import { PDFFormsTabProbe } from './PDFFormsTabProbe';
import { docPageHrefWithSearch, sidebarTabFromQuery, type DocSidebarTab } from '@/utils/docPageUrl';

import type { HighlightInfo } from '@/types/index';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import { Card } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import PDFTextPanel from '@/components/doc/PDFTextPanel';
import PDFInfoPanel from '@/components/doc/PDFInfoPanel';

const PDFExtractionSidebar = dynamic(() => import('./PDFExtractionSidebar'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">Loading extraction…</div>,
});

const PDFFormSidebar = dynamic(() => import('./PDFFormSidebar'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">Loading forms…</div>,
});

const PDFFlowsSidebar = dynamic(() => import('./PDFFlowsSidebar'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">Loading flows…</div>,
});

const AgentTab = dynamic(() => import('@/components/agent/AgentTab'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">Loading chat…</div>,
});

interface Props {
  organizationId: string;
  id: string;
  pdfDocument?: PDFDocumentProxy | null;
  onHighlight: (highlight: HighlightInfo) => void;
  pdfPage: number;
  fileName: string | null;
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
  if (requested === 'text' || requested === 'info' || requested === 'chat') return requested;
  return 'extraction';
}

const TAB_LABELS: Record<DocSidebarTab, string> = {
  extraction: 'Extraction',
  flows: 'Flows',
  text: 'Text',
  info: 'Info',
  chat: 'Chat',
  forms: 'Forms',
};

const PDFSidebar = ({ organizationId, id, pdfDocument, onHighlight, pdfPage, fileName }: Props) => {
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

  const onTabChange = (value: string) => {
    const tab = sidebarTabFromQuery(value === 'extraction' ? null : value);
    router.replace(docPageHrefWithSearch(pathname, tab, searchParams));
  };

  const tabContentClass =
    'min-h-0 flex-1 overflow-hidden overscroll-y-contain px-3 pb-3 pt-2';

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col border-l border-border bg-card">
      <PDFFormsTabProbe
        organizationId={organizationId}
        documentId={id}
        onHasForms={handleFormsHasForms}
      />
      {!showFlowsTab ? (
        <div className="sr-only" aria-hidden>
          <PDFFlowsSidebar
            organizationId={organizationId}
            id={id}
            panelActive={false}
            onHasFlows={handleFlowsHasFlows}
          />
        </div>
      ) : null}

      <Card className="flex h-full min-h-0 flex-col gap-0 rounded-none border-0 py-0 shadow-none">
        <Tabs
          value={activeMode}
          onValueChange={onTabChange}
          className="flex h-full min-h-0 flex-1 flex-col gap-0"
        >
          <div className="shrink-0 border-b px-2 pt-2">
            <TabsList
              variant="line"
              aria-label="Document panel"
              className="h-9 w-full max-w-full justify-start gap-0 overflow-x-auto overflow-y-hidden [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              <TabsTrigger value="extraction">{TAB_LABELS.extraction}</TabsTrigger>
              {showFlowsTab ? <TabsTrigger value="flows">{TAB_LABELS.flows}</TabsTrigger> : null}
              {showFormsTab ? <TabsTrigger value="forms">{TAB_LABELS.forms}</TabsTrigger> : null}
              <TabsTrigger value="text">{TAB_LABELS.text}</TabsTrigger>
              <TabsTrigger value="info">{TAB_LABELS.info}</TabsTrigger>
              <TabsTrigger value="chat">{TAB_LABELS.chat}</TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="extraction" className={tabContentClass}>
            <PDFExtractionSidebar
              organizationId={organizationId}
              id={id}
              pdfDocument={pdfDocument}
              onHighlight={onHighlight}
            />
          </TabsContent>

          {showFlowsTab ? (
            <TabsContent value="flows" className={tabContentClass}>
              <PDFFlowsSidebar
                organizationId={organizationId}
                id={id}
                panelActive={activeMode === 'flows'}
                onHasFlows={handleFlowsHasFlows}
              />
            </TabsContent>
          ) : null}

          {showFormsTab ? (
            <TabsContent value="forms" className={tabContentClass}>
              <PDFFormSidebar
                organizationId={organizationId}
                id={id}
                pdfDocument={pdfDocument}
                onHighlight={onHighlight}
                onHasForms={handleFormsHasForms}
              />
            </TabsContent>
          ) : null}

          <TabsContent value="text" className={tabContentClass}>
            <PDFTextPanel
              organizationId={organizationId}
              documentId={id}
              page={pdfPage}
              fileName={fileName}
            />
          </TabsContent>

          <TabsContent value="info" className={cnInfoTabContent(tabContentClass)}>
            <PDFInfoPanel organizationId={organizationId} documentId={id} />
          </TabsContent>

          <TabsContent value="chat" className={tabContentClass}>
            <div className="flex h-full min-h-0 flex-col">
              <AgentTab organizationId={organizationId} documentId={id} />
            </div>
          </TabsContent>
        </Tabs>
      </Card>
    </div>
  );
};

function cnInfoTabContent(base: string) {
  return `${base} overflow-y-auto overscroll-y-contain`;
}

export default PDFSidebar;
