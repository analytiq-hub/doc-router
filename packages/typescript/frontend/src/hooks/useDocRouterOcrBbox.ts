import { useCallback, useEffect, useState } from 'react';
import type { OCRBlock } from '@docrouter/sdk';
import { DocRouterOrgApi } from '@/utils/api';
import { isOCRSupported, isOcrNotReadyError } from '@/utils/ocr-utils';
import { toastActionError } from '@/utils/toastActionError';
import { toast } from 'sonner';

const DOCUMENT_ERROR_STATES = new Set(['ocr_failed', 'llm_failed']);

function isDocumentErrorState(state: string | null): boolean {
  return state != null && DOCUMENT_ERROR_STATES.has(state);
}

/** Load OCR blocks when bbox overlay is enabled (`?bbox` or toggle in a later phase). */
export function useDocRouterOcrBbox(
  organizationId: string,
  documentId: string,
  fileName: string,
  documentState: string | null,
  initialShowBoundingBoxes: boolean,
) {
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(initialShowBoundingBoxes);
  const [ocrBlocksForBoxes, setOcrBlocksForBoxes] = useState<OCRBlock[] | null>(null);

  useEffect(() => {
    setOcrBlocksForBoxes(null);
  }, [documentId]);

  useEffect(() => {
    if (initialShowBoundingBoxes) setShowBoundingBoxes(true);
  }, [initialShowBoundingBoxes]);

  useEffect(() => {
    if (!showBoundingBoxes || ocrBlocksForBoxes !== null || !isOCRSupported(fileName)) return;

    let cancelled = false;
    const api = new DocRouterOrgApi(organizationId);

    const tryLoadBlocks = async (): Promise<boolean> => {
      try {
        const blocks = await api.getOCRBlocks({ documentId });
        if (!cancelled) setOcrBlocksForBoxes(blocks);
        return true;
      } catch (err) {
        if (cancelled) return true;
        if (isOcrNotReadyError(err)) return false;
        console.error('Error loading OCR blocks:', err);
        toastActionError('Failed to load OCR bounding boxes', err);
        return true;
      }
    };

    const fetchDocumentState = async (): Promise<string | null> => {
      if (documentState != null) return documentState;
      try {
        const list = await api.listDocuments({ limit: 100, skip: 0 });
        const doc = list.documents.find((d) => d.id === documentId);
        return doc?.state ?? null;
      } catch {
        return null;
      }
    };

    let intervalId: ReturnType<typeof setInterval> | null = null;

    const poll = async () => {
      if (cancelled) return;
      const gotBlocks = await tryLoadBlocks();
      if (cancelled || gotBlocks) {
        if (intervalId) clearInterval(intervalId);
        return;
      }
      const state = await fetchDocumentState();
      if (cancelled) return;
      if (state && isDocumentErrorState(state)) {
        if (intervalId) clearInterval(intervalId);
        toast.info('OCR could not be completed for this document');
      }
    };

    void tryLoadBlocks().then((got) => {
      if (!cancelled && !got) intervalId = setInterval(() => void poll(), 1000);
    });

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [showBoundingBoxes, ocrBlocksForBoxes, fileName, documentId, organizationId, documentState]);

  const ensureBboxBlocks = useCallback(async () => {
    if (ocrBlocksForBoxes !== null || !isOCRSupported(fileName)) return;
    const api = new DocRouterOrgApi(organizationId);
    try {
      const blocks = await api.getOCRBlocks({ documentId });
      setOcrBlocksForBoxes(blocks);
    } catch (err) {
      if (isOcrNotReadyError(err)) {
        toast.info('OCR data not yet available');
      } else {
        console.error('Error loading OCR blocks:', err);
        toastActionError('Failed to load OCR bounding boxes', err);
      }
    }
  }, [ocrBlocksForBoxes, fileName, organizationId, documentId]);

  return {
    showBoundingBoxes,
    setShowBoundingBoxes,
    ocrBlocksForBoxes,
    ensureBboxBlocks,
  };
}
