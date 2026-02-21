import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { 
  ArrowPathIcon,
  DocumentTextIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import { DocRouterOrgApi } from '@/utils/api';
import type { Form } from '@docrouter/sdk';
import { useOCR, OCRProvider } from '@/contexts/OCRContext';
import type { HighlightInfo } from '@/contexts/OCRContext';
import dynamic from 'next/dynamic';

const FormioRenderer = dynamic(() => import('./FormioRenderer'), {
  ssr: false,
  loading: () => <div className="h-32 flex items-center justify-center">Loading form...</div>
});
import { toast } from 'react-toastify';
import { getApiErrorMsg } from '@/utils/api';
import type { FormSubmission, FieldMapping, FieldMappingSource } from '@docrouter/sdk';
import type { GetLLMResultResponse } from '@docrouter/sdk';

interface Props {
  organizationId: string;
  id: string;
  onHighlight: (highlight: HighlightInfo) => void;
  onClearHighlight?: () => void;
}

const PDFFormSidebarContent = ({ organizationId, id, onHighlight }: Props) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const { loadOCRBlocks, findBlocksWithContext } = useOCR();
  
  // Form-related state
  const [documentTags, setDocumentTags] = useState<string[]>([]);
  const [availableForms, setAvailableForms] = useState<Form[]>([]);
  const [loadingForms, setLoadingForms] = useState(false);
  const [submittingForms, setSubmittingForms] = useState<Set<string>>(new Set());
  const [existingSubmissions, setExistingSubmissions] = useState<Record<string, FormSubmission>>({});
  const [loadingSubmissions, setLoadingSubmissions] = useState<Set<string>>(new Set());
  const loadingSubmissionsRef = useRef<Set<string>>(new Set());
  const [deletingSubmissions, setDeletingSubmissions] = useState<Set<string>>(new Set());
  const [llmResults, setLlmResults] = useState<Record<string, GetLLMResultResponse>>({});
  const [llmResultsLoading, setLlmResultsLoading] = useState<Set<string>>(new Set());
  const [llmResultsFailed, setLlmResultsFailed] = useState<Set<string>>(new Set());
  const [formInitialData, setFormInitialData] = useState<Record<string, Record<string, unknown>>>({});
  const [documentName, setDocumentName] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      // Get document metadata only (no file content) for tags and name (single request)
      const documentResponse = await docRouterOrgApi.getDocument({
        documentId: id,
        fileType: 'original',
        includeContent: false
      });

      setDocumentName(documentResponse.document_name ?? null);
      const documentTags = documentResponse.tag_ids || [];
      setDocumentTags(documentTags);

      // Fetch forms that match the document's tags
      if (documentTags.length > 0) {
        setLoadingForms(true);
        try {
          const formsResponse = await docRouterOrgApi.listForms({
            tag_ids: documentTags.join(','),
            limit: 100
          });
          setAvailableForms(formsResponse.forms);
        } catch (error) {
          console.error('Error loading forms:', error);
          toast.error(`Error loading forms: ${getApiErrorMsg(error)}`);
        } finally {
          setLoadingForms(false);
        }
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error(`Error loading document data: ${getApiErrorMsg(error)}`);
    }
  }, [id, docRouterOrgApi]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    // Load OCR blocks in the background (only if OCR is supported)
    if (documentName) {
      loadOCRBlocks(organizationId, id, documentName);
    }
  }, [id, organizationId, documentName, loadOCRBlocks]);

  // Add function to load existing submission for a form
  const loadExistingSubmission = useCallback(async (formRevId: string) => {
    if (loadingSubmissionsRef.current.has(formRevId)) return;
    
    loadingSubmissionsRef.current.add(formRevId);
    setLoadingSubmissions(prev => new Set(prev).add(formRevId));
    
    try {
      const submission = await docRouterOrgApi.getFormSubmission({
        documentId: id,
        formRevId
      });
      
      if (submission) {
        setExistingSubmissions(prev => ({
          ...prev,
          [formRevId]: submission
        }));

        // Update initial data state with existing submission data (only if not already set)
        if (!formInitialData[formRevId]) {
          console.log(`📥 Setting initial data from EXISTING SUBMISSION for form ${formRevId}:`, submission.submission_data);
          setFormInitialData(prev => ({
            ...prev,
            [formRevId]: submission.submission_data || {}
          }));
        }
        
        console.log('submission', submission);
      }
    } catch (error) {
      console.error('Error loading existing submission:', error);
    } finally {
      loadingSubmissionsRef.current.delete(formRevId);
      setLoadingSubmissions(prev => {
        const newSet = new Set(prev);
        newSet.delete(formRevId);
        return newSet;
      });
    }
  }, [id, formInitialData, docRouterOrgApi]);

  // Helper function to get value from nested object using path
  const getValueFromPath = (obj: Record<string, unknown>, path: string): unknown => {
    const parts = path.split('.');
    let current: unknown = obj;
    
    for (const part of parts) {
      const arrayMatch = part.match(/^(.+)\[(\d+)\]$/);
      if (arrayMatch) {
        const [, fieldName, index] = arrayMatch;
        if (current && typeof current === 'object' && fieldName in current) {
          const fieldValue = (current as Record<string, unknown>)[fieldName];
          if (Array.isArray(fieldValue)) {
            current = fieldValue[parseInt(index)];
          } else {
            current = undefined;
          }
        } else {
          current = undefined;
        }
      } else {
        if (current && typeof current === 'object' && part in current) {
          current = (current as Record<string, unknown>)[part];
        } else {
          current = undefined;
        }
      }
      
      if (current === null || current === undefined) {
        return undefined;
      }
    }
    
    return current;
  };

  // Generate initial form data from LLM results and mappings
  const generateInitialFormData = useCallback((form: Form): Record<string, unknown> => {
    console.log(`Generating initial data for form ${form.name}`);
    const mappings = form.response_format.json_formio_mapping;
    if (!mappings) {
      console.log(`No mappings found for form ${form.name}`);
      return {};
    }

    console.log(`Form ${form.name} mappings:`, mappings);
    console.log(`Available LLM results:`, llmResults);

    const initialData: Record<string, unknown> = {};

    Object.entries(mappings).forEach(([formFieldKey, mapping]: [string, FieldMapping]) => {
      console.log(`Processing field ${formFieldKey}:`, mapping);
      const values: string[] = [];

      mapping.sources.forEach((source: FieldMappingSource) => {
        const llmResult = llmResults[source.promptRevId];
        console.log(`LLM result for prompt ${source.promptRevId}:`, llmResult);
        
        if (llmResult) {
          const resultData = llmResult.is_edited ? llmResult.updated_llm_result : llmResult.llm_result;
          console.log(`Result data for path ${source.schemaFieldPath}:`, resultData);
          
          const value = getValueFromPath(resultData as Record<string, unknown>, source.schemaFieldPath);
          console.log(`Extracted value:`, value);
          
          if (value !== null && value !== undefined) {
            const stringValue = typeof value === 'object' ? JSON.stringify(value) : String(value);
            values.push(stringValue);
            console.log(`Added value: ${stringValue}`);
          }
        }
      });

      if (values.length > 0) {
        if (mapping.mappingType === 'concatenated' && values.length > 1) {
          initialData[formFieldKey] = values.join(mapping.concatenationSeparator || ' ');
        } else {
          initialData[formFieldKey] = values[0];
        }
        console.log(`Set field ${formFieldKey} = ${initialData[formFieldKey]}`);
      } else {
        console.log(`No values found for field ${formFieldKey}`);
      }
    });

    console.log(`Final initial data for form ${form.name}:`, initialData);
    return initialData;
  }, [llmResults]);

  // Update form initial data when LLM results are loaded
  const updateFormInitialDataFromLLM = useCallback(() => {
    console.log('🔄 updateFormInitialDataFromLLM called');
    console.log('Available forms:', availableForms.map(f => f.name));
    console.log('Current llmResults keys:', Object.keys(llmResults));
    
    availableForms.forEach(form => {
      console.log(`Processing form ${form.name} (${form.form_revid})`);
      
      // Skip if form has existing submission (don't overwrite user-submitted data)
      if (existingSubmissions[form.form_revid]) {
        console.log(`Skipping ${form.name} - has existing submission, won't overwrite`);
        return;
      }
      
      // Generate initial data from LLM results
      const llmInitialData = generateInitialFormData(form);
      
      console.log(`Generated data for ${form.name}:`, llmInitialData);
      console.log(`Data length: ${Object.keys(llmInitialData).length}`);
      
      // Always update to support multiple LLM results
      if (Object.keys(llmInitialData).length > 0) {
        setFormInitialData(prev => {
          console.log('Current formInitialData keys:', Object.keys(prev));
          const existingData = prev[form.form_revid];
          
          // Merge with existing data if it exists
          const mergedData = existingData && typeof existingData.data === 'object' && existingData.data ? 
            { ...(existingData.data as Record<string, unknown>), ...llmInitialData } : // Merge field data
            llmInitialData; // Use new data
          
          // Format LLM data to match Form.io submission structure
          const formattedData = {
            data: mergedData,
            metadata: existingData?.metadata || {},
            state: "draft"
          };
          
          if (existingData) {
            console.log(`🔄 Merging additional LLM data for form ${form.name}:`, formattedData);
          } else {
            console.log(`🤖 Setting initial data from LLM OUTPUT for form ${form.name}:`, formattedData);
          }
          
          return {
            ...prev,
            [form.form_revid]: formattedData
          };
        });
      } else {
        setFormInitialData(prev => {
          // Only set empty data if no data exists yet
          if (!prev[form.form_revid]) {
            console.log(`⚠️ Setting empty initial data for form ${form.name} (no LLM data available)`);
            return {
              ...prev,
              [form.form_revid]: { data: {}, metadata: {}, state: "draft" }
            };
          }
          return prev; // No change needed
        });
      }
    });
  }, [availableForms, generateInitialFormData, llmResults, existingSubmissions]);

  // Track which LLM results we've already processed to avoid infinite loops
  const processedLlmResults = useRef<Set<string>>(new Set());
  
  // Automatically update form initial data when NEW LLM results are added
  useEffect(() => {
    const currentLlmKeys = Object.keys(llmResults);
    const newLlmKeys = currentLlmKeys.filter(key => !processedLlmResults.current.has(key));
    
    if (newLlmKeys.length > 0) {
      console.log('🔄 New LLM results detected:', newLlmKeys, 'triggering form data update');
      
      // Mark these as processed
      newLlmKeys.forEach(key => processedLlmResults.current.add(key));
      
      // Update form data
      updateFormInitialDataFromLLM();
    }
  }, [llmResults, updateFormInitialDataFromLLM]);
  
  // Load LLM result for a specific prompt
  const loadLLMResult = useCallback(async (promptRevId: string) => {
    if (llmResults[promptRevId] || llmResultsLoading.has(promptRevId) || llmResultsFailed.has(promptRevId)) {
      return; // Already loaded, loading, or failed
    }

    setLlmResultsLoading(prev => new Set(prev).add(promptRevId));
    
    try {
      const result = await docRouterOrgApi.getLLMResult({
        documentId: id,
        promptRevId: promptRevId,
        fallback: true
      });
      
      setLlmResults(prev => ({
        ...prev,
        [promptRevId]: result
      }));
      
      console.log(`✅ LLM result loaded for prompt ${promptRevId}: ${JSON.stringify(result)}`);
    } catch (error) {
      console.info(`❌ LLM result failed for prompt ${promptRevId}: ${error instanceof Error ? error.message : String(error)}`);
      
      // Mark as failed to prevent infinite retries
      setLlmResultsFailed(prev => new Set(prev).add(promptRevId));
    } finally {
      setLlmResultsLoading(prev => {
        const newSet = new Set(prev);
        newSet.delete(promptRevId);
        return newSet;
      });
    }
  }, [id, llmResults, llmResultsLoading, llmResultsFailed, docRouterOrgApi]);



  // Check if a form needs LLM data and if it's ready to render
  const isFormReadyToRender = useCallback((form: Form): boolean => {
    console.log(`Checking if form ${form.name} is ready to render`);
    
    // If there's an existing submission, always render
    if (existingSubmissions[form.form_revid]) {
      console.log(`Form ${form.name} has existing submission - ready to render`);
      return true;
    }

    // If there are no mappings, render immediately
    const mappings = form.response_format.json_formio_mapping;
    if (!mappings) {
      console.log(`Form ${form.name} has no mappings - ready to render`);
      return true;
    }

    // Check if all required LLM results are loaded
    const requiredPromptRevIds = new Set<string>();
    Object.values(mappings).forEach((mapping: FieldMapping) => {
      mapping.sources.forEach((source: FieldMappingSource) => {
        requiredPromptRevIds.add(source.promptRevId);
      });
    });

    console.log(`Form ${form.name} requires LLM results for prompts:`, Array.from(requiredPromptRevIds));
    console.log(`Current LLM results:`, Object.keys(llmResults));
    console.log(`Currently loading:`, Array.from(llmResultsLoading));
    console.log(`Failed LLM results:`, Array.from(llmResultsFailed));

    // All required prompts must be either loaded successfully OR failed (don't wait for non-existent data)
    const isReady = Array.from(requiredPromptRevIds).every(promptRevId => 
      (llmResults[promptRevId] && !llmResultsLoading.has(promptRevId)) || // Successfully loaded
      llmResultsFailed.has(promptRevId) // Failed to load (don't wait forever)
    );
    
    console.log(`Form ${form.name} ready to render:`, isReady);
    return isReady;
  }, [existingSubmissions, llmResults, llmResultsLoading, llmResultsFailed]);

  // Add useEffect to load existing submissions when forms are loaded
  useEffect(() => {
    if (availableForms.length > 0) {
      availableForms.forEach(form => {
        loadExistingSubmission(form.form_revid);
      });
    }
  }, [availableForms, loadExistingSubmission]);

  // Separate useEffect to load LLM results to avoid infinite loop
  useEffect(() => {
    if (availableForms.length > 0) {
      availableForms.forEach(form => {
        // Load LLM results if form has mappings and no existing submission
        if (!existingSubmissions[form.form_revid]) {
          const mappings = form.response_format.json_formio_mapping;
          if (mappings) {
            const requiredPromptRevIds = new Set<string>();
            Object.values(mappings).forEach((mapping: FieldMapping) => {
              mapping.sources.forEach((source: FieldMappingSource) => {
                requiredPromptRevIds.add(source.promptRevId);
              });
            });
            
            // Load each required LLM result
            requiredPromptRevIds.forEach(promptRevId => {
              loadLLMResult(promptRevId);
            });
          }
        }
      });
    }
  }, [availableForms, existingSubmissions, loadLLMResult]); // Removed loadExistingSubmission to prevent loop

  // Form handling functions
  const handleFormSubmit = async (form: Form, submissionData: unknown) => {
    setSubmittingForms(prev => new Set(prev).add(form.form_revid));

    try {
      const result = await docRouterOrgApi.submitForm({
        documentId: id,
        formRevId: form.form_revid,
        submission_data: submissionData as Record<string, unknown>
      });

      // Update the existing submissions state with the new submission
      setExistingSubmissions(prev => ({
        ...prev,
        [form.form_revid]: result
      }));

      // Update initial data state with submission data (only if not already set)
      if (!formInitialData[form.form_revid]) {
        console.log(`🔄 Setting initial data from NEW SUBMISSION for form ${form.name}:`, result.submission_data);
        setFormInitialData(prev => ({
          ...prev,
          [form.form_revid]: result.submission_data || {}
        }));
      }

    } catch (error) {
      console.error('Error submitting form:', error);
      toast.error(`Error submitting form: ${getApiErrorMsg(error)}`);
    } finally {
      setSubmittingForms(prev => {
        const newSet = new Set(prev);
        newSet.delete(form.form_revid);
        return newSet;
      });
    }
  };

  const handleDeleteSubmission = async (formRevId: string) => {
    if (!existingSubmissions[formRevId]) return;
    
    setDeletingSubmissions(prev => new Set(prev).add(formRevId));

    try {
      await docRouterOrgApi.deleteFormSubmission({
        documentId: id,
        formRevId
      });

      // Remove from existing submissions state
      setExistingSubmissions(prev => {
        const newSubmissions = { ...prev };
        delete newSubmissions[formRevId];
        return newSubmissions;
      });

    } catch (error) {
      console.error('Error deleting submission:', error);
      toast.error(`Error deleting submission: ${getApiErrorMsg(error)}`);
    } finally {
      setDeletingSubmissions(prev => {
        const newSet = new Set(prev);
        newSet.delete(formRevId);
        return newSet;
      });
    }
  };

  // Add this function to handle form field search
  const handleFormFieldSearch = (fieldValue: string) => {
    if (!fieldValue || typeof fieldValue !== 'string') {
      toast.info('No text to search');
      return;
    }
    
    const highlightInfo = findBlocksWithContext(fieldValue, 'form', 'field');
    if (highlightInfo.blocks.length > 0) {
      onHighlight(highlightInfo);
    } else {
      toast.info('No matching text found in document');
    }
  };

  return (
    <div className="h-full overflow-y-auto p-4 space-y-6">
      {/* Forms Section */}
      <div>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <DocumentTextIcon className="h-5 w-5" />
          Forms
        </h3>
        
        {loadingForms ? (
          <div className="flex items-center justify-center py-8">
            <ArrowPathIcon className="h-6 w-6 animate-spin text-gray-500" />
            <span className="ml-2 text-gray-500">Loading forms...</span>
          </div>
        ) : availableForms.length > 0 ? (
          <div className="space-y-4">
            {availableForms.map((form) => (
              <div key={form.form_revid} className="border rounded-lg p-4 bg-white">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-semibold text-sm">{form.name}</h4>
                  <div className="flex items-center gap-2">
                    {loadingSubmissions.has(form.form_revid) && (
                      <ArrowPathIcon className="h-4 w-4 animate-spin text-blue-500" />
                    )}
                    {existingSubmissions[form.form_revid] && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-green-600 bg-green-100 px-2 py-1 rounded">
                          Previously submitted
                        </span>
                        <button
                          onClick={() => handleDeleteSubmission(form.form_revid)}
                          disabled={deletingSubmissions.has(form.form_revid)}
                          className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50"
                          title="Delete submission"
                        >
                          {deletingSubmissions.has(form.form_revid) ? (
                            <ArrowPathIcon className="h-3 w-3 animate-spin" />
                          ) : (
                            <XMarkIcon className="h-3 w-3" />
                          )}
                        </button>
                      </div>
                    )}
                    {submittingForms.has(form.form_revid) && (
                      <ArrowPathIcon className="h-4 w-4 animate-spin text-blue-500" />
                    )}
                  </div>
                </div>
                
                {isFormReadyToRender(form) ? (
                  <FormioRenderer
                    jsonFormio={JSON.stringify(form.response_format.json_formio || [])}
                    onSubmit={(submission) => handleFormSubmit(form, submission)}
                    readOnly={submittingForms.has(form.form_revid)}
                    initialData={formInitialData[form.form_revid] || {}}
                    onFieldSearch={handleFormFieldSearch}
                  />
                ) : (
                  <div className="flex items-center justify-center py-8">
                    <ArrowPathIcon className="h-4 w-4 animate-spin text-blue-500" />
                    <span className="ml-2 text-gray-500">Loading form data...</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : documentTags.length > 0 ? (
          <div className="text-center py-8 text-gray-500">
            <DocumentTextIcon className="h-12 w-12 mx-auto mb-2 text-gray-300" />
            <p>No forms found for this document&apos;s tags</p>
            <p className="text-sm mt-1">Create forms with matching tags to see them here</p>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <DocumentTextIcon className="h-12 w-12 mx-auto mb-2 text-gray-300" />
            <p>No tags assigned to this document</p>
            <p className="text-sm mt-1">Add tags to the document to see relevant forms</p>
          </div>
        )}
      </div>
    </div>
  );
};

const PDFFormSidebar = (props: Props) => {
  return (
    <OCRProvider>
      <PDFFormSidebarContent {...props} />
    </OCRProvider>
  );
};

export default PDFFormSidebar;
