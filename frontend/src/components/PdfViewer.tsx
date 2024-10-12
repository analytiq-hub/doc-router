// components/PDFViewer.js
"use client"

import { useEffect, useRef, useState } from 'react';
import { pdfjs, Document, Page } from 'react-pdf';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';
import { downloadFile } from '@/utils/api';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const PDFViewer = ({ id }: { id: string }) => {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [error, setError] = useState<string | null>(null); // State to hold error messages
  const canvasRef = useRef<HTMLCanvasElement | null>(null); // Specify the type for canvasRef

  const handleLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setPageNumber(1);
  };

  const handleLoadError = (error: { message: string }) => { // Specify the type for error
    setError(error.message); // Capture the error message
  };

  const [file, setFile] = useState<string | null>(null); // Update type to accept string

  useEffect(() => {
    const fetchPDF = async () => {
      try {
        const response = await downloadFile(id);

        // Ensure the response is a Blob
        const blob = new Blob([response], { type: 'application/pdf' });
        const fileURL = URL.createObjectURL(blob);
        setFile(fileURL);
      } catch (error) {
        console.error('Error fetching PDF:', error);
        setError('Failed to load PDF. Please try again.');
      }
    };

    fetchPDF();

    // Cleanup function to revoke the object URL
    return () => {
      if (file) {
        URL.revokeObjectURL(file);
      }
    };
  }, [id]);

  useEffect(() => {
    const canvas = canvasRef.current;

    // Check if canvas is not null before accessing getContext
    if (canvas) {
      const ctx = canvas.getContext('2d');
      
      const drawRectangle = (e: MouseEvent) => { // Specify the type for e
        // Draw a rectangle based on mouse coordinates
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = 'red';
        ctx.strokeRect(x, y, 100, 100); // Example: 100x100 rectangle
      };

      canvas.addEventListener('mousedown', drawRectangle);

      return () => {
        canvas.removeEventListener('mousedown', drawRectangle);
      };
    }
  }, []);

  const goToNextPage = () => {
    if (pageNumber < numPages!) {
      setPageNumber(pageNumber + 1);
    }
  };

  const goToPrevPage = () => {
    if (pageNumber > 1) {
      setPageNumber(pageNumber - 1);
    }
  };

  return (
    <div>
      {/* Add discreet navigation buttons */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
        <button onClick={goToPrevPage} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '20px' }}>&lt;</button>
        <button onClick={goToNextPage} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '20px' }}>&gt;</button>
      </div>
      {/* Display total number of pages if available */}
      {numPages && <p>Total Pages: {numPages}</p>}
      {error && <div style={{ color: 'red' }}>Error: {error}</div>} {/* Display error message */}
      <Document file={file} onLoadSuccess={handleLoadSuccess} onLoadError={handleLoadError}>
        <Page pageNumber={pageNumber} />
      </Document>
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          pointerEvents: 'none',
        }}
        width="1000"
        height="1000"
      />
    </div>
  );
};

export default PDFViewer;
