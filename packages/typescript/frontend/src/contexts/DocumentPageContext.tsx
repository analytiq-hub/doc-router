'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';

export interface DocumentPageData {
  /** PDF file content; null until loaded or if failed. */
  pdfContent: ArrayBuffer | null;
  documentName: string | null;
  documentState: string | null;
  loading: boolean;
  error: string | null;
  /** Re-fetch document (e.g. after processing). */
  refresh: () => Promise<void>;
}

const DocumentPageContext = createContext<DocumentPageData | null>(null);

export function useDocumentPage(): DocumentPageData | null {
  return useContext(DocumentPageContext);
}

interface DocumentPageProviderProps {
  organizationId: string;
  documentId: string;
  children: React.ReactNode;
}

/**
 * Fetches the document (PDF + state + name) once and shares across PDFViewer, AgentTab, and sidebars
 * to avoid duplicate GET /documents/:id?file_type=pdf and related calls.
 */
export function DocumentPageProvider({ organizationId, documentId, children }: DocumentPageProviderProps) {
  const [pdfContent, setPdfContent] = useState<ArrayBuffer | null>(null);
  const [documentName, setDocumentName] = useState<string | null>(null);
  const [documentState, setDocumentState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const api = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);

  const fetchDocument = useCallback(async () => {
    try {
      setError(null);
      const response = await api.getDocument({ documentId, fileType: 'pdf' });
      setPdfContent(response.content);
      setDocumentName(response.document_name ?? null);
      setDocumentState(response.state ?? null);
    } catch (e) {
      try {
        const fallback = await api.getDocument({ documentId, fileType: 'original' });
        setPdfContent(null);
        setDocumentName(fallback.document_name ?? null);
        setDocumentState(fallback.state ?? null);
      } catch {
        setError(e instanceof Error ? e.message : 'Failed to load document');
        setDocumentState(null);
        setDocumentName(null);
        setPdfContent(null);
      }
    } finally {
      setLoading(false);
    }
  }, [documentId, api]);

  useEffect(() => {
    setLoading(true);
    fetchDocument();
  }, [fetchDocument]);

  // Poll state while processing so chat/sidebar see completion without each polling separately
  useEffect(() => {
    if (documentState !== 'ocr_processing' && documentState !== 'llm_processing') {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const response = await api.getDocument({ documentId, fileType: 'pdf' });
        setDocumentState(response.state ?? null);
        if (response.state === 'llm_completed' || response.state === 'ocr_completed') {
          setPdfContent(response.content);
          setDocumentName(response.document_name ?? null);
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      } catch {
        // keep polling on error
      }
    }, 2000);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [documentState, documentId, api]);

  const refresh = useCallback(async () => {
    setLoading(true);
    await fetchDocument();
  }, [fetchDocument]);

  const value: DocumentPageData = {
    pdfContent,
    documentName,
    documentState,
    loading,
    error,
    refresh,
  };

  return (
    <DocumentPageContext.Provider value={value}>
      {children}
    </DocumentPageContext.Provider>
  );
}
