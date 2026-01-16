'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import { Form } from '@docrouter/sdk';

// Type alias for form creation/update (without id and timestamps)
type FormConfig = Omit<Form, 'form_revid' | 'form_id' | 'form_version' | 'created_at' | 'created_by'>;
import { Tag } from '@docrouter/sdk';
import { getApiErrorMsg } from '@/utils/api';
import TagSelector from './TagSelector';
import { toast } from 'react-toastify';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';

const FormioBuilder = dynamic(() => import('./FormioBuilder'), {
  ssr: false,
  loading: () => <div className="h-64 flex items-center justify-center">Loading form builder...</div>
});

const FormioMapper = dynamic(() => import('./FormioMapper'), {
  ssr: false,
  loading: () => <div className="h-64 flex items-center justify-center">Loading form mapper...</div>
});

const Editor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => <div className="h-64 flex items-center justify-center">Loading editor...</div>
});
import InfoTooltip from '@/components/InfoTooltip';
import { FormComponent } from '@/types/ui';
import BadgeIcon from '@mui/icons-material/Badge';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import FormInfoModal from './FormInfoModal';
import FormVersionSelector from './FormVersionSelector';
import FormVersionCompareModal from './FormVersionCompareModal';
import FormDiffView from './FormDiffView';

const FormCreate: React.FC<{ organizationId: string, formId?: string }> = ({ organizationId, formId }) => {
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [currentFormId, setCurrentFormId] = useState<string | null>(null);
  const [currentFormFull, setCurrentFormFull] = useState<Form | null>(null);
  const [viewingVersion, setViewingVersion] = useState<number | null>(null);
  const [isReadOnly, setIsReadOnly] = useState(false);
  const [currentForm, setCurrentForm] = useState<FormConfig>({
    name: '',
    response_format: {
      json_formio: [],
      json_formio_mapping: {}
    },
    tag_ids: [] // Initialize with empty array
  });
  const [isLoading, setIsLoading] = useState(false);
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<'builder' | 'mapper' | 'json'>('builder');
  const [jsonForm, setJsonForm] = useState('');
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const [diffLeft, setDiffLeft] = useState<Form | null>(null);
  const [diffRight, setDiffRight] = useState<Form | null>(null);

  // Load editing form if available
  useEffect(() => {
    const loadForm = async () => {
      if (formId) {
        try {
          setIsLoading(true);
          const form = await docRouterOrgApi.getForm({ formRevId: formId });
          setCurrentFormId(form.form_id);
          setCurrentFormFull(form);
          setViewingVersion(form.form_version);
          // Check if this is the latest version
          const versionsResponse = await docRouterOrgApi.listFormVersions({ formId: form.form_id });
          const latestVersion = versionsResponse.forms.sort((a, b) => b.form_version - a.form_version)[0];
          setIsReadOnly(form.form_version !== latestVersion.form_version);
          setCurrentForm({
            name: form.name,
            response_format: {
              ...form.response_format,
              json_formio_mapping: form.response_format.json_formio_mapping || {}
            },
            tag_ids: form.tag_ids || []
          });
          setSelectedTagIds(form.tag_ids || []);
        } catch (error) {
          toast.error(`Error loading form for editing: ${getApiErrorMsg(error)}`);
        } finally {
          setIsLoading(false);
        }
      }
    };
    loadForm();
  }, [formId, docRouterOrgApi]);

  const loadTags = useCallback(async () => {
    try {
      const response = await docRouterOrgApi.listTags({});
      setAvailableTags(response.tags);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading tags';
      toast.error('Error: ' + errorMsg);
    }
  }, [docRouterOrgApi]);

  useEffect(() => {
    loadTags();
  }, [loadTags]);

  // Update jsonForm when currentForm changes
  useEffect(() => {
    setJsonForm(JSON.stringify(currentForm.response_format, null, 2));
  }, [currentForm]);

  // Add handler for JSON form changes
  const handleJsonFormChange = (value: string | undefined) => {
    if (!value) return;
    try {
      const parsedForm = JSON.parse(value);
      
      // Validate form structure
      if (!parsedForm.json_formio) {
        toast.error('Error: Invalid form format. Must contain json_formio');
        return;
      }
      
      // Update form (preserve existing mapping if not provided in JSON)
      setCurrentForm(prev => ({
        ...prev,
        response_format: {
          json_formio: parsedForm.json_formio,
          json_formio_mapping: parsedForm.json_formio_mapping || prev.response_format.json_formio_mapping || {}
        }
      }));
    } catch (error) {
      // Invalid JSON - don't update
      toast.error(`Error: Invalid JSON syntax: ${error}`);
    }
  };

  const saveForm = async () => {
    try {
      setIsLoading(true);
      
      // Create the form object with tag_ids
      const formToSave = {
        ...currentForm,
        tag_ids: selectedTagIds
      };

      if (currentFormId) {
        // Update existing form
        await docRouterOrgApi.updateForm({
          formId: currentFormId, 
          form: formToSave
        });
      } else {
        // Create new form
        await docRouterOrgApi.createForm(formToSave);
      }

      // Clear the form
      setCurrentForm({
        name: '',
        response_format: {
          json_formio: [],
          json_formio_mapping: {}
        },
        tag_ids: []
      });
      setCurrentFormId(null);
      setSelectedTagIds([]);

      router.push(`/orgs/${organizationId}/forms`);
      
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error saving form';
      toast.error('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-4 w-full">
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <div className="hidden md:flex items-center gap-3 mb-4 flex-wrap">
          <h2 className="text-xl font-bold">
            {currentFormId ? 'Edit Form' : 'Create Form'}
          </h2>
          {currentFormFull && currentFormId && (
            <>
              <FormVersionSelector
                organizationId={organizationId}
                formId={currentFormId}
                currentVersion={currentFormFull.form_version}
                onVersionSelect={async (formRevId, version) => {
                  try {
                    setIsLoading(true);
                    const form = await docRouterOrgApi.getForm({ formRevId });
                    setCurrentFormFull(form);
                    setViewingVersion(version);
                    // Check if this is the latest version
                    const versionsResponse = await docRouterOrgApi.listFormVersions({ formId: currentFormId });
                    const latestVersion = versionsResponse.forms.sort((a, b) => b.form_version - a.form_version)[0];
                    setIsReadOnly(version !== latestVersion.form_version);
                    setCurrentForm({
                      name: form.name,
                      response_format: {
                        ...form.response_format,
                        json_formio_mapping: form.response_format.json_formio_mapping || {}
                      },
                      tag_ids: form.tag_ids || []
                    });
                    setSelectedTagIds(form.tag_ids || []);
                    // Update URL to reflect the selected version
                    router.push(`/orgs/${organizationId}/forms/${formRevId}`);
                  } catch (error) {
                    toast.error(`Error loading form version: ${getApiErrorMsg(error)}`);
                  } finally {
                    setIsLoading(false);
                  }
                }}
              />
              <button
                onClick={() => setIsCompareModalOpen(true)}
                className="h-8 mb-2 flex items-center gap-2 px-3 text-sm font-medium text-blue-600 border border-blue-600 rounded-md hover:bg-blue-50 transition-colors"
              >
                <CompareArrowsIcon className="text-base" />
                <span>Compare Versions</span>
              </button>
            </>
          )}
          {currentFormFull && (
            <button
              onClick={() => setIsInfoModalOpen(true)}
              className="h-8 w-8 mb-2 flex items-center justify-center text-gray-600 hover:bg-gray-50 rounded-md transition-colors"
              title="Form Properties"
            >
              <BadgeIcon className="text-lg" />
            </button>
          )}
          <InfoTooltip 
            title="About Forms"
            content={
              <>
                <p className="mb-2">
                  Forms are used to validate and structure data extracted from documents.
                </p>
                <ul className="list-disc list-inside space-y-1 mb-2">
                  <li>Use descriptive field names</li>
                  <li>Choose appropriate data types for each field</li>
                  <li>All fields defined in a form are required by default</li>
                </ul>
              </>
            }
          />
        </div>
        
        {isReadOnly && currentFormFull && (
          <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-800">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">
                Viewing version {viewingVersion} (read-only). This is not the latest version.
              </span>
              <button
                type="button"
                onClick={async () => {
                  if (!currentFormId) return;
                  try {
                    setIsLoading(true);
                    const versionsResponse = await docRouterOrgApi.listFormVersions({ formId: currentFormId });
                    const latestVersion = versionsResponse.forms.sort((a, b) => b.form_version - a.form_version)[0];
                    const form = await docRouterOrgApi.getForm({ formRevId: latestVersion.form_revid });
                    setCurrentFormFull(form);
                    setViewingVersion(form.form_version);
                    setIsReadOnly(false);
                    setCurrentForm({
                      name: form.name,
                      response_format: {
                        ...form.response_format,
                        json_formio_mapping: form.response_format.json_formio_mapping || {}
                      },
                      tag_ids: form.tag_ids || []
                    });
                    setSelectedTagIds(form.tag_ids || []);
                    router.push(`/orgs/${organizationId}/forms/${latestVersion.form_revid}`);
                  } catch (error) {
                    toast.error(`Error loading latest version: ${getApiErrorMsg(error)}`);
                  } finally {
                    setIsLoading(false);
                  }
                }}
                className="px-3 py-1 text-sm bg-yellow-100 hover:bg-yellow-200 rounded border border-yellow-300"
              >
                View Latest Version
              </button>
            </div>
          </div>
        )}
        
        <div className="space-y-4">
          {/* Form Name Input */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex-1 md:w-1/2 md:max-w-[calc(50%-1rem)]">
              <input
                type="text"
                className="w-full p-2 border rounded"
                value={currentForm.name}
                onChange={e => setCurrentForm({ ...currentForm, name: e.target.value })}
                placeholder="Form Name"
                disabled={isLoading || isReadOnly}
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setCurrentFormId(null);
                  setCurrentForm({
                    name: '',
                    response_format: {
                      json_formio: [],
                      json_formio_mapping: {}
                    },
                    tag_ids: []
                  });
                  setSelectedTagIds([]);
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
                disabled={isLoading || isReadOnly}
              >
                Clear
              </button>
              <button
                type="button"
                onClick={() => {
                  if (!currentForm.name) {
                    toast.error('Please fill in the form name');
                    return;
                  }
                  saveForm();
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={isLoading || isReadOnly}
              >
                {currentFormId ? 'Update Form' : 'Save Form'}
              </button>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="border-b border-gray-200 mb-4">
            <div className="flex gap-8">
              <button
                type="button"
                onClick={() => setActiveTab('builder')}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  activeTab === 'builder'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Form Builder
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('mapper')}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  activeTab === 'mapper'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Form Mapper
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('json')}
                className={`pb-4 px-1 relative font-semibold text-base ${
                  activeTab === 'json'
                    ? 'text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                JSON Form
              </button>
            </div>
          </div>

          {/* Tab Content */}
          <div className="space-y-4">
            {activeTab === 'builder' ? (
              // Form Builder Tab
              <div className="border rounded-lg overflow-hidden bg-white">
                <FormioBuilder
                  jsonFormio={JSON.stringify(currentForm.response_format.json_formio || [])}
                  onChange={(components) => {
                    if (!isReadOnly) {
                      setCurrentForm(prev => ({
                        ...prev,
                        response_format: {
                          ...prev.response_format,
                          json_formio: components
                        }
                      }));
                    }
                  }}
                  readOnly={isReadOnly}
                />
              </div>
            ) : activeTab === 'mapper' ? (
              // Form Mapper Tab
              <FormioMapper
                organizationId={organizationId}
                selectedTagIds={selectedTagIds}
                formComponents={currentForm.response_format.json_formio as FormComponent[] || []}
                fieldMappings={currentForm.response_format.json_formio_mapping || {}}
                onMappingChange={(mappings) => {
                  if (!isReadOnly) {
                    setCurrentForm(prev => ({
                      ...prev,
                      response_format: {
                        ...prev.response_format,
                        json_formio_mapping: mappings
                      }
                    }));
                  }
                }}
                readOnly={isReadOnly}
              />
            ) : (
              // JSON Form Tab
              <div className="h-[calc(100vh-300px)] border rounded">
                <Editor
                  height="100%"
                  defaultLanguage="json"
                  value={jsonForm}
                  onChange={handleJsonFormChange}
                  options={{
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                    wordWrap: "on",
                    wrappingIndent: "indent",
                    lineNumbers: "on",
                    folding: true,
                    renderValidationDecorations: "on",
                    readOnly: isReadOnly
                  }}
                  theme="vs-light"
                />
              </div>
            )}
          </div>

          {/* Tags Section - moved to bottom like in PromptCreate */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              Tags
            </label>
            <div className="w-full md:w-1/4">
              <TagSelector
                availableTags={availableTags}
                selectedTagIds={selectedTagIds}
                onChange={setSelectedTagIds}
                disabled={isLoading || isReadOnly}
              />
            </div>
          </div>
        </div>
      </div>
      
      {/* Version Compare Modal */}
      {currentFormFull && currentFormId && (
        <FormVersionCompareModal
          isOpen={isCompareModalOpen}
          onClose={() => setIsCompareModalOpen(false)}
          organizationId={organizationId}
          formId={currentFormId}
          currentForm={currentFormFull}
          onCompare={(leftForm, rightForm) => {
            setDiffLeft(leftForm);
            setDiffRight(rightForm);
          }}
        />
      )}
      
      {/* Info Modal */}
      {currentFormFull && (
        <FormInfoModal
          isOpen={isInfoModalOpen}
          onClose={() => setIsInfoModalOpen(false)}
          form={currentFormFull}
        />
      )}
      
      {/* Diff View */}
      {diffLeft && diffRight && (
        <FormDiffView
          leftForm={diffLeft}
          rightForm={diffRight}
          onClose={() => {
            setDiffLeft(null);
            setDiffRight(null);
          }}
        />
      )}
    </div>
  );
};

export default FormCreate;