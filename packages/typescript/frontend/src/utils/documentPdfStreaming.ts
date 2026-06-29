import { PDFDataRangeTransport } from 'pdfjs-dist';
import { getCachedSession } from '@/utils/api';
import type { DocRouterOrgApi } from '@/utils/api';

// Matches backend GridFS chunk size (packages/python/analytiq_data/mongodb/blob.py).
export const PDF_RANGE_CHUNK_BYTES = 8 * 1024 * 1024;

export const pdfDocumentLoadOptions = {
  disableAutoFetch: true,
  disableStream: true,
  rangeChunkSize: PDF_RANGE_CHUNK_BYTES,
} as const;

// PDF bytes always load through the same-origin /fastapi proxy (Next rewrite or nginx),
// not PUBLIC_API_URL / :8000.
const PDF_API_PREFIX = '/fastapi';

function sameOriginPdfFileUrl(organizationId: string, documentId: string): string {
  const query = new URLSearchParams({ file_type: 'pdf' });
  return `${window.location.origin}${PDF_API_PREFIX}/v0/orgs/${organizationId}/documents/${documentId}/file?${query}`;
}

/**
 * pdf.js URL loading probes with a full GET and only enables ranges when response
 * headers include Accept-Ranges + Content-Length (invisible cross-origin without CORS).
 * This transport issues explicit Range requests so the viewer never downloads the whole file.
 */
class AuthenticatedPdfRangeTransport extends PDFDataRangeTransport {
  private readonly inflight = new Map<string, AbortController>();

  constructor(
    length: number,
    private readonly url: string,
    private readonly authToken: string,
  ) {
    super(length, new Uint8Array(0));
  }

  requestDataRange(begin: number, end: number): void {
    const inclusiveEnd = end - 1;
    const key = `${begin}-${inclusiveEnd}`;
    const controller = new AbortController();
    this.inflight.set(key, controller);

    void fetch(this.url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${this.authToken}`,
        Range: `bytes=${begin}-${inclusiveEnd}`,
      },
      signal: controller.signal,
      credentials: 'same-origin',
    })
      .then(async (response) => {
        if (response.status !== 206 && response.status !== 200) {
          throw new Error(`PDF range fetch failed (${response.status})`);
        }
        const buffer = await response.arrayBuffer();
        this.onDataRange(begin, new Uint8Array(buffer));
      })
      .catch((error: unknown) => {
        if (error instanceof Error && error.name === 'AbortError') {
          return;
        }
        console.error('PDF range fetch error:', error);
      })
      .finally(() => {
        this.inflight.delete(key);
      });
  }

  abort(): void {
    for (const controller of this.inflight.values()) {
      controller.abort();
    }
    this.inflight.clear();
  }
}

export type StreamingPdfFile = AuthenticatedPdfRangeTransport;

export async function buildStreamingPdfFile(
  api: DocRouterOrgApi,
  documentId: string,
  fileSize?: number | null,
): Promise<StreamingPdfFile | null> {
  const token = (await getCachedSession())?.apiAccessToken;
  if (!token) {
    return null;
  }

  let length = fileSize ?? 0;
  if (length <= 0) {
    const meta = await api.getDocument({
      documentId,
      fileType: 'pdf',
      includeContent: false,
    });
    length = meta.file_size ?? 0;
  }
  if (length <= 0) {
    throw new Error('PDF file size is unknown');
  }

  return new AuthenticatedPdfRangeTransport(
    length,
    sameOriginPdfFileUrl(api.organizationId, documentId),
    token,
  );
}
