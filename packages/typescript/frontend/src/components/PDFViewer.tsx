// components/PDFViewer.js
"use client"

import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { pdfjs, Document, Page } from 'react-pdf';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';
import { DocRouterOrgApi } from '@/utils/api';
import { Toolbar, Typography, IconButton, TextField, Menu, MenuItem, Divider, Dialog, DialogTitle, DialogContent, DialogActions, Button, List, Tooltip, Box, CircularProgress } from '@mui/material';
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
import { saveAs } from 'file-saver';
import { PanelGroup, Panel } from 'react-resizable-panels';
import CheckIcon from '@mui/icons-material/Check';
import TextSnippetIcon from '@mui/icons-material/TextSnippet';
import { OCRProvider } from '@/contexts/OCRContext';
import type { OCRBlock } from '@docrouter/sdk';
import type { HighlightInfo } from '@/types/index';

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

// Update the props interface
interface PDFViewerProps {
  organizationId: string;
  id: string;
  highlightInfo?: HighlightInfo;
}

const PDFViewer = ({ organizationId, id, highlightInfo }: PDFViewerProps) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [scale, setScale] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [pdfDimensions, setPdfDimensions] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Use a fileRef to store the file URL, which doesn't trigger re-renders when it changes.
  // The cleanup function now uses this ref to revoke the URL.
  //This approach resolves the dependency warning without causing unnecessary re-renders.
  const fileRef = useRef<string | null>(null);

  // This is a tricky effect hook. It needs to clean up
  // the file URL when the component unmounts. The hook cleanup can be called while
  // the hook is still running, for example, before the axios request completes.
  // We handle this by checking if isMounted is true before setting the file URL.
  useEffect(() => {
    let isMounted = true;

    const loadPDF = async () => {
      try {
        const response = await docRouterOrgApi.getDocument(
          {
            documentId: id,
            fileType: "pdf"
          }
        );
        
        // Create a blob from the array buffer
        const blob = new Blob([response.content], { type: 'application/pdf' });
        const url = URL.createObjectURL(blob);

        if (isMounted) {
          // Load the PDF data directly instead of using the blob URL
          const loadingTask = pdfjs.getDocument({ data: response.content });
          await loadingTask.promise;  // Wait for PDF to load before continuing
          
          setFile(url);  // Keep the URL for download/print functionality
          fileRef.current = url;
          setLoading(false);

          // Use metadata from the response
          setFileName(response.document_name);
          setFileSize(blob.size);
        } else {
          if (url) {
            URL.revokeObjectURL(url);
          }
        }
      } catch (error) {
        console.error('Error loading PDF:', error);
        if (isMounted) {
          setError('Failed to load PDF. Please try again.');
          setLoading(false);
        }
      }
    };

    loadPDF();

    return () => {
      isMounted = false;
      if (fileRef.current) {
        URL.revokeObjectURL(fileRef.current);
      }
      setFile(null);
    };
  }, [id, organizationId, docRouterOrgApi]);

  const pageRefs = useRef<(HTMLDivElement | null)[]>([]);

  const scrollToPage = useCallback((pageNum: number, behavior: ScrollBehavior = 'smooth') => {
    
    if (pageRefs.current[pageNum - 1]) {
      pageRefs.current[pageNum - 1]?.scrollIntoView({ behavior });
      setPageNumber(pageNum);
      setInputPageNumber(pageNum.toString());
    }
  }, []);

  const [showProperties, setShowProperties] = useState(false);
  const [documentProperties, setDocumentProperties] = useState<Record<string, string> | null>(null);
  const [fileName, setFileName] = useState<string>('');
  const [fileSize, setFileSize] = useState<number>(0);
  const [showOcr, setShowOcr] = useState(false);
  const [ocrText, setOcrText] = useState<string>('');
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [fitMode, setFitMode] = useState<'width' | 'page' | 'manual'>('width');

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
        'Creation Date': info.CreationDate ? new Date(info.CreationDate).toLocaleString() : 'N/A',
        'Modification Date': info.ModDate ? new Date(info.ModDate).toLocaleString() : 'N/A',
        'Creator': info.Creator || 'N/A',
        'Producer': info.Producer || 'N/A',
        'Version': info.PDFFormatVersion || 'N/A',
        'Number of Pages': pdf.numPages.toString(),
        'Original Rotation': `${page.rotate}°`,
      };

      console.log('Extracted properties:', properties);
      setDocumentProperties(properties);
    } catch (error) {
      console.error('Error extracting document properties:', error);
      setDocumentProperties({ 'Error': 'Failed to extract document properties' });
    }
  }, [fileName, fileSize]);

  const [originalRotation, setOriginalRotation] = useState(0);

  const handleLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setPageNumber(1);
    pageRefs.current = new Array(numPages).fill(null);
    
    pdfjs.getDocument(file!).promise.then((pdf) => {
      extractDocumentProperties(pdf);
      
      // Get the first page and check its rotation
      pdf.getPage(1).then((page) => {
        const viewport = page.getViewport({ scale: 1 });
        setPdfDimensions({ width: viewport.width, height: viewport.height });
        
        // Store the original rotation
        setOriginalRotation(page.rotate || 0);
      });
    });
  };

  const handleLoadError = (error: { message: string }) => {
    setError(error.message);
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

          setScale(adjustedScale);
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
    if (file) {
      // Create a temporary iframe
      const iframe = printIframeRef.current;
      if (!iframe) return;

      // Set the source of the iframe to the PDF file
      iframe.src = file;

      // Wait for the iframe to load
      iframe.onload = () => {
        // Print the iframe content
        iframe.contentWindow?.print();
      };
    }
    handleMenuClose();
  };

  const handleSave = () => {
    if (file) {
      fetch(file)
        .then(response => response.blob())
        .then(blob => {
          const defaultFileName = fileName || `Document_${id}.pdf`;
          saveAs(blob, defaultFileName);
        })
        .catch(error => {
          console.error('Error saving the file:', error);
          // Optionally, you can show an error message to the user here
        });
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

  const handleOcrToggle = useCallback(() => {
    setShowOcr(prev => !prev);
    handleMenuClose();
  }, [handleMenuClose]);

  const handleDownloadOcrText = async () => {
    try {
      const text = await docRouterOrgApi.getOCRText({
        documentId: id
      });
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const defaultFileName = (fileName || `Document_${id}`) + `_ocr.txt`;
      saveAs(blob, defaultFileName);
    } catch (err) {
      console.error('Error downloading OCR text:', err);
    }
    handleMenuClose();
  };

  const handleDownloadOcrJson = async () => {
    try {
      const blocks = await docRouterOrgApi.getOCRBlocks({
        documentId: id
      });
      const blob = new Blob([JSON.stringify(blocks, null, 2)], { type: 'application/json' });
      const defaultFileName = (fileName || `Document_${id}`) + `_ocr.json`;
      saveAs(blob, defaultFileName);
    } catch (err) {
      console.error('Error downloading OCR JSON:', err);
    }
    handleMenuClose();
  };

  useEffect(() => {
    const fetchOcrText = async () => {
      if (!showOcr) return;
      
      try {
        setOcrLoading(true);
        setOcrError(null);
        const text = await docRouterOrgApi.getOCRText({
          documentId: id,
          pageNum: pageNumber
        });
        setOcrText(text);
      } catch (err) {
        console.error('Error fetching OCR text:', err);
        setOcrError('Failed to load OCR text');
      } finally {
        setOcrLoading(false);
      }
    };

    fetchOcrText();
  }, [id, pageNumber, showOcr, organizationId, docRouterOrgApi]);

  // This is called once for each page
  const renderHighlights = useCallback((page: number) => {
    if (!highlightInfo?.blocks.length) return null;

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
        {highlightInfo?.blocks.map((block: OCRBlock, index: number) => {
          if (block.Page !== page) return null;

          const { Geometry } = block;
          const { Width, Height, Left, Top } = Geometry.BoundingBox;
          
          return (
            <div
              key={index}
              style={{
                position: 'absolute',
                left: `${(Left * 100) - PADDING_PERCENT}%`,
                top: `${(Top * 100) - PADDING_PERCENT}%`,
                width: `${(Width * 100) + (PADDING_PERCENT * 2)}%`,
                height: `${(Height * 100) + (PADDING_PERCENT * 2)}%`,
                //backgroundColor: 'rgba(255, 140, 50, 0.4)', // Orange
                //backgroundColor: 'rgba(255, 127, 80, 0.4)', // Coral orange
                backgroundColor: 'rgba(251, 192, 45, 0.4)',  // Soft amber
                //backgroundColor: 'rgba(0, 188, 212, 0.35)',  // Teal accent
                //backgroundColor: 'rgba(156, 39, 176, 0.25)',  // Royal purple
                //backgroundColor: 'rgba(255, 64, 129, 0.3)',  // Deep rose
                clipPath: `polygon(
                  /* Left edge - slightly jagged */
                  0% 35%, 2% 30%, 0% 25%, 3% 20%,
                  /* Top edge - gentle wave */
                  3% 20%, 20% 15%, 40% 18%, 60% 15%, 80% 17%, 97% 20%,
                  /* Right edge - slightly jagged */
                  97% 20%, 100% 25%, 98% 30%, 100% 35%,
                  /* Bottom edge - gentle wave, moved even lower */
                  100% 85%, 80% 90%, 60% 87%, 40% 90%, 20% 88%, 3% 85%,
                  /* Close back to start */
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
      </div>
    );
  }, [highlightInfo]);

  // Add this near the other state declarations
  const [lastSearch, setLastSearch] = useState<{
    promptId: string;
    key?: string;
    value: string;
    lastPage?: number;
  } | null>(null);

  // Update the useEffect for highlightInfo changes
  useEffect(() => {
    if (highlightInfo?.blocks.length) {
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
    if (!highlightInfo?.blocks.length) return null;

    //console.log('findNextHighlightedPage', currentPage, isSameSearch, highlightInfo.key, highlightInfo.value);

    // For a repeated search, start looking from the next page
    const startPage = isSameSearch ? currentPage + 1 : currentPage;

    // // Log all pages with highlights
    // for (const block of highlightInfo.blocks) {
    //   console.log('block', block.Page);
    // }

    // First look for highlights after the start page
    const nextHighlightedPage = highlightInfo.blocks
      .filter(block => block.Page >= startPage)
      .sort((a, b) => a.Page - b.Page)[0]?.Page;

    if (nextHighlightedPage) {
      console.log('nextHighlightedPage', nextHighlightedPage);
      return nextHighlightedPage;
    }

    // Look for highlights from the first page
    const firstHighlightedPage = highlightInfo.blocks
      .sort((a, b) => a.Page - b.Page)[0]?.Page;

    // Only return first page if it's different from current page
    if (firstHighlightedPage) {
      console.log('firstHighlightedPage', firstHighlightedPage);
      return firstHighlightedPage;
    }

    return null;
  }, [highlightInfo]);

  useEffect(() => {
    scrollToPage(pageNumber);
  }, [pageNumber, scrollToPage]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Toolbar 
        variant='dense'
        sx={{ 
          backgroundColor: theme => theme.palette.pdf_menubar.main,
          minHeight: '48px',
          flexShrink: 0,
          '& .MuiIconButton-root': {
            padding: '4px',
          },
          '& .MuiTypography-root': {
            fontSize: '0.875rem',
          },
          justifyContent: 'space-between',
        }}
      >
      
        <div style={{ display: 'flex', alignItems: 'center', overflow: 'hidden' }}>
          <div style={{ width: '200px', marginRight: '8px', display: 'flex', justifyContent: 'flex-end' }}>
            <Tooltip title={fileName || 'Untitled Document'} arrow>
              <Typography
                variant="body2"
                noWrap
                sx={{
                  maxWidth: '100%',
                  color: theme => theme.palette.pdf_menubar.contrastText,
                  fontWeight: 'bold',
                  cursor: 'default',
                }}
              >
                {fileName || 'Untitled Document'}
              </Typography>
            </Tooltip>
          </div>
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
                  '-moz-appearance': 'textfield',
                  '&::-webkit-outer-spin-button, &::-webkit-inner-spin-button': {
                    '-webkit-appearance': 'none',
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
          <StyledMenuItem onClick={handleOcrToggle}>
            <TextSnippetIcon fontSize="small" sx={{ mr: 1 }} />
            Show OCR Text
            {showOcr && <CheckIcon fontSize="small" sx={{ ml: 1 }} />}
          </StyledMenuItem>
          <StyledMenuItem onClick={handleDownloadOcrText}>
            <DownloadIcon fontSize="small" sx={{ mr: 1 }} />
            Download OCR Text
          </StyledMenuItem>
          <StyledMenuItem onClick={handleDownloadOcrJson}>
            <DownloadIcon fontSize="small" sx={{ mr: 1 }} />
            Download OCR JSON
          </StyledMenuItem>
          <Divider />
          <StyledMenuItem onClick={handleDocumentProperties}>
            <DescriptionOutlinedIcon fontSize="small" sx={{ mr: 1 }} />
            Document Properties...
          </StyledMenuItem>
        </Menu>
      </Toolbar>
      
      <OCRProvider>
        <PanelGroup direction="horizontal" style={{ flexGrow: 1 }}>
          <Panel defaultSize={70}>
            <div ref={containerRef} style={{ height: '100%', overflowY: 'auto', padding: '16px' }}>
              {loading ? (
                <div>Loading PDF...</div>
              ) : error ? (
                <Typography color="error" align="center">{error}</Typography>
              ) : file ? (
                <Document
                  file={file}
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
                      >
                        {renderHighlights(index + 1)}
                      </Page>
                      {index < numPages! - 1 && <hr style={{ border: '2px solid black' }} />}
                    </div>
                  ))}
                </Document>
              ) : (
                <Typography color="error" align="center">
                  No PDF file available.
                </Typography>
              )}
            </div>
          </Panel>

          {showOcr && (
            <Panel defaultSize={30}>
              <Box sx={{ height: '100%', overflow: 'auto', p: 2, borderLeft: 1, borderColor: 'divider' }}>
                <Typography variant="h6" gutterBottom>
                  OCR Text - Page {pageNumber}
                </Typography>
                {ocrLoading ? (
                  <CircularProgress size={24} />
                ) : ocrError ? (
                  <Typography color="error">{ocrError}</Typography>
                ) : (
                  <Typography
                    variant="body2"
                    component="pre"
                    sx={{
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontFamily: 'monospace'
                    }}
                  >
                    {ocrText}
                  </Typography>
                )}
              </Box>
            </Panel>
          )}
        </PanelGroup>
      </OCRProvider>

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
