import React, { useEffect, useRef } from 'react';
import { Templates } from '@tsed/react-formio';
import { Form } from 'formiojs';

interface FormioRendererProps {
  jsonFormio?: string;
  onSubmit?: (submission: unknown) => void;
  readOnly?: boolean;
  initialData?: Record<string, unknown>;
  onFieldSearch?: (fieldValue: string) => void;
}

const FormioRenderer: React.FC<FormioRendererProps> = ({ 
  jsonFormio, 
  onSubmit, 
  readOnly = false,
  initialData,
  onFieldSearch 
}) => {
  const formRef = useRef<HTMLDivElement>(null);
  const formInstance = useRef<Form | null>(null);

  useEffect(() => {
    Templates.framework = 'tailwind';

    if (!formRef.current) return;

    if (formInstance.current) {
      formInstance.current.destroy();
      formInstance.current = null;
    }

    let form = {};
    if (jsonFormio && jsonFormio.trim() !== '') {
      try {
        const parsedComponents = JSON.parse(jsonFormio);
        form = { components: parsedComponents };
      } catch (error) {
        console.error('Error parsing jsonFormio:', error);
        form = { components: [] };
      }
    }

    const formioForm = new Form(formRef.current, form, {
      readOnly: readOnly,
      noAlerts: true,
      noValidate: false,
      disableAlerts: true,
      hooks: {
        beforeSubmit: (submission: unknown, next: (submission?: unknown) => void) => {
          if (onSubmit) {
            onSubmit(submission);
          }
          next();
        },
      }
    });
    
    // Wait for form to be ready, then set up listeners
    formioForm.ready.then(() => {
      console.log('Form ready');
      
      // Redraw is now handled automatically after custom button execution
      // No general change listener needed

      // Set initial data properly
      if (initialData) {
        console.log('Setting initial data:', initialData);
        console.log('Form instance:', formioForm);
        formioForm.instance.submission = initialData;
      }
    }).catch((error) => {
      console.error('Error waiting for form ready:', error);
    });

    formInstance.current = formioForm;

    // Add search icons after form is rendered
    if (onFieldSearch) {
      const addSearchIcons = () => {
        const formElement = formRef.current;
        if (!formElement) return;

        // Find all form field labels
        const labels = formElement.querySelectorAll('label[class*="formio"], .formio-label, label[for]');
        
        labels.forEach((label) => {
          // Skip if already has search icon
          if (label.querySelector('.search-icon')) return;
          
          // Create search icon
          const searchIcon = document.createElement('button');
          searchIcon.type = 'button';
          searchIcon.tabIndex = -1; // Prevent focus via tab navigation
          searchIcon.className = 'search-icon ml-1 text-primary-600 hover:text-primary-800 inline-flex items-center';
          searchIcon.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="rgb(156, 163, 175)" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
          `;
          
          searchIcon.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Find the corresponding input field
            const fieldContainer = label.closest('.formio-component, .form-group');
            const input = fieldContainer?.querySelector('input, textarea, select') as HTMLInputElement;
            const fieldValue = input?.value;
            
            if (fieldValue && fieldValue.trim()) {
              onFieldSearch(fieldValue.trim());
            } else {
              // If no value, search for the label text
              const labelText = label.textContent?.replace('*', '').trim();
              if (labelText) {
                onFieldSearch(labelText);
              }
            }
          };
          
          // Add icon to label
          label.appendChild(searchIcon);
        });
      };

      // Add icons after form is ready
      setTimeout(addSearchIcons, 200);
      
      // Also add icons when form data changes
      const observer = new MutationObserver(addSearchIcons);
      observer.observe(formRef.current, { childList: true, subtree: true });
      
      return () => observer.disconnect();
    }

    return () => {
      if (formInstance.current) {
        formInstance.current.destroy();
        formInstance.current = null;
      }
    };
  }, [jsonFormio, onSubmit, readOnly, initialData, onFieldSearch]);

  return <div ref={formRef} />;
};

export default FormioRenderer; 