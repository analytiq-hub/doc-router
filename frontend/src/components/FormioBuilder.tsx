import React, { useEffect, useRef, useState } from 'react';

interface FormioBuilderProps {
  jsonFormio?: string;
  onChange?: (components: unknown[]) => void;
}

const FormioBuilder: React.FC<FormioBuilderProps> = ({ jsonFormio, onChange }) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const onChangeRef = useRef(onChange);
  const [iframeReady, setIframeReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [iframeHeight, setIframeHeight] = useState(600);

  // Keep the onChange ref updated
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  // Listen for messages from iframe
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Security: In production, check event.origin
      if (!event.data || typeof event.data !== 'object') return;

      switch (event.data.type) {
        case 'BUILDER_READY':
          console.log('FormioBuilder: Iframe ready');
          setIframeReady(true);
          setError(null);
          break;

        case 'FORM_CHANGED':
          console.log('FormioBuilder: Form changed', event.data.components);
          if (onChangeRef.current) {
            onChangeRef.current(event.data.components);
          }
          break;

        case 'ERROR':
          console.error('FormioBuilder: Iframe error', event.data.message);
          setError(event.data.message);
          break;

        case 'RESIZE_NEEDED':
          if (event.data.height && event.data.height !== iframeHeight) {
            setIframeHeight(Math.max(400, event.data.height + 50)); // Add some padding
          }
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [iframeHeight]);

  // Send form data to iframe when it changes
  useEffect(() => {
    if (!iframeReady || !iframeRef.current?.contentWindow) return;

    console.log('FormioBuilder: Sending form data to iframe', jsonFormio);
    
    try {
      iframeRef.current.contentWindow.postMessage({
        type: 'LOAD_FORM',
        jsonFormio: jsonFormio || '[]'
      }, '*');
    } catch (error) {
      console.error('FormioBuilder: Error sending message to iframe', error);
    }
  }, [jsonFormio, iframeReady]);

  // Handle iframe load
  const handleIframeLoad = () => {
    console.log('FormioBuilder: Iframe loaded');
    // The iframe will send BUILDER_READY message when actually ready
  };

  if (error) {
    return (
      <div className="p-4 border border-red-200 rounded-lg bg-red-50">
        <h3 className="text-red-800 font-semibold mb-2">Formio Builder Error</h3>
        <p className="text-red-600 text-sm">{error}</p>
        <button 
          onClick={() => {
            setError(null);
            setIframeReady(false);
            // Force iframe reload
            if (iframeRef.current) {
              iframeRef.current.src = iframeRef.current.src;
            }
          }}
          className="mt-2 px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      {!iframeReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50 border border-gray-200 rounded-lg z-10">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-sm text-gray-600">Loading Form Builder...</p>
          </div>
        </div>
      )}
      
      <iframe
        ref={iframeRef}
        src="/formio-builder.html"
        onLoad={handleIframeLoad}
        style={{
          width: '100%',
          height: `${iframeHeight}px`,
          border: 'none',
          borderRadius: '0.5rem',
          opacity: iframeReady ? 1 : 0,
          transition: 'opacity 0.3s ease-in-out'
        }}
        title="Formio Form Builder"
        sandbox="allow-scripts allow-same-origin allow-forms allow-modals"
      />
    </div>
  );
};

export default FormioBuilder;
