import { isAxiosError } from 'axios';
import type { DocRouterOrgApi } from '@/utils/api';

// Full-file downloads (save/print/view) can exceed the default 60s API timeout on large PDFs.
export const DOCUMENT_PDF_FILE_TIMEOUT_MS = 180_000;

const inFlightLoads = new Map<string, Promise<ArrayBuffer>>();

function cacheKey(organizationId: string, documentId: string): string {
  return `${organizationId}:${documentId}`;
}

export function isAbortedDocumentPdfFileError(error: unknown): boolean {
  return isAxiosError(error) && error.code === 'ECONNABORTED';
}

// One in-flight GET /file per org+document. Remounts share the same download instead of aborting a duplicate.
export function fetchDocumentPdfFile(
  api: DocRouterOrgApi,
  organizationId: string,
  documentId: string,
): Promise<ArrayBuffer> {
  const key = cacheKey(organizationId, documentId);
  const existing = inFlightLoads.get(key);
  if (existing) {
    return existing;
  }

  const promise = api
    .getDocumentFile({
      documentId,
      fileType: 'pdf',
      timeout: DOCUMENT_PDF_FILE_TIMEOUT_MS,
    })
    .finally(() => {
      inFlightLoads.delete(key);
    });

  inFlightLoads.set(key, promise);
  return promise;
}
