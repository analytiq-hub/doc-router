import React, { useEffect, useRef } from 'react';
import { Templates } from '@tsed/react-formio';
import { FormBuilder } from 'formiojs';
import type { Form } from 'formiojs';

interface FormioBuilderProps {
  jsonFormio?: string;
  onChange?: (schema: Form | object) => void;
}

interface FormWithComponents extends Form {
  components: unknown[];
}

const FormioBuilder: React.FC<FormioBuilderProps> = ({ jsonFormio, onChange }) => {
  const builderRef = useRef<HTMLDivElement>(null);
  const builderInstance = useRef<FormBuilder | null>(null);
  const onChangeRef = useRef(onChange);
  const isInitializing = useRef(false);
  const lastJsonFormio = useRef<string>('');
  const isUpdatingFromProps = useRef(false);

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
    
    // Only recreate if jsonFormio actually changed
    if (currentJsonFormio === lastJsonFormio.current) return;
    
    lastJsonFormio.current = currentJsonFormio;

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
        console.error('FormioBuilder: Error parsing jsonFormio:', error);
        form = { components: [] };
      }
    }

    // Create the Formio builder
    const builder = new FormBuilder(builderRef.current, form, {});
    builderInstance.current = builder;
    
    // Listen to the correct FormBuilder events
    const handleFormChange = () => {
      // Don't trigger onChange if we're updating from props to prevent loops
      if (onChangeRef.current && !isInitializing.current && !isUpdatingFromProps.current) {
        const currentForm: FormWithComponents = (builder as FormBuilder & { _form: FormWithComponents })._form;
        const currentComponents = JSON.stringify(currentForm.components);
        
        // Only call onChange if the components actually changed from what we have
        if (currentComponents !== lastJsonFormio.current) {
          onChangeRef.current(currentForm.components);
        }
      }
    };

    // Listen via the events emitter directly
    if (builder.events) {
      (builder.events as { on: (event: string, handler: () => void) => void }).on('formio.change', handleFormChange);
    }

    // Trigger initial change after builder is ready to sync the actual form structure
    setTimeout(() => {
      isInitializing.current = false;
      isUpdatingFromProps.current = false;
    }, 100);

    // Cleanup on unmount
    return () => {
      if (builderInstance.current) {
        builderInstance.current.destroy();
        builderInstance.current = null;
      }
    };
  }, [jsonFormio]);

  return <div ref={builderRef} />;
};

export default FormioBuilder;
