import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import {
  fetchDocumentPdfFile,
  isAbortedDocumentPdfFileError,
} from '@/utils/documentPdfFileCache';

const PROCESSING_STATES = new Set(['ocr_processing', 'llm_processing']);
const COMPLETED_STATES = new Set(['llm_completed', 'ocr_completed']);

export type UseDocRouterPdfDocumentResult = {
  loading: boolean;
  fetchError: string | null;
  fileUrl: string | null;
  documentState: string | null;
  setDocumentState: Dispatch<SetStateAction<string | null>>;
  fileName: string;
  fileSize: number;
};

/**
 * Blob URL lifecycle + metadata poll for document PDF viewing (extracted from legacy PDFViewer).
 */
export function useDocRouterPdfDocument(
  organizationId: string,
  documentId: string,
): UseDocRouterPdfDocumentResult {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);

  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [documentState, setDocumentState] = useState<string | null>(null);
  const [fileName, setFileName] = useState('');
  const [fileSize, setFileSize] = useState(0);

  const fileUrlRef = useRef<string | null>(null);
  const loadedIdRef = useRef<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const completionFetchStartedRef = useRef(false);

  const revokeCurrentUrl = useCallback(() => {
    if (fileUrlRef.current) {
      URL.revokeObjectURL(fileUrlRef.current);
      fileUrlRef.current = null;
    }
  }, []);

  const setUrlFromBlob = useCallback(
    (blob: Blob | null, name: string | null, state: string | null) => {
      revokeCurrentUrl();
      if (!blob) {
        setFileUrl(null);
        setDocumentState(state);
        return;
      }
      const url = URL.createObjectURL(blob);
      fileUrlRef.current = url;
      setFileUrl(url);
      setDocumentState(state);
    },
    [revokeCurrentUrl],
  );

  useEffect(() => {
    const loadDocumentId = documentId;

    if (loadedIdRef.current === loadDocumentId && fileUrlRef.current) {
      setLoading(false);
      return;
    }

    if (loadedIdRef.current !== null && loadedIdRef.current !== loadDocumentId) {
      revokeCurrentUrl();
    }

    loadedIdRef.current = loadDocumentId;
    setFetchError(null);
    if (!fileUrlRef.current) {
      setLoading(true);
      setFileUrl(null);
    }

    let cancelled = false;

    const applyPdfBuffer = (buffer: ArrayBuffer, name: string | null, state: string | null) => {
      const blob = new Blob([buffer], { type: 'application/pdf' });
      setUrlFromBlob(blob, name, state);
      setFileName(name ?? '');
      setFileSize(blob.size);
      setLoading(false);
    };

    const load = async () => {
      try {
        const meta = await docRouterOrgApi.getDocument({
          documentId: loadDocumentId,
          fileType: 'pdf',
          includeContent: false,
        });
        if (cancelled) return;
        const state = meta.state ?? null;
        const name = meta.document_name ?? null;
        setDocumentState(state);
        const stillProcessing = PROCESSING_STATES.has(state ?? '');
        try {
          const buffer = await fetchDocumentPdfFile(docRouterOrgApi, organizationId, loadDocumentId);
          if (cancelled) return;
          applyPdfBuffer(buffer, name, state);
        } catch (fileErr) {
          if (isAbortedDocumentPdfFileError(fileErr)) return;
          if (!stillProcessing) {
            throw fileErr;
          }
          if (!cancelled) {
            setLoading(false);
          }
        }
      } catch (e) {
        if (cancelled || isAbortedDocumentPdfFileError(e)) return;
        setFetchError(e instanceof Error ? e.message : 'Failed to load document');
        setDocumentState(null);
        setFileUrl(null);
        setFileName('');
        setFileSize(0);
        setLoading(false);
      }
    };

    void load();

    return () => {
      cancelled = true;
      if (loadedIdRef.current !== loadDocumentId) {
        revokeCurrentUrl();
        setFileUrl(null);
      }
    };
  }, [documentId, organizationId, docRouterOrgApi, revokeCurrentUrl, setUrlFromBlob]);

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
    pollRef.current = setInterval(() => {
      void (async () => {
        try {
          const meta = await docRouterOrgApi.getDocument({
            documentId,
            fileType: 'pdf',
            includeContent: false,
          });
          setDocumentState(meta.state ?? null);
          if (meta.state && COMPLETED_STATES.has(meta.state)) {
            if (completionFetchStartedRef.current) return;
            completionFetchStartedRef.current = true;
            if (pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
            setDocumentState(meta.state ?? null);
            if (fileUrlRef.current == null) {
              const buffer = await fetchDocumentPdfFile(docRouterOrgApi, organizationId, documentId);
              const blob = new Blob([buffer], { type: 'application/pdf' });
              setUrlFromBlob(blob, meta.document_name ?? null, meta.state ?? null);
              setFileName(meta.document_name ?? '');
              setFileSize(blob.size);
              setLoading(false);
            }
          }
        } catch {
          // keep polling on error
        }
      })();
    }, 2000);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      completionFetchStartedRef.current = false;
    };
  }, [documentState, documentId, organizationId, docRouterOrgApi, setUrlFromBlob]);

  return {
    loading,
    fetchError,
    fileUrl,
    documentState,
    setDocumentState,
    fileName,
    fileSize,
  };
}
