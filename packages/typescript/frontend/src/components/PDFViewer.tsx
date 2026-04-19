// components/PDFViewer.js
"use client"

import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import { pdfjs, Document, Page } from 'react-pdf';
import 'react-pdf/dist/esm/Page/TextLayer.css';
import { DocRouterOrgApi } from '@/utils/api';
import {
  getTextractNormalizedBox,
  isOCRSupported,
  isOcrNotReadyError,
  ocrBlockPageNum,
} from '@/utils/ocr-utils';
import { formatLocalDate } from '@/utils/date';
import { searchPdf, isPdfDocumentDetachedError, type PdfSearchHit } from '@/utils/pdfTextSearch';

/** Document states that indicate an error; stop polling for OCR/bounding boxes when these are set. */
const DOCUMENT_ERROR_STATES = ['ocr_failed', 'llm_failed'] as const;
function isDocumentErrorState(state: string | null): boolean {
  return state != null && (DOCUMENT_ERROR_STATES as readonly string[]).includes(state);
}
import { toast } from 'react-toastify';
import { BoltIcon } from '@heroicons/react/24/outline';
import { Toolbar, Typography, IconButton, TextField, Menu, MenuItem, Divider, Dialog, DialogTitle, DialogContent, DialogActions, Button, List, Tooltip, Tabs, Tab, Box, Paper } from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import RotateLeftIcon from '@mui/icons-material/RotateLeft';
import RotateRightIcon from '@mui/icons-material/RotateRight';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import VerticalAlignTopIcon from '@mui/icons-material/VerticalAlignTop';
import VerticalAlignBottomIcon from '@mui/icons-material/VerticalAlignBottom';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import FitScreenIcon from '@mui/icons-material/FitScreen';
import UnfoldMoreIcon from '@mui/icons-material/UnfoldMore';
import { styled } from '@mui/material/styles';
import { alpha } from '@mui/material/styles';
import PrintIcon from '@mui/icons-material/Print';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import DownloadIcon from '@mui/icons-material/Download';
import ArticleIcon from '@mui/icons-material/Article';
import { saveAs } from 'file-saver';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PanelGroup, Panel } from 'react-resizable-panels';
import CheckIcon from '@mui/icons-material/Check';
import SearchIcon from '@mui/icons-material/Search';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import CloseIcon from '@mui/icons-material/Close';
import CropFreeIcon from '@mui/icons-material/CropFree';
import type { OCRBlock } from '@docrouter/sdk';
import type { HighlightInfo } from '@/types/index';
import DraggablePanel from '@/components/DraggablePanel';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const StyledMenuItem = styled(MenuItem)(({ theme }) => ({
  fontSize: '0.875rem',
  padding: '4px 16px',
  '& .MuiListItemIcon-root': {
    minWidth: '32px',
  },
  '& .MuiSvgIcon-root': {
    color: alpha(theme.palette.text.primary, 0.6), // This makes the icons slightly grayer
  },
}));

// Add this styled component
const StyledListItem = styled('li')(({ theme }) => ({
  display: 'flex',
  justifyContent: 'space-between',
  padding: theme.spacing(1, 0),
  borderBottom: `1px solid ${theme.palette.divider}`,
  '&:last-child': {
    borderBottom: 'none',
  },
  '& .property-key': {
    fontWeight: 'bold',
    marginRight: theme.spacing(2),
  },
  '& .property-value': {
    textAlign: 'right',
    wordBreak: 'break-word',
    maxWidth: '60%',
  },
}));

// Add this interface near the top of your file, before the PDFViewer component
interface PDFMetadata {
  Title?: string;
  Author?: string;
  Subject?: string;
  Keywords?: string;
  CreationDate?: string;
  ModDate?: string;
  Creator?: string;
  Producer?: string;
  PDFFormatVersion?: string;
}

type OcrPanelKind = 'text' | 'markdown' | 'html' | 'excel';

// Update the props interface
interface PDFViewerProps {
  organizationId: string;
  id: string;
  highlightInfo?: HighlightInfo;
  /** When true (e.g. from ?bbox), bounding boxes are shown and OCR blocks are loaded on mount. */
  initialShowBoundingBoxes?: boolean;
  /** Fired when the PDF document is loaded (extraction search can use PDF.js text when OCR is missing). */
  onPdfDocumentReady?: (pdf: PDFDocumentProxy) => void;
}

const PDFViewer = ({ organizationId, id, highlightInfo, initialShowBoundingBoxes, onPdfDocumentReady }: PDFViewerProps) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [pdfDimensions, setPdfDimensions] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // PDF fetch state: we pass a blob URL (string) to react-pdf so the file prop is stable. One URL per load.
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [documentState, setDocumentState] = useState<string | null>(null);
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

  const setUrlFromBlob = useCallback((blob: Blob | null, name: string | null, state: string | null) => {
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
  }, [revokeCurrentUrl]);

  // Single load: fetch PDF once per document id; create blob URL and pass to Document. Cleanup revokes URL.
  useEffect(() => {
    if (loadedIdRef.current === id && fileUrlRef.current) {
      return;
    }
    revokeCurrentUrl();
    loadedIdRef.current = id;
    setLoading(true);
    setFetchError(null);
    setFileUrl(null);
    let cancelled = false;

    const load = async () => {
      try {
        const response = await docRouterOrgApi.getDocument({ documentId: id, fileType: 'pdf' });
        if (cancelled) return;
        const content = response.content ?? null;
        const name = response.document_name ?? null;
        const state = response.state ?? null;
        setDocumentState(state);
        const hasContent = content != null;
        const stillProcessing = ['ocr_processing', 'llm_processing'].includes(state ?? '');
        if (hasContent) {
          const blob = new Blob([content], { type: 'application/pdf' });
          setUrlFromBlob(blob, name, state);
          setFileName(name ?? '');
          setFileSize(blob.size);
        } else {
          setFileUrl(null);
        }
        if (hasContent || !stillProcessing) {
          setLoading(false);
        }
      } catch (e) {
        if (cancelled) return;
        setFetchError(e instanceof Error ? e.message : 'Failed to load document');
        setDocumentState(null);
        setFileUrl(null);
        setFileName('');
        setFileSize(0);
        setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
      revokeCurrentUrl();
      setFileUrl(null);
    };
  }, [id, docRouterOrgApi, revokeCurrentUrl, setUrlFromBlob]);

  // Poll metadata when processing. When completed and we still have no URL, do one full fetch and set blob URL.
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
        const meta = await docRouterOrgApi.getDocument({ documentId: id, fileType: 'pdf', includeContent: false });
        setDocumentState(meta.state ?? null);
        if (meta.state === 'llm_completed' || meta.state === 'ocr_completed') {
          if (completionFetchStartedRef.current) return;
          completionFetchStartedRef.current = true;
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          setDocumentState(meta.state ?? null);
          if (fileUrlRef.current == null) {
            const response = await docRouterOrgApi.getDocument({ documentId: id, fileType: 'pdf' });
            const content = response.content ?? null;
            if (content) {
              const blob = new Blob([content], { type: 'application/pdf' });
              setUrlFromBlob(blob, response.document_name ?? null, response.state ?? null);
              setFileName(response.document_name ?? '');
              setFileSize(blob.size);
            }
            setLoading(false);
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
      completionFetchStartedRef.current = false;
    };
  }, [documentState, id, docRouterOrgApi, setUrlFromBlob]);

  // Fetch errors vs react-pdf parse/display errors
  const [pdfLoadError, setPdfLoadError] = useState<string | null>(null);
  const error = fetchError ?? pdfLoadError;

  const pageRefs = useRef<(HTMLDivElement | null)[]>([]);
  const pdfDocRef = useRef<pdfjs.PDFDocumentProxy | null>(null);

  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [searchHits, setSearchHits] = useState<PdfSearchHit[]>([]);
  const [activeMatchIndex, setActiveMatchIndex] = useState(0);
  const [searchBusy, setSearchBusy] = useState(false);
  const [findBarOpen, setFindBarOpen] = useState(false);
  const findInputRef = useRef<HTMLInputElement | null>(null);
  /** Bumps on each successful `Document` load so search re-runs even when `numPages` is unchanged. */
  const [pdfLoadVersion, setPdfLoadVersion] = useState(0);

  const [fileName, setFileName] = useState<string>('');
  const [fileSize, setFileSize] = useState<number>(0);

  const scrollToPage = useCallback((pageNum: number, behavior: ScrollBehavior = 'smooth') => {
    
    if (pageRefs.current[pageNum - 1]) {
      pageRefs.current[pageNum - 1]?.scrollIntoView({ behavior });
      setPageNumber(pageNum);
      setInputPageNumber(pageNum.toString());
    }
  }, []);

  const [showProperties, setShowProperties] = useState(false);
  const [documentProperties, setDocumentProperties] = useState<Record<string, string> | null>(null);

  const [ocrPanelKind, setOcrPanelKind] = useState<OcrPanelKind | null>(null);
  const [ocrText, setOcrText] = useState<string>('');
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [ocrMarkdown, setOcrMarkdown] = useState<string>('');
  const [ocrMarkdownLoading, setOcrMarkdownLoading] = useState(false);
  const [ocrMarkdownError, setOcrMarkdownError] = useState<string | null>(null);
  const [ocrHtml, setOcrHtml] = useState<string>('');
  const [ocrHtmlLoading, setOcrHtmlLoading] = useState(false);
  const [ocrHtmlError, setOcrHtmlError] = useState<string | null>(null);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(!!initialShowBoundingBoxes);
  const [ocrBlocksForBoxes, setOcrBlocksForBoxes] = useState<OCRBlock[] | null>(null);
  const [fitMode, setFitMode] = useState<'width' | 'page' | 'manual'>('width');

  useEffect(() => {
    setOcrPanelKind(null);
    setOcrText('');
    setOcrError(null);
    setOcrMarkdown('');
    setOcrMarkdownError(null);
    setOcrHtml('');
    setOcrHtmlError(null);
  }, [id]);

  useEffect(() => {
    setSearchInput('');
    setDebouncedSearch('');
    setSearchHits([]);
    setActiveMatchIndex(0);
    setFindBarOpen(false);
    pdfDocRef.current = null;
    setPdfLoadVersion(0);
  }, [id]);

  /** Avoid using a stale PDFDocumentProxy after react-pdf swaps `file` (destroyed worker / null messageHandler). */
  useEffect(() => {
    pdfDocRef.current = null;
  }, [fileUrl]);

  const openFindBar = useCallback(() => {
    setFindBarOpen(true);
    queueMicrotask(() => findInputRef.current?.focus());
  }, []);

  const closeFindBar = useCallback(() => {
    setFindBarOpen(false);
    setSearchInput('');
    setDebouncedSearch('');
    setSearchHits([]);
    setActiveMatchIndex(0);
    setSearchBusy(false);
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const isFindShortcut =
        (e.ctrlKey || e.metaKey) && (e.key === 'f' || e.key === 'F' || e.code === 'KeyF');
      if (isFindShortcut) {
        if (!fileUrl || loading) return;
        e.preventDefault();
        e.stopPropagation();
        openFindBar();
        return;
      }
      if (e.key === 'Escape' && findBarOpen) {
        e.preventDefault();
        closeFindBar();
      }
    };
    // Capture phase: canvas / inner nodes may stop bubbling; we still see the shortcut first.
    document.addEventListener('keydown', onKeyDown, true);
    return () => document.removeEventListener('keydown', onKeyDown, true);
  }, [fileUrl, loading, findBarOpen, openFindBar, closeFindBar]);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchInput), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    const pdf = pdfDocRef.current;
    const q = debouncedSearch.trim();
    if (!pdf || !q) {
      setSearchHits([]);
      setActiveMatchIndex(0);
      setSearchBusy(false);
      return;
    }
    const ac = new AbortController();
    setSearchBusy(true);
    void searchPdf(pdf, q, false, ac.signal)
      .then((hits) => {
        if (!ac.signal.aborted) {
          setSearchHits(hits);
          setActiveMatchIndex(0);
        }
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === 'AbortError') return;
        if (isPdfDocumentDetachedError(e)) return;
        console.error(e);
      })
      .finally(() => {
        if (!ac.signal.aborted) setSearchBusy(false);
      });
    return () => ac.abort();
  }, [debouncedSearch, numPages, fileUrl, pdfLoadVersion]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const extractDocumentProperties = useCallback(async (pdf: pdfjs.PDFDocumentProxy) => {
    try {
      const metadata = await pdf.getMetadata();
      const info = metadata.info as PDFMetadata;
      const page = await pdf.getPage(1);

      const properties: Record<string, string> = {
        'File name': fileName,
        'File size': `${formatFileSize(fileSize)} (${fileSize.toLocaleString()} bytes)`,
        'Title': info.Title || 'N/A',
        'Author': info.Author || 'N/A',
        'Subject': info.Subject || 'N/A',
        'Keywords': info.Keywords || 'N/A',
        'Creation Date': info.CreationDate ? formatLocalDate(info.CreationDate) : 'N/A',
        'Modification Date': info.ModDate ? formatLocalDate(info.ModDate) : 'N/A',
        'Creator': info.Creator || 'N/A',
        'Producer': info.Producer || 'N/A',
        'Version': info.PDFFormatVersion || 'N/A',
        'Number of Pages': pdf.numPages.toString(),
        'Original Rotation': `${page.rotate}°`,
      };

      console.log('Extracted properties:', properties);
      setDocumentProperties(properties);
    } catch (err) {
      // Document may have been destroyed (e.g. file prop changed) before async call completed.
      if (err instanceof Error && (err.message?.includes('messageHandler') || err.message?.includes('sendWithPromise'))) {
        return;
      }
      console.error('Error extracting document properties:', err);
      setDocumentProperties({ 'Error': 'Failed to extract document properties' });
    }
  }, [fileName, fileSize]);

  const [originalRotation, setOriginalRotation] = useState(0);

  const handleLoadSuccess = (pdf: pdfjs.PDFDocumentProxy) => {
    pdfDocRef.current = pdf;
    onPdfDocumentReady?.(pdf);
    setPdfLoadVersion((v) => v + 1);
    setNumPages(pdf.numPages);
    setPageNumber(1);
    pageRefs.current = new Array(pdf.numPages).fill(null);
    void extractDocumentProperties(pdf).catch((err: unknown) => {
      // Guard against unexpected rejections not caught inside extractDocumentProperties
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('messageHandler') || msg.includes('sendWithPromise')) return;
      console.error('extractDocumentProperties failed unexpectedly:', err);
    });
    pdf.getPage(1).then((page) => {
      const viewport = page.getViewport({ scale: 1 });
      setPdfDimensions({ width: viewport.width, height: viewport.height });
      setOriginalRotation(page.rotate || 0);
    }).catch((err: unknown) => {
      // Document may have been destroyed (e.g. file prop changed) before getPage completed.
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('messageHandler') || msg.includes('sendWithPromise')) return;
      console.error('getPage(1) failed', err);
    });
  };

  const handleLoadError = (error: { message: string }) => {
    setPdfLoadError(error.message);
    console.error('PDF Load Error:', error);
  };

  const goToNextPage = () => {
    if (pageNumber < numPages!) {
      const newPageNumber = pageNumber + 1;
      setPageNumber(newPageNumber);
      setInputPageNumber(newPageNumber.toString());
    }
  };

  const goToPrevPage = () => {
    if (pageNumber > 1) {
      const newPageNumber = pageNumber - 1;
      setPageNumber(newPageNumber);
      setInputPageNumber(newPageNumber.toString());
    }
  };

  const zoomIn = () => {
    setScale(prevScale => Math.min(prevScale + 0.25, 3));
    setFitMode('manual');
  };
  const zoomOut = () => {
    setScale(prevScale => Math.max(prevScale - 0.25, 0.5));
    setFitMode('manual');
  };
  const rotateLeft = () => setRotation(prevRotation => (prevRotation - 90) % 360);
  const rotateRight = () => setRotation(prevRotation => (prevRotation + 90) % 360);

  const handleMenuClose = useCallback(() => {
    setAnchorEl(null);
  }, []);

  // Fit to page - scales to fit entire page in container
  const fitToPage = useCallback(() => {
    if (pdfDimensions.width && pdfDimensions.height && containerRef.current) {
      const containerElement = containerRef.current;
      const containerWidth = containerElement.clientWidth - 32;
      const containerHeight = containerElement.clientHeight - 32;

      let effectiveWidth = pdfDimensions.width;
      let effectiveHeight = pdfDimensions.height;
      
      if (Math.abs(rotation) === 90 || Math.abs(rotation) === 270) {
        effectiveWidth = pdfDimensions.height;
        effectiveHeight = pdfDimensions.width;
      }

      const widthScale = containerWidth / effectiveWidth;
      const heightScale = containerHeight / effectiveHeight;
      const optimalScale = Math.min(widthScale, heightScale) * 0.9;
      
      setScale(Math.max(optimalScale, 0.1));
      setFitMode('page');
    }
    handleMenuClose();
  }, [pdfDimensions, rotation, handleMenuClose]);

  // Fit to width - scales to fit page width in container
  const fitToWidth = useCallback(() => {
    if (pdfDimensions.width && pdfDimensions.height && containerRef.current) {
      const containerElement = containerRef.current;
      const containerWidth = containerElement.clientWidth - 32;

      let effectiveWidth = pdfDimensions.width;
      
      if (Math.abs(rotation) === 90 || Math.abs(rotation) === 270) {
        effectiveWidth = pdfDimensions.height;
      }

      const widthScale = containerWidth / effectiveWidth;
      const optimalScale = widthScale * 0.95;
      
      setScale(Math.max(optimalScale, 0.1));
      setFitMode('width');
    }
    handleMenuClose();
  }, [pdfDimensions, rotation, handleMenuClose]);

  // Auto-zoom based on current fit mode
  useEffect(() => {
    if (pdfDimensions.width && pdfDimensions.height && containerRef.current && fitMode !== 'manual') {
      const containerElement = containerRef.current;
      const containerWidth = containerElement.clientWidth - 32;
      const containerHeight = containerElement.clientHeight - 32;

      let effectiveWidth = pdfDimensions.width;
      let effectiveHeight = pdfDimensions.height;
      
      if (Math.abs(rotation) === 90 || Math.abs(rotation) === 270) {
        effectiveWidth = pdfDimensions.height;
        effectiveHeight = pdfDimensions.width;
      }

      let adjustedScale;
      if (fitMode === 'page') {
        // Fit to page - use smaller scale to fit both dimensions
        const widthScale = containerWidth / effectiveWidth;
        const heightScale = containerHeight / effectiveHeight;
        const optimalScale = Math.min(widthScale, heightScale) * 0.9;
        adjustedScale = Math.max(optimalScale, 0.1);
      } else {
        // Fit to width (default)
        const widthScale = containerWidth / effectiveWidth;
        const optimalScale = widthScale * 0.95;
        adjustedScale = Math.max(optimalScale, 0.1);
      }

      setScale(adjustedScale);
    }
  }, [pdfDimensions, rotation, fitMode]);

  // Add this useEffect after the existing scale calculation useEffect
  useEffect(() => {
    if (!containerRef.current || fitMode === 'manual') return;

    const resizeObserver = new ResizeObserver(() => {
        if (pdfDimensions.width && pdfDimensions.height) {
          const containerElement = containerRef.current;
          if (!containerElement) return;

          const containerWidth = containerElement.clientWidth - 32;
          const containerHeight = containerElement.clientHeight - 32;

          let effectiveWidth = pdfDimensions.width;
          let effectiveHeight = pdfDimensions.height;
          
          if (Math.abs(rotation) === 90 || Math.abs(rotation) === 270) {
            effectiveWidth = pdfDimensions.height;
            effectiveHeight = pdfDimensions.width;
          }

          let adjustedScale;
          if (fitMode === 'page') {
            const widthScale = containerWidth / effectiveWidth;
            const heightScale = containerHeight / effectiveHeight;
            const optimalScale = Math.min(widthScale, heightScale) * 0.9;
            adjustedScale = Math.max(optimalScale, 0.1);
          } else {
            const widthScale = containerWidth / effectiveWidth;
            const optimalScale = widthScale * 0.95;
            adjustedScale = Math.max(optimalScale, 0.1);
          }

          setScale(prev => Math.abs(prev - adjustedScale) < 0.001 ? prev : adjustedScale);
        }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, [pdfDimensions, rotation, fitMode]);

  const [inputPageNumber, setInputPageNumber] = useState('1');

  const handlePageNumberChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputPageNumber(event.target.value);
  };

  const handlePageNumberSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const newPageNumber = parseInt(inputPageNumber, 10);
    if (newPageNumber >= 1 && newPageNumber <= (numPages || 0)) {
      setPageNumber(newPageNumber);
    } else {
      // Reset input to current page number if invalid
      setInputPageNumber(pageNumber.toString());
    }
  };

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleDocumentProperties = useCallback(() => {
    setShowProperties(true);
    handleMenuClose();
  }, [handleMenuClose]);

  const printIframeRef = useRef<HTMLIFrameElement>(null);

  const handlePrint = () => {
    if (fileUrl) {
      const iframe = printIframeRef.current;
      if (!iframe) return;
      iframe.src = fileUrl;
      iframe.onload = () => {
        iframe.contentWindow?.print();
      };
    }
    handleMenuClose();
  };

  const handleSave = () => {
    if (fileUrl) {
      fetch(fileUrl)
        .then((response) => response.blob())
        .then((blob) => {
          const defaultFileName = fileName || `Document_${id}.pdf`;
          saveAs(blob, defaultFileName);
        })
        .catch((err) => console.error('Error saving the file:', err));
    }
    handleMenuClose();
  };

  const handleGoToFirstPage = () => {
    setPageNumber(1);
    handleMenuClose();
  };

  const handleGoToLastPage = () => {
    if (numPages) setPageNumber(numPages);
    handleMenuClose();
  };

  const openOcrOutput = useCallback(() => {
    setOcrPanelKind((prev) => prev ?? 'text');
    handleMenuClose();
  }, [handleMenuClose]);

  const handleRerunOCR = useCallback(async () => {
    handleMenuClose();
    try {
      await docRouterOrgApi.runOCR({ documentId: id });
      setOcrBlocksForBoxes(null);
      completionFetchStartedRef.current = false;
      setDocumentState('ocr_processing');
      toast.info('OCR requeued');
    } catch (err) {
      console.error('Error rerunning OCR:', err);
      toast.error('Failed to rerun OCR');
    }
  }, [handleMenuClose, docRouterOrgApi, id]);

  const handleBoundingBoxesToggle = useCallback(async () => {
    const next = !showBoundingBoxes;
    setShowBoundingBoxes(next);
    if (next && ocrBlocksForBoxes === null && isOCRSupported(fileName)) {
      try {
        const blocks = await docRouterOrgApi.getOCRBlocks({ documentId: id });
        setOcrBlocksForBoxes(blocks);
      } catch (err) {
        if (isOcrNotReadyError(err)) {
          toast.info('OCR data not yet available');
        } else {
          console.error('Error loading OCR blocks:', err);
          toast.error('Failed to load OCR bounding boxes');
        }
        // Leave null so user can retry by toggling off and on
      }
    }
    handleMenuClose();
  }, [showBoundingBoxes, ocrBlocksForBoxes, fileName, id, docRouterOrgApi, handleMenuClose]);

  // Sync URL ?bbox into menu state when user navigates with bbox param
  useEffect(() => {
    if (initialShowBoundingBoxes) {
      setShowBoundingBoxes(true);
    }
  }, [initialShowBoundingBoxes]);

  // When bounding boxes are on and we have a file name: load OCR blocks once, then poll every 1s until blocks
  // are available or document state is an error (ocr_failed, llm_failed).
  useEffect(() => {
    if (!showBoundingBoxes || ocrBlocksForBoxes !== null || !isOCRSupported(fileName)) return;

    let cancelled = false;

    const tryLoadBlocks = async (): Promise<boolean> => {
      try {
        const blocks = await docRouterOrgApi.getOCRBlocks({ documentId: id });
        if (!cancelled) setOcrBlocksForBoxes(blocks);
        return true;
      } catch (err) {
        if (cancelled) return true;
        if (isOcrNotReadyError(err)) {
          return false; // keep polling
        }
        console.error('Error loading OCR blocks:', err);
        toast.error('Failed to load OCR bounding boxes');
        return true; // stop polling on other errors
      }
    };

    const fetchDocumentState = async (): Promise<string | null> => {
      if (documentState != null) return documentState;
      try {
        const list = await docRouterOrgApi.listDocuments({ limit: 100, skip: 0 });
        const doc = list.documents.find((d) => d.id === id);
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
        return;
      }
    };

    // First attempt immediately (and show toast only once for "not yet available")
    tryLoadBlocks().then((gotBlocks) => {
      if (cancelled || gotBlocks) return;
    });

    intervalId = setInterval(poll, 1000);
    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [showBoundingBoxes, ocrBlocksForBoxes, fileName, id, docRouterOrgApi, documentState]);

  const ocrDownloadBaseName = useMemo(
    () => (fileName || `Document_${id}`).replace(/\.[^/.]+$/, '') || `Document_${id}`,
    [fileName, id],
  );

  const handleOcrPanelDownload = useCallback(async () => {
    if (!ocrPanelKind) return;
    if (!isOCRSupported(fileName)) {
      toast.error('OCR is not supported for this file type');
      return;
    }
    try {
      if (ocrPanelKind === 'text') {
        const text =
          ocrText || (await docRouterOrgApi.getOCRText({ documentId: id }));
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        saveAs(blob, `${ocrDownloadBaseName}_ocr.txt`);
      } else if (ocrPanelKind === 'markdown') {
        const md =
          ocrMarkdown ||
          (await docRouterOrgApi.getOCRExportMarkdown({ documentId: id }));
        const blob = new Blob([md], {
          type: 'text/markdown;charset=utf-8',
        });
        saveAs(blob, `${ocrDownloadBaseName}_ocr.md`);
      } else if (ocrPanelKind === 'html') {
        const html =
          ocrHtml ||
          (await docRouterOrgApi.getOCRExportHtml({ documentId: id }));
        const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
        saveAs(blob, `${ocrDownloadBaseName}_ocr.html`);
      } else {
        const blob = await docRouterOrgApi.getOCRExportTablesXlsx({
          documentId: id,
        });
        saveAs(blob, `${ocrDownloadBaseName}_ocr_tables.xlsx`);
      }
    } catch (err) {
      if (isOcrNotReadyError(err)) {
        toast.info('OCR data not yet available');
      } else if (
        ocrPanelKind === 'excel' &&
        (err as Error & { status?: number })?.status === 404
      ) {
        toast.warning(
          'Excel tables are not available for this document. Make sure the Textract TABLES feature is enabled, then re-run OCR.',
        );
      } else {
        console.error('OCR export download failed:', err);
        toast.error(
          err instanceof Error ? err.message : 'Failed to download OCR export',
        );
      }
    }
  }, [
    ocrPanelKind,
    fileName,
    ocrText,
    ocrMarkdown,
    ocrHtml,
    docRouterOrgApi,
    id,
    ocrDownloadBaseName,
  ]);

  const handleDownloadOcrJson = async () => {
    if (!isOCRSupported(fileName)) {
      toast.error('OCR is not supported for this file type');
      handleMenuClose();
      return;
    }
    try {
      const payload = await docRouterOrgApi.getOCRStoredPayload({ documentId: id });
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const defaultFileName = (fileName || `Document_${id}`) + `_ocr.json`;
      saveAs(blob, defaultFileName);
    } catch (err) {
      if (isOcrNotReadyError(err)) {
        toast.info('OCR data not yet available');
      } else {
        console.error('Error downloading OCR JSON:', err);
        toast.error('Failed to download OCR JSON');
      }
    }
    handleMenuClose();
  };

  useEffect(() => {
    if (!ocrPanelKind) return;

    if (!isOCRSupported(fileName)) {
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
      (async () => {
        try {
          setOcrLoading(true);
          setOcrError(null);
          const text = await docRouterOrgApi.getOCRText({ documentId: id });
          if (!cancelled) setOcrText(text);
        } catch (err) {
          if (!cancelled) {
            if (isOcrNotReadyError(err)) {
              setOcrError('OCR data not yet available');
            } else {
              console.error('Error fetching OCR text:', err);
              setOcrError('Failed to load OCR text');
            }
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
      (async () => {
        try {
          setOcrMarkdownLoading(true);
          setOcrMarkdownError(null);
          const md = await docRouterOrgApi.getOCRExportMarkdown({
            documentId: id,
          });
          if (!cancelled) setOcrMarkdown(md);
        } catch (err) {
          if (!cancelled) {
            if (isOcrNotReadyError(err)) {
              setOcrMarkdownError('OCR data not yet available');
            } else {
              console.error('Error fetching OCR markdown:', err);
              setOcrMarkdownError('Failed to load OCR markdown');
            }
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
      (async () => {
        try {
          setOcrHtmlLoading(true);
          setOcrHtmlError(null);
          const html = await docRouterOrgApi.getOCRExportHtml({ documentId: id });
          if (!cancelled) setOcrHtml(html);
        } catch (err) {
          if (!cancelled) {
            if (isOcrNotReadyError(err)) {
              setOcrHtmlError('OCR data not yet available');
            } else {
              console.error('Error fetching OCR HTML:', err);
              setOcrHtmlError('Failed to load OCR HTML');
            }
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
  }, [ocrPanelKind, id, docRouterOrgApi, fileName]);

  // This is called once for each page
  const renderHighlights = useCallback((page: number) => {
    const blocks = highlightInfo?.blocks ?? [];
    const pdfHits = highlightInfo?.pdfFallbackHits ?? [];
    if (!blocks.length && !pdfHits.length) return null;

    // Define padding as a percentage of the container
    const PADDING_PERCENT = 1.0; // 1.0% padding

    return (
      <div style={{ 
        position: 'absolute',
        width: '100%',
        height: '100%',
        top: 0,
        left: 0,
        pointerEvents: 'none',
      }}>
        {blocks.length > 0 &&
          blocks.map((block: OCRBlock, index: number) => {
            if (ocrBlockPageNum(block) !== page) return null;

            const box = getTextractNormalizedBox(block);
            if (!box) return null;
            const { Width, Height, Left, Top } = box;
            
            return (
              <div
                key={`ocr-${index}`}
                style={{
                  position: 'absolute',
                  left: `${(Left * 100) - PADDING_PERCENT}%`,
                  top: `${(Top * 100) - PADDING_PERCENT}%`,
                  width: `${(Width * 100) + (PADDING_PERCENT * 2)}%`,
                  height: `${(Height * 100) + (PADDING_PERCENT * 2)}%`,
                  backgroundColor: 'rgba(251, 192, 45, 0.4)',  // Soft amber
                  clipPath: `polygon(
                  0% 35%, 2% 30%, 0% 25%, 3% 20%,
                  3% 20%, 20% 15%, 40% 18%, 60% 15%, 80% 17%, 97% 20%,
                  97% 20%, 100% 25%, 98% 30%, 100% 35%,
                  100% 85%, 80% 90%, 60% 87%, 40% 90%, 20% 88%, 3% 85%,
                  0% 85%, 2% 80%, 0% 75%, 2% 70%, 0% 65%, 2% 45%, 0% 35%
                )`,
                  filter: 'blur(2px)',
                  pointerEvents: 'auto',
                  cursor: 'help',
                  zIndex: 1,
                }}
              />
            );
          })}
        {!blocks.length &&
          pdfHits.map((hit, idx) => {
            if (hit.page !== page) return null;
            return (
              <div
                key={`pdf-fallback-${idx}`}
                style={{
                  position: 'absolute',
                  left: `${hit.left * 100}%`,
                  top: `${hit.top * 100}%`,
                  width: `${hit.width * 100}%`,
                  height: `${hit.height * 100}%`,
                  backgroundColor: 'rgba(251, 192, 45, 0.4)',
                  pointerEvents: 'auto',
                  cursor: 'help',
                  zIndex: 1,
                }}
              />
            );
          })}
      </div>
    );
  }, [highlightInfo]);

  // Render OCR word bounding boxes overlay (when "Bounding Boxes" is on and OCR has completed)
  const renderBoundingBoxes = useCallback((page: number) => {
    if (!showBoundingBoxes || !ocrBlocksForBoxes?.length) return null;
    const onPage = (b: OCRBlock) => ocrBlockPageNum(b) === page;
    let drawBlocks = ocrBlocksForBoxes.filter((b) => b.BlockType === 'WORD' && onPage(b));
    if (drawBlocks.length === 0) {
      drawBlocks = ocrBlocksForBoxes.filter((b) => b.BlockType === 'LINE' && onPage(b));
    }
    const withBoxes = drawBlocks
      .map((block) => {
        const box = getTextractNormalizedBox(block);
        return box ? { block, box } : null;
      })
      .filter((x): x is { block: OCRBlock; box: NonNullable<ReturnType<typeof getTextractNormalizedBox>> } => x !== null);
    if (!withBoxes.length) return null;
    return (
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          right: 0,
          bottom: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          zIndex: 10,
        }}
      >
        {withBoxes.map(({ block, box }, index) => {
          const { Width, Height, Left, Top } = box;
          const wordText = block.Text ?? '';
          return (
            <Tooltip key={`${block.Id}-${index}`} title={wordText} arrow placement="top">
              <div
                style={{
                  position: 'absolute',
                  left: `${Left * 100}%`,
                  top: `${Top * 100}%`,
                  width: `${Width * 100}%`,
                  height: `${Height * 100}%`,
                  border: '1px solid rgba(33, 150, 243, 0.8)',
                  backgroundColor: 'rgba(33, 150, 243, 0.08)',
                  boxSizing: 'border-box',
                  pointerEvents: 'auto',
                  cursor: 'default',
                }}
              />
            </Tooltip>
          );
        })}
      </div>
    );
  }, [showBoundingBoxes, ocrBlocksForBoxes]);

  const goToActiveMatch = useCallback(
    (index: number) => {
      if (searchHits.length === 0) return;
      const i = Math.max(0, Math.min(index, searchHits.length - 1));
      setActiveMatchIndex(i);
      const hit = searchHits[i];
      setPageNumber(hit.page);
      setInputPageNumber(String(hit.page));
    },
    [searchHits],
  );

  const goToNextSearchMatch = useCallback(() => {
    if (searchHits.length === 0) return;
    const next = (activeMatchIndex + 1) % searchHits.length;
    goToActiveMatch(next);
  }, [searchHits, activeMatchIndex, goToActiveMatch]);

  const goToPrevSearchMatch = useCallback(() => {
    if (searchHits.length === 0) return;
    const prev = (activeMatchIndex - 1 + searchHits.length) % searchHits.length;
    goToActiveMatch(prev);
  }, [searchHits, activeMatchIndex, goToActiveMatch]);

  const renderSearchHighlights = useCallback(
    (page: number) => {
      if (searchHits.length === 0) return null;
      return (
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            right: 0,
            bottom: 0,
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
            zIndex: 11,
          }}
        >
          {searchHits.map((hit, globalIdx) => {
            if (hit.page !== page) return null;
            const isActive = globalIdx === activeMatchIndex;
            return (
              <div
                key={`search-hit-${globalIdx}`}
                style={{
                  position: 'absolute',
                  left: `${hit.left * 100}%`,
                  top: `${hit.top * 100}%`,
                  width: `${hit.width * 100}%`,
                  height: `${hit.height * 100}%`,
                  backgroundColor: isActive ? 'rgba(255, 180, 0, 0.45)' : 'rgba(255, 255, 100, 0.22)',
                  boxShadow: isActive ? '0 0 0 1px rgba(255, 140, 0, 0.85)' : 'none',
                  pointerEvents: 'none',
                }}
              />
            );
          })}
        </div>
      );
    },
    [searchHits, activeMatchIndex],
  );

  // Add this near the other state declarations
  const [lastSearch, setLastSearch] = useState<{
    promptId: string;
    key?: string;
    value: string;
    lastPage?: number;
  } | null>(null);

  // Update the useEffect for highlightInfo changes
  useEffect(() => {
    if (highlightInfo?.blocks.length || highlightInfo?.pdfFallbackHits?.length) {
      // Check if this is the same search as before
      const isSameSearch = !!(lastSearch && 
        lastSearch.promptId === highlightInfo.promptId && 
        lastSearch.key === highlightInfo.key && 
        lastSearch.value === highlightInfo.value);

      console.log('isSameSearch', isSameSearch);

      const nextPage = findNextHighlightedPage(pageNumber, isSameSearch);
      if (nextPage && nextPage !== pageNumber) {
        scrollToPage(nextPage);
        // Update lastSearch with the new page
        setLastSearch({
          promptId: highlightInfo.promptId,
          key: highlightInfo.key,
          value: highlightInfo.value,
          lastPage: nextPage
        });
      } else if (!isSameSearch) {
        // If it's a new search, save it
        setLastSearch({
          promptId: highlightInfo.promptId,
          key: highlightInfo.key,
          value: highlightInfo.value,
          lastPage: nextPage || pageNumber
        });
      }
    } else {
      // Clear lastSearch when there are no highlights
      setLastSearch(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightInfo]);

  // Modify findNextHighlightedPage to handle repeated searches
  const findNextHighlightedPage = useCallback((currentPage: number, isSameSearch: boolean = false): number | null => {
    const blocks = highlightInfo?.blocks ?? [];
    const pdfHits = highlightInfo?.pdfFallbackHits ?? [];
    if (!blocks.length && !pdfHits.length) return null;

    const startPage = isSameSearch ? currentPage + 1 : currentPage;

    if (blocks.length) {
      const nextBlock = highlightInfo!.blocks
        .filter((block) => ocrBlockPageNum(block) >= startPage)
        .sort((a, b) => ocrBlockPageNum(a) - ocrBlockPageNum(b))[0];

      if (nextBlock) {
        return ocrBlockPageNum(nextBlock);
      }

      const firstBlock = [...highlightInfo!.blocks].sort(
        (a, b) => ocrBlockPageNum(a) - ocrBlockPageNum(b),
      )[0];
      return firstBlock ? ocrBlockPageNum(firstBlock) : null;
    }

    const pages = [...new Set(pdfHits.map((h) => h.page))].sort((a, b) => a - b);
    const after = pages.find((p) => p >= startPage);
    if (after !== undefined) return after;
    return pages[0] ?? null;
  }, [highlightInfo]);

  useEffect(() => {
    scrollToPage(pageNumber);
  }, [pageNumber, scrollToPage]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', minWidth: 0 }}>
      <Toolbar 
        variant='dense'
        sx={{ 
          backgroundColor: theme => theme.palette.pdf_menubar.main,
          minHeight: '48px',
          flexShrink: 0,
          minWidth: 0,
          width: '100%',
          boxSizing: 'border-box',
          justifyContent: 'flex-start',
          gap: 0.5,
          '& .MuiIconButton-root': {
            padding: '4px',
          },
          '& .MuiTypography-root': {
            fontSize: '0.875rem',
          },
        }}
      >
        {/*
          Toolbar layout: [title][find][rest | clip][menu]
          Find and title are NOT inside the overflow:hidden row so a long filename cannot push Find off-screen.
        */}
        <div
          style={{
            flex: '0 1 200px',
            minWidth: 0,
            maxWidth: 200,
            marginRight: 4,
            overflow: 'hidden',
          }}
        >
          <Tooltip title={fileName || 'Untitled Document'} arrow>
            <Typography
              variant="body2"
              noWrap
              sx={{
                display: 'block',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                color: theme => theme.palette.pdf_menubar.contrastText,
                fontWeight: 'bold',
                cursor: 'default',
              }}
            >
              {fileName || 'Untitled Document'}
            </Typography>
          </Tooltip>
        </div>
        <Tooltip title="Find in document — search text in this PDF (Ctrl+F or ⌘F)">
          <span>
            <IconButton
              onClick={openFindBar}
              disabled={!fileUrl || !!loading}
              color="inherit"
              size="small"
              aria-label="Find in document"
              sx={{ flexShrink: 0 }}
            >
              <SearchIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        <div style={{ display: 'flex', alignItems: 'center', overflow: 'hidden', flex: '1 1 0%', minWidth: 0 }}>
          <IconButton onClick={goToPrevPage} disabled={pageNumber <= 1} color="inherit" size="small">
            <ArrowUpwardIcon fontSize="small" />
          </IconButton>
          <IconButton onClick={goToNextPage} disabled={pageNumber >= (numPages || 0)} color="inherit" size="small">
            <ArrowDownwardIcon fontSize="small" />
          </IconButton>
          <form onSubmit={handlePageNumberSubmit} style={{ display: 'flex', alignItems: 'center' }}>
            <TextField
              value={inputPageNumber}
              onChange={handlePageNumberChange}
              onBlur={() => setInputPageNumber(pageNumber.toString())}
              type="number"
              size="small"
              slotProps={{
                input: {
                  inputProps: {
                    min: 1,
                    max: numPages || 1,
                    style: { textAlign: 'center' }
                  }
                }
              }}
              sx={{ 
                mx: 0.5,
                width: '50px', // Slightly reduced width
                '& .MuiInputBase-root': {
                  height: '28px', // Make the input field shorter
                },
                '& input': {
                  appearance: 'textfield',
                  MozAppearance: 'textfield',
                  '&::-webkit-outer-spin-button, &::-webkit-inner-spin-button': {
                    WebkitAppearance: 'none',
                    margin: 0,
                  },
                }
              }}
            />
            <Typography variant="body2" sx={{ mx: 0.5, color: theme => theme.palette.pdf_menubar.contrastText, whiteSpace: 'nowrap' }}>
              of {numPages}
            </Typography>
          </form>
          <IconButton onClick={zoomOut} color="inherit" size="small">
            <ZoomOutIcon fontSize="small" />
          </IconButton>
          <IconButton onClick={zoomIn} color="inherit" size="small">
            <ZoomInIcon fontSize="small" />
          </IconButton>
          <IconButton onClick={rotateLeft} color="inherit" size="small">
            <RotateLeftIcon fontSize="small" />
          </IconButton>
          <IconButton onClick={rotateRight} color="inherit" size="small">
            <RotateRightIcon fontSize="small" />
          </IconButton>
        </div>
        <IconButton
          color="inherit"
          size="small"
          onClick={handleMenuClick}
          aria-label="more"
          aria-controls={open ? 'pdf-menu' : undefined}
          aria-haspopup="true"
          aria-expanded={open ? 'true' : undefined}
          sx={{ flexShrink: 0, ml: 'auto' }}
        >
          <MoreVertIcon fontSize="small" />
        </IconButton>
        <Menu
          id="pdf-menu"
          anchorEl={anchorEl}
          open={open}
          onClose={handleMenuClose}
          MenuListProps={{
            'aria-labelledby': 'more-button',
          }}
        >
          <StyledMenuItem
            onClick={() => {
              handleMenuClose();
              openFindBar();
            }}
            disabled={!fileUrl || !!loading}
          >
            <SearchIcon fontSize="small" sx={{ mr: 1 }} />
            Find in document…
          </StyledMenuItem>
          <StyledMenuItem onClick={handlePrint}>
            <PrintIcon fontSize="small" sx={{ mr: 1 }} />
            Print
          </StyledMenuItem>
          <StyledMenuItem onClick={handleSave}>
            <DownloadIcon fontSize="small" sx={{ mr: 1 }} />
            Download
          </StyledMenuItem>
          <Divider />
          <StyledMenuItem onClick={handleGoToFirstPage}>
            <VerticalAlignTopIcon fontSize="small" sx={{ mr: 1 }} />
            Go to First Page
          </StyledMenuItem>
          <StyledMenuItem onClick={handleGoToLastPage}>
            <VerticalAlignBottomIcon fontSize="small" sx={{ mr: 1 }} />
            Go to Last Page
          </StyledMenuItem>
          <Divider />
          <StyledMenuItem onClick={rotateRight}>
            <RotateRightIcon fontSize="small" sx={{ mr: 1 }} />
            Rotate Clockwise
          </StyledMenuItem>
          <StyledMenuItem onClick={rotateLeft}>
            <RotateLeftIcon fontSize="small" sx={{ mr: 1 }} />
            Rotate Counterclockwise
          </StyledMenuItem>
          <Divider />
          <StyledMenuItem onClick={fitToWidth}>
            <UnfoldMoreIcon fontSize="small" sx={{ mr: 1 }} />
            Fit to Width
            {fitMode === 'width' && <CheckIcon fontSize="small" sx={{ ml: 1, mb:1  }} />}
          </StyledMenuItem>
          <StyledMenuItem onClick={fitToPage}>
            <FitScreenIcon fontSize="small" sx={{ mr: 1 }} />
            Fit to Page
            {fitMode === 'page' && <CheckIcon fontSize="small" sx={{ ml: 1, mb: 1 }} />}
          </StyledMenuItem>
          <Divider />
          <StyledMenuItem
            onClick={handleBoundingBoxesToggle}
            disabled={!isOCRSupported(fileName)}
          >
            <CropFreeIcon fontSize="small" sx={{ mr: 1 }} />
            Bounding Boxes
            {showBoundingBoxes && <CheckIcon fontSize="small" sx={{ ml: 1 }} />}
          </StyledMenuItem>
          <StyledMenuItem onClick={openOcrOutput} disabled={!isOCRSupported(fileName)}>
            <ArticleIcon fontSize="small" sx={{ mr: 1 }} />
            Show OCR Output
            {!!ocrPanelKind && <CheckIcon fontSize="small" sx={{ ml: 1 }} />}
          </StyledMenuItem>
          <StyledMenuItem onClick={handleDownloadOcrJson}>
            <DownloadIcon fontSize="small" sx={{ mr: 1 }} />
            Download OCR JSON
          </StyledMenuItem>
          <StyledMenuItem
            onClick={handleRerunOCR}
            disabled={!isOCRSupported(fileName)}
          >
            <BoltIcon style={{ width: '1.25rem', height: '1.25rem', marginRight: '0.5rem' }} />
            Rerun OCR
          </StyledMenuItem>
          <Divider />
          <StyledMenuItem onClick={handleDocumentProperties}>
            <DescriptionOutlinedIcon fontSize="small" sx={{ mr: 1 }} />
            Document Properties...
          </StyledMenuItem>
        </Menu>
      </Toolbar>
      
      <PanelGroup id={`pdf-viewer-panels-${id}`} direction="horizontal" style={{ flexGrow: 1 }}>
          <Panel defaultSize={70}>
            <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
              <div
                ref={containerRef}
                style={{
                  flex: 1,
                  minHeight: 0,
                  overflowY: 'auto',
                  padding: '16px',
                }}
              >
                {loading ? (
                  <div>Loading PDF...</div>
                ) : error ? (
                  <Typography color="error" align="center">{error}</Typography>
                ) : fileUrl ? (
                  <Document
                    file={fileUrl}
                    onLoadSuccess={handleLoadSuccess}
                    onLoadError={handleLoadError}
                  >
                    {Array.from(new Array(numPages), (el, index) => (
                      <div 
                        key={`page_container_${index + 1}`}
                        ref={el => { pageRefs.current[index] = el; }}
                        style={{ 
                          position: 'relative',
                          width: Math.abs(rotation) === 90 || Math.abs(rotation) === 270 
                            ? pdfDimensions.height * scale 
                            : pdfDimensions.width * scale,
                          height: Math.abs(rotation) === 90 || Math.abs(rotation) === 270 
                            ? pdfDimensions.width * scale 
                            : pdfDimensions.height * scale,
                          transform: `rotate(${rotation}deg)`,
                          transformOrigin: 'center center',
                          margin: '8px auto',
                          display: 'flex',
                          justifyContent: 'center',
                          alignItems: 'center'
                        }}
                      >
                        <Page 
                          key={`page_${index + 1}`} 
                          pageNumber={index + 1} 
                          width={pdfDimensions.width}
                          height={pdfDimensions.height}
                          scale={scale}
                          rotate={originalRotation}
                          renderTextLayer={false}
                          renderAnnotationLayer={false}
                        >
                          {renderHighlights(index + 1)}
                          {renderSearchHighlights(index + 1)}
                          {renderBoundingBoxes(index + 1)}
                        </Page>
                        {index < numPages! - 1 && <hr style={{ border: '2px solid black' }} />}
                      </div>
                    ))}
                  </Document>
                ) : (documentState === 'ocr_processing' || documentState === 'llm_processing') ? (
                  <Typography color="text.secondary" align="center" sx={{ py: 2 }}>
                    Document is being processed. PDF will appear when ready.
                  </Typography>
                ) : (
                  <Typography color="error" align="center">
                    No PDF file available.
                  </Typography>
                )}
              </div>

              {findBarOpen && fileUrl && !loading && (
                <Paper
                  elevation={0}
                  square
                  component="div"
                  role="search"
                  aria-label="Find in document"
                  sx={{
                    flexShrink: 0,
                    borderTop: 1,
                    borderColor: 'divider',
                    px: 1.25,
                    py: 0.5,
                    bgcolor: theme => (theme.palette.mode === 'dark' ? 'grey.900' : 'grey.100'),
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.75,
                      width: '100%',
                      flexWrap: 'wrap',
                      minHeight: 32,
                    }}
                  >
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.75,
                        flex: '1 1 0',
                        minWidth: 0,
                        flexWrap: 'wrap',
                      }}
                    >
                      <Tooltip title="Embedded PDF text only — scanned image pages are not searched">
                        <SearchIcon sx={{ color: 'text.secondary', flexShrink: 0, fontSize: '1.125rem' }} aria-hidden />
                      </Tooltip>
                      <TextField
                        inputRef={findInputRef}
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            if (searchHits.length > 0) goToActiveMatch(0);
                          }
                        }}
                        placeholder="Find in document…"
                        size="small"
                        autoFocus
                        sx={{
                          flex: '1 1 200px',
                          minWidth: { xs: 140, sm: 240 },
                          maxWidth: { md: 640 },
                          '& .MuiInputBase-root': {
                            backgroundColor: theme => theme.palette.background.paper,
                            minHeight: 30,
                            height: 30,
                            fontSize: '0.8125rem',
                          },
                          '& .MuiInputBase-input': {
                            py: 0.5,
                          },
                        }}
                      />
                      <IconButton
                        onClick={goToPrevSearchMatch}
                        disabled={searchHits.length === 0}
                        color="default"
                        size="small"
                        aria-label="Previous match"
                        sx={{ flexShrink: 0, p: 0.375 }}
                      >
                        <NavigateBeforeIcon sx={{ fontSize: '1.125rem' }} />
                      </IconButton>
                      <IconButton
                        onClick={goToNextSearchMatch}
                        disabled={searchHits.length === 0}
                        color="default"
                        size="small"
                        aria-label="Next match"
                        sx={{ flexShrink: 0, p: 0.375 }}
                      >
                        <NavigateNextIcon sx={{ fontSize: '1.125rem' }} />
                      </IconButton>
                      <Typography
                        variant="caption"
                        sx={{
                          minWidth: '3.5rem',
                          lineHeight: 1,
                          color: 'text.secondary',
                          opacity: searchBusy ? 0.6 : 1,
                          flexShrink: 0,
                          fontVariantNumeric: 'tabular-nums',
                          alignSelf: 'center',
                        }}
                      >
                        {debouncedSearch.trim()
                          ? searchBusy
                            ? '…'
                            : searchHits.length > 0
                              ? `${activeMatchIndex + 1} / ${searchHits.length}`
                              : '0 / 0'
                          : '—'}
                      </Typography>
                    </Box>
                    <Tooltip title="Close (Esc)">
                      <IconButton
                        onClick={closeFindBar}
                        size="small"
                        aria-label="Close find bar"
                        sx={{ flexShrink: 0, p: 0.375 }}
                      >
                        <CloseIcon sx={{ fontSize: '1.125rem' }} />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </Paper>
              )}
            </Box>
          </Panel>

          {ocrPanelKind && (
            <>
              <div
                className="fixed inset-0 z-[70] bg-black bg-opacity-50"
                onClick={() => setOcrPanelKind(null)}
                role="presentation"
              />
              <DraggablePanel
                open={!!ocrPanelKind}
                resetToken={id}
                anchorPercent={{ x: 50, y: 45 }}
                width="min(100vw - 32px, 42rem)"
                height="min(90vh, 820px)"
                zIndex={71}
                ariaLabel="OCR Output"
                title={
                  <>
                    <ArticleIcon className="shrink-0 text-blue-600" fontSize="small" />
                    <span className="truncate">OCR Output</span>
                  </>
                }
                headerActions={
                  <button
                    type="button"
                    onClick={() => setOcrPanelKind(null)}
                    className="rounded-md bg-blue-600 px-3 py-1.5 text-xs text-white hover:bg-blue-700"
                  >
                    Close
                  </button>
                }
              >
                <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                  <Tabs
                    value={ocrPanelKind}
                    onChange={(_, v: OcrPanelKind) => setOcrPanelKind(v)}
                    variant="scrollable"
                    scrollButtons="auto"
                    sx={{
                      borderBottom: 1,
                      borderColor: 'divider',
                      px: 2,
                      minHeight: 40,
                      '& .MuiTab-root:not(.Mui-selected)': { color: '#374151' },
                    }}
                  >
                    <Tab label="Text" value="text" sx={{ minHeight: 40, py: 1, textTransform: 'none' }} />
                    <Tab label="Markdown" value="markdown" sx={{ minHeight: 40, py: 1, textTransform: 'none' }} />
                    <Tab label="Web" value="html" sx={{ minHeight: 40, py: 1, textTransform: 'none' }} />
                    <Tab label="Excel" value="excel" sx={{ minHeight: 40, py: 1, textTransform: 'none' }} />
                  </Tabs>
                  <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-6 pt-3">
                    {ocrPanelKind === 'text' && (
                      <>
                        {ocrLoading ? (
                          <div className="flex items-center gap-3 py-6">
                            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" aria-hidden />
                            <span className="text-sm italic text-gray-500">Loading OCR text...</span>
                          </div>
                        ) : ocrError ? (
                          <p className="py-4 text-sm text-red-600">{ocrError}</p>
                        ) : (
                          <div className="flex min-h-0 flex-1 flex-col">
                            <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words rounded border bg-gray-50 p-2 font-mono text-xs leading-relaxed text-gray-800 [&::-webkit-scrollbar]:w-2.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent">
                              {ocrText || 'No OCR text available.'}
                            </pre>
                          </div>
                        )}
                      </>
                    )}
                    {ocrPanelKind === 'markdown' && (
                      <>
                        {ocrMarkdownLoading ? (
                          <div className="flex items-center gap-3 py-6">
                            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" aria-hidden />
                            <span className="text-sm italic text-gray-500">Loading OCR markdown...</span>
                          </div>
                        ) : ocrMarkdownError ? (
                          <p className="py-4 text-sm text-red-600">{ocrMarkdownError}</p>
                        ) : (
                          <div className="min-h-0 flex-1 overflow-auto rounded border bg-gray-50 p-3 text-gray-800 [&::-webkit-scrollbar]:w-2.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                h1: ({children}) => <h1 className="text-2xl font-bold mt-4 mb-2">{children}</h1>,
                                h2: ({children}) => <h2 className="text-xl font-bold mt-3 mb-2">{children}</h2>,
                                h3: ({children}) => <h3 className="text-lg font-semibold mt-3 mb-1">{children}</h3>,
                                h4: ({children}) => <h4 className="text-base font-semibold mt-2 mb-1">{children}</h4>,
                                p: ({children}) => <p className="mb-2">{children}</p>,
                                ul: ({children}) => <ul className="list-disc pl-5 mb-2">{children}</ul>,
                                ol: ({children}) => <ol className="list-decimal pl-5 mb-2">{children}</ol>,
                                li: ({children}) => <li className="mb-0.5">{children}</li>,
                                table: ({children}) => <table className="border-collapse w-full mb-2 text-sm">{children}</table>,
                                th: ({children}) => <th className="border border-gray-300 px-2 py-1 bg-gray-100 font-semibold text-left">{children}</th>,
                                td: ({children}) => <td className="border border-gray-300 px-2 py-1">{children}</td>,
                                code: ({children}) => <code className="bg-gray-200 rounded px-1 text-xs font-mono">{children}</code>,
                              }}
                            >
                              {ocrMarkdown || '*No content.*'}
                            </ReactMarkdown>
                          </div>
                        )}
                      </>
                    )}
                    {ocrPanelKind === 'html' && (
                      <>
                        {ocrHtmlLoading ? (
                          <div className="flex items-center gap-3 py-6">
                            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" aria-hidden />
                            <span className="text-sm italic text-gray-500">Loading OCR HTML...</span>
                          </div>
                        ) : ocrHtmlError ? (
                          <p className="py-4 text-sm text-red-600">{ocrHtmlError}</p>
                        ) : (
                          <iframe
                            title="OCR HTML preview"
                            sandbox="allow-same-origin"
                            className="min-h-[min(70vh,600px)] w-full flex-1 rounded border border-gray-200 bg-white"
                            srcDoc={ocrHtml || '<p></p>'}
                          />
                        )}
                      </>
                    )}
                    {ocrPanelKind === 'excel' && (
                      <div className="flex flex-col gap-3 py-2">
                        <p className="text-sm text-gray-700">
                          Download an Excel workbook built from tables detected in the OCR result (one worksheet per table).
                        </p>
                        <p className="text-xs text-gray-500">
                          If the document has no tables, a notification will appear.
                        </p>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center justify-end border-t border-gray-200 px-6 py-3">
                    <button
                      type="button"
                      onClick={() => void handleOcrPanelDownload()}
                      className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-800 shadow-sm hover:bg-gray-50"
                    >
                      <DownloadIcon fontSize="small" sx={{ mr: 0.5 }} />
                      {ocrPanelKind === 'text' ? 'Save as .txt'
                        : ocrPanelKind === 'markdown' ? 'Save as .md'
                        : ocrPanelKind === 'html' ? 'Save as .html'
                        : 'Download Excel'}
                    </button>
                  </div>
                </div>
              </DraggablePanel>
            </>
          )}
        </PanelGroup>

      <Dialog 
        open={showProperties} 
        onClose={() => setShowProperties(false)}
        aria-labelledby="document-properties-dialog-title"
        maxWidth="xs" // Changed from "sm" to "xs" for a narrower dialog
        fullWidth
      >
        <DialogTitle id="document-properties-dialog-title">Document Properties</DialogTitle>
        <DialogContent>
          {documentProperties === null ? (
            <Typography>Loading properties...</Typography>
          ) : Object.keys(documentProperties).length === 0 ? (
            <Typography>No properties available</Typography>
          ) : (
            <List sx={{ padding: 0 }}>
              {Object.entries(documentProperties).map(([key, value]) => (
                <StyledListItem key={key}>
                  <Typography component="span" className="property-key">
                    {key}:
                  </Typography>
                  <Typography component="span" className="property-value">
                    {value}
                  </Typography>
                </StyledListItem>
              ))}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowProperties(false)}>Close</Button>
        </DialogActions>
      </Dialog>
      {/* Add this iframe for printing */}
      <iframe
        ref={printIframeRef}
        style={{ display: 'none' }}
        title="Print PDF"
      />
    </div>
  );
};

export default PDFViewer;
