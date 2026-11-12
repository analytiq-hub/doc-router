'use client';

import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { DocRouterOrgApi } from '@/utils/api';
import { Button } from '@/components/ui/button';
import { isOCRSupported } from '@/utils/ocr-utils';

type PDFTextPanelProps = {
  organizationId: string;
  documentId: string;
  /** Current PDF page (1-based), synced from the viewer. */
  page: number;
  fileName: string | null;
};

export default function PDFTextPanel({
  organizationId,
  documentId,
  page,
  fileName,
}: PDFTextPanelProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [ocrType, setOcrType] = useState<string | null>(null);
  const [nPages, setNPages] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!isOCRSupported(fileName)) {
      setText('');
      setError('OCR text is not available for this file type.');
      return;
    }
    setLoading(true);
    setError(null);
    const api = new DocRouterOrgApi(organizationId);
    try {
      const meta = await api.getOCRMetadata({ documentId });
      setOcrType(meta.ocr_type ?? null);
      const maxPages = meta.n_pages ?? null;
      setNPages(maxPages);
      const shownPage = Math.max(1, maxPages ? Math.min(page, maxPages) : page);
      const pageText = await api.getOCRText({ documentId, pageNum: shownPage });
      setText(pageText);
    } catch (err) {
      console.error('Failed to load OCR text:', err);
      setError('OCR text is not available yet. Run OCR from the PDF toolbar if needed.');
      setText('');
    } finally {
      setLoading(false);
    }
  }, [organizationId, documentId, fileName, page]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setText('');
    setError(null);
    setOcrType(null);
    setNPages(null);
  }, [documentId]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex shrink-0 items-center gap-2">
        <p className="text-xs text-muted-foreground">
          {ocrType ? `Engine: ${ocrType}` : 'Extracted text'}
          {nPages ? ` · page ${Math.min(page, nPages)} of ${nPages}` : page > 1 ? ` · page ${page}` : null}
        </p>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="ml-auto"
          aria-label="Refresh OCR text"
          onClick={() => void load()}
        >
          <RefreshCw className="size-4" aria-hidden />
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto rounded-md border bg-muted/30 p-2">
        {loading ? (
          <p className="text-sm italic text-muted-foreground">Loading OCR text…</p>
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : (
          <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-foreground">
            {text || 'No OCR text for this page.'}
          </pre>
        )}
      </div>
    </div>
  );
}
