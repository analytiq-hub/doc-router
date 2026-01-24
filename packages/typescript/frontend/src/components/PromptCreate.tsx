'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DocRouterOrgApi, DocRouterAccountApi } from '@/utils/api';
import { LLMChatModel } from '@docrouter/sdk';
import { Tag, Prompt, Schema, SchemaResponseFormat, KnowledgeBase } from '@docrouter/sdk';

// Type alias for prompt creation/update (without id and timestamps)
type PromptConfig = Omit<Prompt, 'prompt_revid' | 'prompt_id' | 'prompt_version' | 'created_at' | 'created_by'>;
import { getApiErrorMsg } from '@/utils/api';
import InfoTooltip from '@/components/InfoTooltip';
import TagSelector from './TagSelector';
import { toast } from 'react-toastify';
import { useRouter } from 'next/navigation';
import Editor from "@monaco-editor/react";
import BadgeIcon from '@mui/icons-material/Badge';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import PromptInfoModal from './PromptInfoModal';
import PromptVersionSelector from './PromptVersionSelector';
import PromptVersionCompareModal from './PromptVersionCompareModal';
import PromptDiffView from './PromptDiffView';

// Define default model constant
const DEFAULT_LLM_MODEL = 'gemini-2.0-flash';

const PromptCreate: React.FC<{ organizationId: string, promptRevId?: string }> = ({ organizationId, promptRevId }) => {
  const router = useRouter();
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const [currentPromptId, setCurrentPromptId] = useState<string | null>(null);
  const [currentPromptFull, setCurrentPromptFull] = useState<Prompt | null>(null);
  const [viewingVersion, setViewingVersion] = useState<number | null>(null);
  const [isReadOnly, setIsReadOnly] = useState(false);
  const [currentPrompt, setCurrentPrompt] = useState<PromptConfig>({
    name: '',
    content: '',
    schema_id: undefined,
    schema_version: undefined,
    tag_ids: [],
    model: undefined
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const [diffLeft, setDiffLeft] = useState<Prompt | null>(null);
  const [diffRight, setDiffRight] = useState<Prompt | null>(null);
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [selectedSchema, setSelectedSchema] = useState<string>('');
  const [selectedSchemaDetails, setSelectedSchemaDetails] = useState<Schema | null>(null);
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [llmModels, setLLMModels] = useState<LLMChatModel[]>([]);
  const [availableKnowledgeBases, setAvailableKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string>('');

  const handleSchemaSelect = useCallback(async (schemaId: string) => {
    setSelectedSchema(schemaId);
    
    // Update currentPrompt with schema_id
    setCurrentPrompt(prev => ({
      ...prev,
      schema_id: schemaId || undefined,
      schema_version: undefined  // Reset version until we load schema details
    }));

    if (schemaId) {
      try {
        // Find schema with matching schema_id and highest schema_version
        const matchingSchemas = schemas.filter(s => s.schema_id === schemaId);
        if (matchingSchemas.length > 0) {
          // Sort by schema_version in descending order and take the first one
          const schemaDoc = matchingSchemas.sort((a, b) => 
            (b.schema_version || 0) - (a.schema_version || 0)
          )[0];
          
          const schema = await docRouterOrgApi.getSchema({ 
            schemaRevId: schemaDoc.schema_revid 
          });

          setSelectedSchemaDetails(schema);
          // Update currentPrompt with the schema_id and version
          setCurrentPrompt(prev => ({
            ...prev,
            schema_id: schema.schema_id,
            schema_version: schema.schema_version
          }));
        }
      } catch (error) {
        toast.error(`Error fetching schema details: ${getApiErrorMsg(error)}`);
      }
    } else {
      setSelectedSchemaDetails(null);
    }
  }, [schemas, docRouterOrgApi, setSelectedSchema, setSelectedSchemaDetails, setCurrentPrompt])

  // Load editing prompt if available
  useEffect(() => {
    const loadPrompt = async () => {
      if (promptRevId) {
        try {
          setIsLoading(true);
          const prompt = await docRouterOrgApi.getPrompt({ promptRevId });
          setCurrentPromptId(prompt.prompt_id);
          setCurrentPromptFull(prompt);
          setViewingVersion(prompt.prompt_version);
          // Check if this is the latest version
          const versionsResponse = await docRouterOrgApi.listPromptVersions({ promptId: prompt.prompt_id });
          const latestVersion = versionsResponse.prompts.sort((a, b) => b.prompt_version - a.prompt_version)[0];
          setIsReadOnly(prompt.prompt_version !== latestVersion.prompt_version);
          setCurrentPrompt({
            name: prompt.name,
            content: prompt.content,
            schema_id: prompt.schema_id,
            schema_version: prompt.schema_version,
            tag_ids: prompt.tag_ids || [],
            model: prompt.model,
            kb_id: prompt.kb_id
          });
          setSelectedTagIds(prompt.tag_ids || []);
          setSelectedSchema(prompt.schema_id || '');
          setSelectedKbId(prompt.kb_id || '');
          // Optionally, load schema details if needed
          if (prompt.schema_id) {
            await handleSchemaSelect(prompt.schema_id);
          } else {
            setSelectedSchemaDetails(null);
          }
        } catch (error) {
          toast.error(`Error loading prompt for editing: ${getApiErrorMsg(error)}`);
        } finally {
          setIsLoading(false);
        }
      }
    };
    loadPrompt();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [promptRevId, organizationId]);

  // Initialize schema details when form is loaded with a schema
  useEffect(() => {
    const initSchema = async () => {
      if (currentPrompt.schema_id && schemas.length > 0) {
        // Find schema with matching schema_id and highest schema_version
        const matchingSchemas = schemas.filter(s => s.schema_id === currentPrompt.schema_id);
        if (matchingSchemas.length > 0) {
          // Sort by schema_version in descending order and take the first one
          const schemaDoc = matchingSchemas.sort((a, b) => 
            (b.schema_version || 0) - (a.schema_version || 0)
          )[0];
          
          try {
            const schema = await docRouterOrgApi.getSchema({ 
              schemaRevId: schemaDoc.schema_revid 
            });
            setSelectedSchemaDetails(schema);
            // Ensure currentPrompt has the latest schema_version
            setCurrentPrompt(prev => ({
              ...prev,
              schema_version: schema.schema_version
            }));
          } catch (error) {
            toast.error(`Error fetching schema details: ${getApiErrorMsg(error)}`);
          }
        }
      }
    };
    
    initSchema();
  }, [schemas, currentPrompt.schema_id, docRouterOrgApi]);

  const savePrompt = async () => {
    try {
      setIsLoading(true);
      
      // Create the prompt object with tag_ids and kb_id
      const promptToSave = {
        ...currentPrompt,
        tag_ids: selectedTagIds,
        kb_id: selectedKbId || undefined
      };

      if (currentPromptId) {
        // Update existing prompt
        await docRouterOrgApi.updatePrompt({ promptId: currentPromptId, prompt: promptToSave });
      } else {
        // Create new prompt
        await docRouterOrgApi.createPrompt({ prompt: promptToSave });
      }

      // Clear the form
      setCurrentPrompt({
        name: '',
        content: '',
        schema_id: undefined,
        schema_version: undefined,
        tag_ids: [],
        model: undefined,
        kb_id: undefined
      });
      setCurrentPromptId(null);
      setSelectedSchema('');
      setSelectedSchemaDetails(null);
      setSelectedTagIds([]);
      setSelectedKbId('');

      router.push(`/orgs/${organizationId}/prompts`);
      
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error saving prompt';
      toast.error(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const loadSchemas = useCallback(async () => {
    try {
      const response = await docRouterOrgApi.listSchemas({ limit: 100 });
      setSchemas(response.schemas);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading schemas';
      toast.error(errorMsg);
    }
  }, [docRouterOrgApi]);

  const loadTags = useCallback(async () => {
    try {
      const response = await docRouterOrgApi.listTags({ limit: 100 });
      setAvailableTags(response.tags);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading tags';
      toast.error(errorMsg);
    }
  }, [docRouterOrgApi]);

  const loadLLMModels = useCallback(async () => {
    try {
      const response = await docRouterAccountApi.listLLMModels({
        providerEnabled: true,
        llmEnabled: true
      });
      setLLMModels(response.chat_models);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading LLM models';
      toast.error(errorMsg);
    }
  }, [docRouterAccountApi]);

  const loadKnowledgeBases = useCallback(async () => {
    try {
      const response = await docRouterOrgApi.listKnowledgeBases({ limit: 100 });
      // Only show active knowledge bases
      const activeKBs = response.knowledge_bases.filter(kb => kb.status === 'active');
      setAvailableKnowledgeBases(activeKBs);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error loading knowledge bases';
      toast.error(errorMsg);
    }
  }, [docRouterOrgApi]);

  useEffect(() => {
    loadSchemas();
    loadTags();
    loadLLMModels();
    loadKnowledgeBases();
  }, [loadSchemas, loadTags, loadLLMModels, loadKnowledgeBases]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentPrompt.name || !currentPrompt.content) {
      toast.error('Please fill in all fields');
      return;
    }

    savePrompt();
  };

  // Helper function
  const isJsonContent = (content: string): boolean => {
    try {
      JSON.parse(content);
      return true;
    } catch {
      return false;
    }
  };

  // Helper function
  const jsonSchemaToFields = (responseFormat: SchemaResponseFormat) => {
    const fields = [];
    const properties = responseFormat.json_schema.schema.properties;
    
    for (const [name, prop] of Object.entries(properties)) {
      const type = prop.type === 'string' ? 'str' :
                 prop.type === 'integer' ? 'int' :
                 prop.type === 'number' ? 'float' :
                 prop.type === 'boolean' ? 'bool' : 'str';
                 
      fields.push({ name, type });
    }
    return fields;
  };

  return (
    <div className="p-4 w-full">
      {/* Prompt Creation Form */}
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <div className="hidden md:flex items-center gap-3 mb-4 flex-wrap">
          <h2 className="text-xl font-bold">
            {currentPromptId ? 'Edit Prompt' : 'Create Prompt'}
          </h2>
          {currentPromptFull && currentPromptId && (
            <>
              <PromptVersionSelector
                organizationId={organizationId}
                promptId={currentPromptId}
                currentVersion={currentPromptFull.prompt_version}
                onVersionSelect={async (promptRevId, version) => {
                  try {
                    setIsLoading(true);
                    const prompt = await docRouterOrgApi.getPrompt({ promptRevId });
                    setCurrentPromptFull(prompt);
                    setViewingVersion(version);
                    // Check if this is the latest version
                    const versionsResponse = await docRouterOrgApi.listPromptVersions({ promptId: currentPromptId });
                    const latestVersion = versionsResponse.prompts.sort((a, b) => b.prompt_version - a.prompt_version)[0];
                    setIsReadOnly(version !== latestVersion.prompt_version);
                    setCurrentPrompt({
                      name: prompt.name,
                      content: prompt.content,
                      schema_id: prompt.schema_id,
                      schema_version: prompt.schema_version,
                      tag_ids: prompt.tag_ids || [],
                      model: prompt.model,
                      kb_id: prompt.kb_id
                    });
                    setSelectedTagIds(prompt.tag_ids || []);
                    setSelectedSchema(prompt.schema_id || '');
                    setSelectedKbId(prompt.kb_id || '');
                    if (prompt.schema_id) {
                      await handleSchemaSelect(prompt.schema_id);
                    }
                    // Update URL to reflect the selected version
                    router.push(`/orgs/${organizationId}/prompts/${promptRevId}`);
                  } catch (error) {
                    toast.error(`Error loading prompt version: ${getApiErrorMsg(error)}`);
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
          {currentPromptFull && (
            <button
              onClick={() => setIsInfoModalOpen(true)}
              className="h-8 w-8 mb-2 flex items-center justify-center text-gray-600 hover:bg-gray-50 rounded-md transition-colors"
              title="Prompt Properties"
            >
              <BadgeIcon className="text-lg" />
            </button>
          )}
          <InfoTooltip 
            title="Configuring Prompts"
            content={
              <>
                <p className="mb-2">
                  Prompts are instructions that guide AI models to perform specific tasks. An effective prompt should be clear, specific, and provide necessary context.
                </p>
                <p className="mb-2">
                  <strong>Schema:</strong> Link a schema to ensure structured output in a consistent format.
                </p>
                <p className="mb-2">
                  <strong>Model:</strong> Choose the appropriate model based on task complexity and performance requirements.
                </p>
                <p>
                  <strong>Tags:</strong> Only files with the selected tags will be processed by this prompt.
                </p>
              </>
            }
          />
        </div>
        
        {isReadOnly && currentPromptFull && (
          <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-800">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">
                Viewing version {viewingVersion} (read-only). This is not the latest version.
              </span>
              <button
                type="button"
                onClick={async () => {
                  if (!currentPromptId) return;
                  try {
                    setIsLoading(true);
                    const versionsResponse = await docRouterOrgApi.listPromptVersions({ promptId: currentPromptId });
                    const latestVersion = versionsResponse.prompts.sort((a, b) => b.prompt_version - a.prompt_version)[0];
                    const prompt = await docRouterOrgApi.getPrompt({ promptRevId: latestVersion.prompt_revid });
                    setCurrentPromptFull(prompt);
                    setViewingVersion(prompt.prompt_version);
                    setIsReadOnly(false);
                    setCurrentPrompt({
                      name: prompt.name,
                      content: prompt.content,
                      schema_id: prompt.schema_id,
                      schema_version: prompt.schema_version,
                      tag_ids: prompt.tag_ids || [],
                      model: prompt.model,
                      kb_id: prompt.kb_id
                    });
                    setSelectedTagIds(prompt.tag_ids || []);
                    setSelectedSchema(prompt.schema_id || '');
                    setSelectedKbId(prompt.kb_id || '');
                    if (prompt.schema_id) {
                      await handleSchemaSelect(prompt.schema_id);
                    }
                    router.push(`/orgs/${organizationId}/prompts/${latestVersion.prompt_revid}`);
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
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Prompt Name Input and Action Buttons in a flex container */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex-1 md:w-1/2 md:max-w-[calc(50%-1rem)]">
              <input
                type="text"
                className="w-full p-2 border rounded"
                value={currentPrompt.name}
                onChange={e => setCurrentPrompt({ ...currentPrompt, name: e.target.value })}
                placeholder="Prompt Name"
                disabled={isLoading || isReadOnly}
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  // Clear the form
                  setCurrentPromptId(null);
                  setCurrentPrompt({
                    name: '',
                    content: '',
                    schema_id: undefined,
                    schema_version: undefined,
                    tag_ids: [],
                    model: undefined,
                    kb_id: undefined
                  });
                  setSelectedSchema('');
                  setSelectedSchemaDetails(null);
                  setSelectedTagIds([]);
                  setSelectedKbId('');
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
                disabled={isLoading || isReadOnly}
              >
                Clear
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={isLoading || isReadOnly}
              >
                {currentPromptId ? 'Update Prompt' : 'Save Prompt'}
              </button>
            </div>
          </div>

          <div className="border rounded-lg overflow-hidden bg-white">
            <Editor
              height="400px"
              defaultLanguage={isJsonContent(currentPrompt.content) ? 'json' : 'markdown'}
              value={currentPrompt.content}
              onChange={(value) => setCurrentPrompt(prev => ({ ...prev, content: value || '' }))}
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

          <div className="flex gap-4">
            <div className="w-1/2 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700" data-tour="prompt-model-select">
                  Model
                </label>
                <select
                  value={currentPrompt.model || DEFAULT_LLM_MODEL}
                  onChange={(e) => setCurrentPrompt(prev => ({ ...prev, model: e.target.value }))}
                  disabled={isLoading || isReadOnly}
                  className="w-full p-2 border border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                >
                  {llmModels.map((model) => (
                    <option key={model.litellm_model} value={model.litellm_model}>
                      {model.litellm_model} ({model.litellm_provider})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700" data-tour="prompt-schema-select">
                  Schema (Optional)
                </label>
                <select
                  value={selectedSchema}
                  onChange={(e) => handleSchemaSelect(e.target.value)}
                  disabled={isLoading || isReadOnly}
                  className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
                >
                  <option value="">None</option>
                  {schemas.map((schema) => (
                    <option key={schema.schema_id} value={schema.schema_id}>
                      {schema.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Knowledge Base (Optional)
                </label>
                <select
                  value={selectedKbId}
                  onChange={(e) => {
                    setSelectedKbId(e.target.value);
                    setCurrentPrompt(prev => ({ ...prev, kb_id: e.target.value || undefined }));
                  }}
                  disabled={isLoading || isReadOnly}
                  className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
                >
                  <option value="">None</option>
                  {availableKnowledgeBases.map((kb) => (
                    <option key={kb.kb_id} value={kb.kb_id}>
                      {kb.name}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Associate a knowledge base to enable RAG (Retrieval-Augmented Generation) for this prompt
                </p>
              </div>

              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">
                  Tags
                </label>
                <TagSelector
                  availableTags={availableTags}
                  selectedTagIds={selectedTagIds}
                  onChange={setSelectedTagIds}
                  disabled={isLoading || isReadOnly}
                />
              </div>
            </div>

            {selectedSchemaDetails && (
              <div className="w-1/2 p-4 bg-gray-50 rounded-md">
                <h3 className="text-sm font-medium text-gray-700 mb-2">
                  Schema: {selectedSchemaDetails.name} (v{selectedSchemaDetails.schema_version})
                </h3>
                <div className="space-y-1">
                  {jsonSchemaToFields(selectedSchemaDetails.response_format).map((field, index) => (
                    <div key={index} className="text-sm text-gray-600">
                      • {field.name}: <span className="text-gray-500">{field.type}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </form>
      </div>
      
      {/* Version Compare Modal */}
      {currentPromptFull && currentPromptId && (
        <PromptVersionCompareModal
          isOpen={isCompareModalOpen}
          onClose={() => setIsCompareModalOpen(false)}
          organizationId={organizationId}
          promptId={currentPromptId}
          currentPrompt={currentPromptFull}
          onCompare={(leftPrompt, rightPrompt) => {
            setDiffLeft(leftPrompt);
            setDiffRight(rightPrompt);
          }}
        />
      )}
      
      {/* Info Modal */}
      {currentPromptFull && (
        <PromptInfoModal
          isOpen={isInfoModalOpen}
          onClose={() => setIsInfoModalOpen(false)}
          prompt={currentPromptFull}
        />
      )}
      
      {/* Diff View */}
      {diffLeft && diffRight && (
        <PromptDiffView
          leftPrompt={diffLeft}
          rightPrompt={diffRight}
          onClose={() => {
            setDiffLeft(null);
            setDiffRight(null);
          }}
        />
      )}
    </div>
  );
};

export default PromptCreate; 