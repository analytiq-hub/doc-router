import { saveAs } from 'file-saver';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { DocRouterOrgApi } from '@/utils/api';
import { isOCRSupported, isOcrNotReadyError } from '@/utils/ocr-utils';
import { toastActionError } from '@/utils/toastActionError';

export type OcrPanelKind = 'text' | 'markdown' | 'html' | 'excel';

export function useDocRouterOcrOutput(
  organizationId: string,
  documentId: string,
  fileName: string,
) {
  const api = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [ocrPanelKind, setOcrPanelKind] = useState<OcrPanelKind | null>(null);
  const [ocrMetadataType, setOcrMetadataType] = useState<string | null>(null);
  const [ocrText, setOcrText] = useState('');
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [ocrMarkdown, setOcrMarkdown] = useState('');
  const [ocrMarkdownLoading, setOcrMarkdownLoading] = useState(false);
  const [ocrMarkdownError, setOcrMarkdownError] = useState<string | null>(null);
  const [ocrHtml, setOcrHtml] = useState('');
  const [ocrHtmlLoading, setOcrHtmlLoading] = useState(false);
  const [ocrHtmlError, setOcrHtmlError] = useState<string | null>(null);

  const ocrDownloadBaseName = useMemo(
    () => (fileName || `Document_${documentId}`).replace(/\.[^/.]+$/, '') || `Document_${documentId}`,
    [fileName, documentId],
  );

  useEffect(() => {
    setOcrPanelKind(null);
    setOcrText('');
    setOcrError(null);
    setOcrMarkdown('');
    setOcrMarkdownError(null);
    setOcrHtml('');
    setOcrHtmlError(null);
  }, [documentId]);

  useEffect(() => {
    if (!ocrPanelKind) return;
    void api
      .getOCRMetadata({ documentId })
      .then((meta) => setOcrMetadataType(meta?.ocr_type ?? null))
      .catch(() => setOcrMetadataType(null));
  }, [ocrPanelKind, api, documentId]);

  useEffect(() => {
    if (!ocrPanelKind || !isOCRSupported(fileName)) {
      const msg = 'OCR is not supported for this file type';
      if (ocrPanelKind === 'text') {
        setOcrError(msg);
        setOcrLoading(false);
      }
      if (ocrPanelKind === 'markdown') {
        setOcrMarkdownError(msg);
        setOcrMarkdownLoading(false);
      }
      if (ocrPanelKind === 'html') {
        setOcrHtmlError(msg);
        setOcrHtmlLoading(false);
      }
      return;
    }

    if (ocrPanelKind === 'text') {
      let cancelled = false;
      void (async () => {
        try {
          setOcrLoading(true);
          setOcrError(null);
          const text = await api.getOCRText({ documentId });
          if (!cancelled) setOcrText(text);
        } catch (err) {
          if (!cancelled) {
            setOcrError(isOcrNotReadyError(err) ? 'OCR data not yet available' : 'Failed to load OCR text');
          }
        } finally {
          if (!cancelled) setOcrLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }

    if (ocrPanelKind === 'markdown') {
      let cancelled = false;
      void (async () => {
        try {
          setOcrMarkdownLoading(true);
          setOcrMarkdownError(null);
          const md = await api.getOCRExportMarkdown({ documentId });
          if (!cancelled) setOcrMarkdown(md);
        } catch (err) {
          if (!cancelled) {
            setOcrMarkdownError(isOcrNotReadyError(err) ? 'OCR data not yet available' : 'Failed to load markdown');
          }
        } finally {
          if (!cancelled) setOcrMarkdownLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }

    if (ocrPanelKind === 'html') {
      let cancelled = false;
      void (async () => {
        try {
          setOcrHtmlLoading(true);
          setOcrHtmlError(null);
          const html = await api.getOCRExportHtml({ documentId });
          if (!cancelled) setOcrHtml(html);
        } catch (err) {
          if (!cancelled) {
            setOcrHtmlError(isOcrNotReadyError(err) ? 'OCR data not yet available' : 'Failed to load HTML');
          }
        } finally {
          if (!cancelled) setOcrHtmlLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }
    return undefined;
  }, [ocrPanelKind, fileName, api, documentId]);

  const openOcrOutput = useCallback(() => {
    setOcrPanelKind((prev) => prev ?? 'text');
  }, []);

  const downloadOcrJson = useCallback(async () => {
    if (!isOCRSupported(fileName)) {
      toast.error('OCR is not supported for this file type');
      return;
    }
    try {
      const payload = await api.getOCRStoredPayload({ documentId });
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      saveAs(blob, `${fileName || `Document_${documentId}`}_ocr.json`);
    } catch (err) {
      if (isOcrNotReadyError(err)) toast.info('OCR data not yet available');
      else toastActionError('Failed to download OCR JSON', err);
    }
  }, [api, documentId, fileName]);

  const downloadPanelExport = useCallback(async () => {
    if (!ocrPanelKind) return;
    if (!isOCRSupported(fileName)) {
      toast.error('OCR is not supported for this file type');
      return;
    }
    try {
      if (ocrPanelKind === 'text') {
        const text = ocrText || (await api.getOCRText({ documentId }));
        saveAs(new Blob([text], { type: 'text/plain;charset=utf-8' }), `${ocrDownloadBaseName}_ocr.txt`);
      } else if (ocrPanelKind === 'markdown') {
        const md = ocrMarkdown || (await api.getOCRExportMarkdown({ documentId }));
        saveAs(new Blob([md], { type: 'text/markdown;charset=utf-8' }), `${ocrDownloadBaseName}_ocr.md`);
      } else if (ocrPanelKind === 'html') {
        const html = ocrHtml || (await api.getOCRExportHtml({ documentId }));
        saveAs(new Blob([html], { type: 'text/html;charset=utf-8' }), `${ocrDownloadBaseName}_ocr.html`);
      } else {
        const blob = await api.getOCRExportTablesXlsx({ documentId });
        saveAs(blob, `${ocrDownloadBaseName}_ocr_tables.xlsx`);
      }
    } catch (err) {
      if (isOcrNotReadyError(err)) toast.info('OCR data not yet available');
      else if (ocrPanelKind === 'excel' && (err as Error & { status?: number })?.status === 404) {
        toast.warning(
          'Excel tables are not available for this document. Enable Textract TABLES and re-run OCR.',
        );
      } else toastActionError('Failed to download OCR export', err);
    }
  }, [
    ocrPanelKind,
    fileName,
    ocrText,
    ocrMarkdown,
    ocrHtml,
    api,
    documentId,
    ocrDownloadBaseName,
  ]);

  return {
    ocrPanelKind,
    setOcrPanelKind,
    ocrMetadataType,
    openOcrOutput,
    downloadOcrJson,
    downloadPanelExport,
    ocrText,
    ocrLoading,
    ocrError,
    ocrMarkdown,
    ocrMarkdownLoading,
    ocrMarkdownError,
    ocrHtml,
    ocrHtmlLoading,
    ocrHtmlError,
  };
}
