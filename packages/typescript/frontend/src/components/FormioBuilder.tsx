import React, { useEffect, useRef } from 'react';
import { Templates } from '@tsed/react-formio';
import { FormBuilder } from 'formiojs';
import type { Form } from 'formiojs';

interface FormioBuilderProps {
  jsonFormio?: string;
  onChange?: (schema: Form | object) => void;
  readOnly?: boolean;
}

interface FormWithComponents extends Form {
  components: unknown[];
}

interface FormBuilderWithReadOnly extends FormBuilder {
  readOnly?: boolean;
}

const FormioBuilder: React.FC<FormioBuilderProps> = ({ jsonFormio, onChange, readOnly = false }) => {
  const builderRef = useRef<HTMLDivElement>(null);
  const builderInstance = useRef<FormBuilder | null>(null);
  const onChangeRef = useRef(onChange);
  const isInitializing = useRef(false);
  const lastJsonFormio = useRef<string>('');
  const isUpdatingFromProps = useRef(false);
  const isTabSwitching = useRef(false);
  const changeTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const handleBuilderClickRef = useRef<((event: Event) => void) | null>(null);

  // Keep the onChange ref updated
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    // Ensure we're using the Tailwind template
    Templates.framework = 'tailwind';

    if (!builderRef.current) return;

    // Normalize jsonFormio for comparison (handle undefined/null)
    const currentJsonFormio = jsonFormio || '';
    
    // Recreate if jsonFormio changed or readOnly changed
    if (currentJsonFormio === lastJsonFormio.current && builderInstance.current) {
      // If only readOnly changed, update the existing builder
      const builderWithReadOnly = builderInstance.current as FormBuilderWithReadOnly;
      if (builderWithReadOnly && typeof builderWithReadOnly.readOnly !== 'undefined') {
        builderWithReadOnly.readOnly = readOnly;
      }
      return;
    }
    
    lastJsonFormio.current = currentJsonFormio;

    // Capture the current element reference for listener add/remove and cleanup
    const builderElement = builderRef.current;

    // Destroy existing builder if it exists
    if (builderInstance.current) {
      builderInstance.current.destroy();
      builderInstance.current = null;
    }

    isInitializing.current = true;
    isUpdatingFromProps.current = true;

    // Parse the form data
    let form = {};
    if (currentJsonFormio.trim() !== '') {
      try {
        const parsedComponents = JSON.parse(currentJsonFormio);
        form = { components: parsedComponents };
      } catch (error) {
        console.error('Error parsing jsonFormio:', error);
        form = { components: [] };
      }
    }

    // Create the Formio builder using the captured element
    const builder = new FormBuilder(builderElement, form, {
      readOnly: readOnly
    });
    builderInstance.current = builder;
    
    // Listen to the correct FormBuilder events
    const handleFormChange = () => {
      // Don't trigger onChange if we're updating from props to prevent loops
      if (onChangeRef.current && !isInitializing.current && !isUpdatingFromProps.current && !isTabSwitching.current) {
        // Clear any existing timeout
        if (changeTimeoutRef.current) {
          clearTimeout(changeTimeoutRef.current);
        }

        // Debounce the change to prevent rapid updates during tab switching
        changeTimeoutRef.current = setTimeout(() => {
          const currentForm: FormWithComponents = (builder as FormBuilder & { _form: FormWithComponents })._form;
          const currentComponents = JSON.stringify(currentForm.components);
          
          // Only call onChange if the components actually changed from what we have
          if (currentComponents !== lastJsonFormio.current && onChangeRef.current) {
            onChangeRef.current(currentForm.components);
          }
        }, 100);
      }
    };

    // Listen via the events emitter directly
    if (builder.events) {
      (builder.events as { on: (event: string, handler: () => void) => void }).on('formio.change', handleFormChange);
      (builder.events as { on: (event: string, handler: () => void) => void }).on('componentChange', handleFormChange);
    }

    // Set up tab switching detection
    const handleTabClick = () => {
      isTabSwitching.current = true;
      setTimeout(() => {
        isTabSwitching.current = false;
      }, 500);
    };

    // Also track clicks within the builder area (captured locally for cleanup)
    const handleBuilderClick = (event: Event) => {
      const target = event.target as HTMLElement;
      if (target.closest('.nav-link, .nav-item a, [role="tab"]')) {
        handleTabClick();
      }
    };
    handleBuilderClickRef.current = handleBuilderClick;

    // Listen for tab clicks in the builder using the captured element
    if (builderElement) {
      const tabElements = builderElement.querySelectorAll('.nav-link, .nav-item a, [role="tab"]');
      tabElements.forEach(tab => {
        tab.addEventListener('click', handleTabClick);
      });
      builderElement.addEventListener('click', handleBuilderClick);
    }

    // Trigger initial change after builder is ready to sync the actual form structure
    setTimeout(() => {
      isInitializing.current = false;
      isUpdatingFromProps.current = false;
    }, 100);

    // Cleanup on unmount or when jsonFormio changes
    return () => {
      if (changeTimeoutRef.current) {
        clearTimeout(changeTimeoutRef.current);
      }

      // Remove event listeners using captured references
      if (builderElement) {
        const tabElements = builderElement.querySelectorAll('.nav-link, .nav-item a, [role="tab"]');
        tabElements.forEach(tab => {
          tab.removeEventListener('click', handleTabClick);
        });
        if (handleBuilderClickRef.current) {
          builderElement.removeEventListener('click', handleBuilderClickRef.current);
        }
      }

      // Destroy the specific builder created by this effect run
      builder.destroy();
      builderInstance.current = null;
    };
  }, [jsonFormio, readOnly]);

  return <div ref={builderRef} />;
};

export default FormioBuilder;
