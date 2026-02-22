'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';

export interface DocumentPageData {
  /** PDF file content; null until loaded or if failed. */
  pdfContent: ArrayBuffer | null;
  /** Stable wrapper around pdfContent for passing directly to react-pdf <Document file={...}>.
   *  Object reference only changes when the ArrayBuffer identity changes, preventing unnecessary reloads. */
  pdfFile: { data: ArrayBuffer } | null;
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
  const [pdfFile, setPdfFile] = useState<{ data: ArrayBuffer } | null>(null);
  const [documentName, setDocumentName] = useState<string | null>(null);
  const [documentState, setDocumentState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const completionFetchStartedRef = useRef(false);
  const api = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);

  /** Set both pdfContent and the stable pdfFile wrapper together. */
  const setContent = useCallback((content: ArrayBuffer | null) => {
    setPdfContent(content);
    setPdfFile(prev =>
      prev?.data === content ? prev : content ? { data: content } : null
    );
  }, []);

  const fetchDocument = useCallback(async () => {
    try {
      setError(null);
      const response = await api.getDocument({ documentId, fileType: 'pdf' });
      setContent(response.content ?? null);
      setDocumentName(response.document_name ?? null);
      setDocumentState(response.state ?? null);
    } catch (e) {
      try {
        const fallback = await api.getDocument({ documentId, fileType: 'original' });
        setContent(null);
        setDocumentName(fallback.document_name ?? null);
        setDocumentState(fallback.state ?? null);
      } catch {
        setError(e instanceof Error ? e.message : 'Failed to load document');
        setDocumentState(null);
        setDocumentName(null);
        setContent(null);
      }
    } finally {
      setLoading(false);
    }
  }, [documentId, api, setContent]);

  useEffect(() => {
    setLoading(true);
    fetchDocument();
  }, [fetchDocument]);

  // Poll state via GET document with include_content=false (no PDF binary). When completed, fetch full document once.
  useEffect(() => {
    if (documentState !== 'ocr_processing' && documentState !== 'llm_processing') {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      completionFetchStartedRef.current = false;
      return;
    }
    completionFetchStartedRef.current = false;
    pollRef.current = setInterval(async () => {
      try {
        const meta = await api.getDocument({ documentId, fileType: 'pdf', includeContent: false });
        setDocumentState(meta.state ?? null);
        setDocumentName(meta.document_name ?? null);
        if (meta.state === 'llm_completed' || meta.state === 'ocr_completed') {
          if (completionFetchStartedRef.current) return;
          completionFetchStartedRef.current = true;
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          const response = await api.getDocument({ documentId, fileType: 'pdf' });
          setContent(response.content ?? null);
          setDocumentName(response.document_name ?? null);
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
      completionFetchStartedRef.current = false;
    };
  }, [documentState, documentId, api, setContent]);

  const refresh = useCallback(async () => {
    setLoading(true);
    await fetchDocument();
  }, [fetchDocument]);

  const value = useMemo<DocumentPageData>(
    () => ({
      pdfContent,
      pdfFile,
      documentName,
      documentState,
      loading,
      error,
      refresh,
    }),
    [pdfContent, pdfFile, documentName, documentState, loading, error, refresh]
  );

  return (
    <DocumentPageContext.Provider value={value}>
      {children}
    </DocumentPageContext.Provider>
  );
}
