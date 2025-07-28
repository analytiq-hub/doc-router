'use client';

import React, { useEffect, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom/client';

interface FormioShadowWrapperProps {
  children: React.ReactNode;
  className?: string;
  onReady?: () => void;
}

const FormioShadowWrapper: React.FC<FormioShadowWrapperProps> = ({ 
  children, 
  className = '',
  onReady
}) => {
  const hostRef = useRef<HTMLDivElement>(null);
  const shadowRef = useRef<ShadowRoot | null>(null);
  const rootRef = useRef<ReactDOM.Root | null>(null);

  // Set up focused drag-and-drop event handling for FormioBuilder
  const setupDragDropEventForwarding = useCallback((shadowRoot: ShadowRoot, hostElement: HTMLElement) => {
    // No-op for now - drag and drop investigation removed
    console.log('FormioShadowWrapper: setupDragDropEventForwarding called (no-op)');
    
    // Return empty cleanup function
    return () => {};
  }, []);

  // Set up FormioBuilder drag support - simplified for now
  const setupFormioBuilderDragSupport = useCallback((shadowRoot: ShadowRoot, container: HTMLElement) => {
    console.log('FormioShadowWrapper: setupFormioBuilderDragSupport called (simplified)');
    // Drag investigation removed for now
  }, []);

  // CSS content for shadow DOM - replicate exact same styles as formio.css
  const getShadowCSS = useCallback(() => {
    return `
    /* Shadow DOM container styles */
    :host {
      display: block;
      width: 100%;
      height: 100%;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    .formio-shadow-container {
      height: 100%;
      width: 100%;
      box-sizing: border-box;
    }

    /* Replicate the exact styles from formio.css */
    
    /* Custom Form.io styles */
    .formio-builder .btn, 
    .formio-builder .btn-primary, 
    .formio-builder .btn-default {
      font-size: 0.85rem !important;
      padding: 0.25rem 0.5rem !important;
      border-radius: 0.375rem !important;
      min-width: 0 !important;
      min-height: 0 !important;
      line-height: 1.2 !important;
      margin-bottom: 0.25rem !important;
    }

    /* Ensure icons are displayed properly */
    .formio-builder .bx,
    .formio-builder [class^="bx-"],
    .formio-builder [class*=" bx-"] {
      font-family: "boxicons" !important;
      font-weight: normal !important;
      font-style: normal !important;
      display: inline-block !important;
      line-height: 1 !important;
      text-rendering: auto !important;
      -webkit-font-smoothing: antialiased !important;
    }

    .formio-builder .formio-component {
      margin-bottom: 0.25rem !important;
    }

    .formio-builder .formio-builder-panel-premium,
    .formio-builder .formio-builder-panel-data {
      display: none !important;
    }

    /* Force the builder to be a horizontal flex container */
    .formio.builder.formbuilder {
      display: flex !important;
      flex-direction: row !important;
      height: 100%;
    }

    /* Sidebar: fixed width, scrollable if needed */
    .formio.builder.formbuilder .formcomponents {
      min-width: 260px;
      max-width: 320px;
      flex: 0 0 260px;
      margin-right: 1rem;
      overflow-y: auto;
      height: 100%;
    }

    /* Form area: take the rest of the space */
    .formio.builder.formbuilder .formarea {
      flex: 1 1 0%;
      min-width: 0;
      overflow-y: auto;
      height: 100%;
    }
    `;
  }, []);

  const createShadowDOM = useCallback(() => {
    if (!hostRef.current) {
      console.log('FormioShadowWrapper: No host element available');
      return;
    }

    // Check if shadow root already exists
    if (hostRef.current.shadowRoot) {
      console.log('FormioShadowWrapper: Shadow DOM already exists, reusing...');
      shadowRef.current = hostRef.current.shadowRoot;
      
      // Clear existing content and recreate
      shadowRef.current.innerHTML = '';
    } else if (shadowRef.current) {
      console.log('FormioShadowWrapper: Shadow ref exists but host shadowRoot is null, clearing ref');
      shadowRef.current = null;
    }

    try {
      let shadow: ShadowRoot;
      
      if (!shadowRef.current) {
        console.log('FormioShadowWrapper: Creating new shadow DOM...');
        shadow = hostRef.current.attachShadow({ mode: 'open' });
        shadowRef.current = shadow;
      } else {
        shadow = shadowRef.current;
      }

      // Create container for React content
      const container = document.createElement('div');
      container.className = `formio-shadow-container ${className}`;
      shadow.appendChild(container);
      console.log('FormioShadowWrapper: Container created and appended');

      // Copy all stylesheets from the light DOM into shadow DOM
      console.log('FormioShadowWrapper: Copying all stylesheets from light DOM...');
      
      // Get all stylesheets from the document
      const stylesheets = Array.from(document.styleSheets);
      
      for (const stylesheet of stylesheets) {
        try {
          const style = document.createElement('style');
          
          // Try to get CSS rules from the stylesheet
          if (stylesheet.cssRules) {
            const cssText = Array.from(stylesheet.cssRules)
              .map(rule => rule.cssText)
              .join('\n');
            style.textContent = cssText;
          } else if (stylesheet.href) {
            // For external stylesheets, create a link element
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = stylesheet.href;
            shadow.appendChild(link);
            continue;
          }
          
          shadow.appendChild(style);
          console.log('FormioShadowWrapper: Copied stylesheet with', style.textContent?.length || 0, 'characters');
        } catch (error) {
          console.warn('FormioShadowWrapper: Could not copy stylesheet:', error);
          
          // Fallback: try to create a link if it's an external stylesheet
          if (stylesheet.href) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = stylesheet.href;
            shadow.appendChild(link);
            console.log('FormioShadowWrapper: Added external stylesheet link:', stylesheet.href);
          }
        }
      }
      
      // Add our custom shadow DOM styles on top
      const customStyle = document.createElement('style');
      customStyle.textContent = getShadowCSS();
      shadow.appendChild(customStyle);
      console.log('FormioShadowWrapper: Added custom shadow DOM styles');

      // Set up event forwarding for drag-and-drop
      console.log('FormioShadowWrapper: Setting up drag-and-drop event forwarding...');
      const cleanupDragDrop = setupDragDropEventForwarding(shadow, hostRef.current);
      
      // Store cleanup function for later
      (hostRef.current as any)._dragDropCleanup = cleanupDragDrop;

      // Create React root and render children
      console.log('FormioShadowWrapper: Creating React root...');
      const root = ReactDOM.createRoot(container);
      rootRef.current = root;
      
      console.log('FormioShadowWrapper: Rendering children...', children);
      root.render(children);

      // Set up document and element access for drag libraries
      setTimeout(() => {
        setupFormioBuilderDragSupport(shadow, container);
      }, 500); // Increased delay to let FormIO fully initialize

      // Call onReady callback
      if (onReady) {
        setTimeout(() => {
          console.log('FormioShadowWrapper: Calling onReady callback');
          onReady();
        }, 100);
      }

    } catch (error) {
      console.error('FormioShadowWrapper: Error creating shadow DOM:', error);
    }
  }, [className, getShadowCSS, onReady]); // Removed children from dependencies

  const destroyShadowDOM = useCallback(() => {
    // Cleanup drag-and-drop event handlers
    if (hostRef.current && (hostRef.current as any)._dragDropCleanup) {
      try {
        (hostRef.current as any)._dragDropCleanup();
        delete (hostRef.current as any)._dragDropCleanup;
      } catch (error) {
        console.error('FormioShadowWrapper: Error cleaning up drag-drop handlers:', error);
      }
    }

    if (rootRef.current) {
      try {
        rootRef.current.unmount();
      } catch (error) {
        console.error('FormioShadowWrapper: Error unmounting React root:', error);
      }
      rootRef.current = null;
    }
    
    shadowRef.current = null;
  }, []);

  // Create shadow DOM on mount
  useEffect(() => {
    console.log('FormioShadowWrapper: Mount effect - creating shadow DOM...');
    createShadowDOM();
    return destroyShadowDOM;
  }, []); // Empty dependency array - only run on mount/unmount

  // Update children when they change
  useEffect(() => {
    if (rootRef.current && shadowRef.current) {
      console.log('FormioShadowWrapper: Updating children in shadow DOM...');
      try {
        rootRef.current.render(children);
      } catch (error) {
        console.error('FormioShadowWrapper: Error updating children:', error);
      }
    } else if (shadowRef.current && !rootRef.current) {
      // Shadow DOM exists but no React root - recreate
      console.log('FormioShadowWrapper: Shadow DOM exists but no React root - recreating...');
      createShadowDOM();
    }
  }, [children]); // Only depend on children

  return (
    <div 
      ref={hostRef} 
      style={{ 
        height: '100%', 
        width: '100%',
        minHeight: '500px',
        position: 'relative'
      }} 
      data-testid="formio-shadow-wrapper"
    >
      {/* Fallback content - should be hidden by shadow DOM */}
      <div style={{ 
        position: 'absolute', 
        top: '50%', 
        left: '50%', 
        transform: 'translate(-50%, -50%)',
        color: '#999',
        fontSize: '14px' 
      }}>
        Shadow DOM Loading...
      </div>
    </div>
  );
};

export default FormioShadowWrapper;