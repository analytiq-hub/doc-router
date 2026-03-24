"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi, DocRouterAccountApi, getApiErrorMsg } from '@/utils/api';
import {
  KnowledgeBaseConfig,
  KnowledgeBaseUpdate,
  Tag,
  ChunkerType,
  ChunkingPreset,
  ChunkingPreprocessConfig,
  chunkingPreprocessForPreset,
  LLMEmbeddingModel,
} from '@docrouter/sdk';
import { useRouter } from 'next/navigation';
import { toast } from 'react-toastify';
import InfoTooltip from '@/components/InfoTooltip';
import TagSelector from '@/components/TagSelector';

const CHUNKER_TYPES: ChunkerType[] = ['token', 'word', 'sentence', 'recursive', 'markdown'];
const CHUNKING_PRESET_OPTIONS: { value: ChunkingPreset; label: string }[] = [
  { value: 'plain', label: 'Plain' },
  { value: 'structured_doc', label: 'Structured document' },
];
const DEFAULT_CHUNKING_PRESET: ChunkingPreset = 'structured_doc';
const DEFAULT_CHUNK_SIZE = 512;
const DEFAULT_CHUNK_OVERLAP = 128;
const DEFAULT_EMBEDDING_MODEL = 'text-embedding-3-small';
const DEFAULT_COALESCE_NEIGHBORS = 0;
const MIN_CHUNK_SIZE = 50;
const MAX_CHUNK_SIZE = 2000;
const MAX_COALESCE_NEIGHBORS = 5;
const KnowledgeBaseCreate: React.FC<{ organizationId: string; kbId?: string }> = ({ organizationId, kbId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const docRouterAccountApi = useMemo(() => new DocRouterAccountApi(), []);
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [currentKB, setCurrentKB] = useState<KnowledgeBaseConfig>({
    name: '',
    description: '',
    system_prompt: '',
    tag_ids: [],
    chunker_type: 'recursive',
    chunk_size: DEFAULT_CHUNK_SIZE,
    chunk_overlap: DEFAULT_CHUNK_OVERLAP,
    embedding_model: DEFAULT_EMBEDDING_MODEL,
    coalesce_neighbors: DEFAULT_COALESCE_NEIGHBORS,
    reconcile_enabled: false,
    reconcile_interval_seconds: undefined,
    min_vector_score: undefined,
  });
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [availableEmbeddingModels, setAvailableEmbeddingModels] = useState<LLMEmbeddingModel[]>([]);
  const [isEditing, setIsEditing] = useState(false);

  // Load available tags
  useEffect(() => {
    async function loadTags() {
      try {
        const response = await docRouterOrgApi.listTags({ limit: 100 });
        setAvailableTags(response.tags);
      } catch (error) {
        console.error('Error loading tags:', error);
      }
    }
    loadTags();
  }, [docRouterOrgApi]);

  // Load available embedding models
  useEffect(() => {
    async function loadEmbeddingModels() {
      try {
        const response = await docRouterAccountApi.listLLMModels({ llmEnabled: true });
        setAvailableEmbeddingModels(response.embedding_models);
      } catch (error) {
        console.error('Error loading embedding models:', error);
        // Don't show error toast - just log it, as this is not critical for KB creation
      }
    }
    loadEmbeddingModels();
  }, [docRouterAccountApi]);

  // Load KB if editing
  useEffect(() => {
    async function loadKB() {
      if (kbId) {
        setIsLoading(true);
        try {
          const kb = await docRouterOrgApi.getKnowledgeBase({ kbId });
          const loadedPreset = (kb.chunking_preset as ChunkingPreset | undefined) ?? DEFAULT_CHUNKING_PRESET;
          setCurrentKB({
            name: kb.name,
            description: kb.description || '',
            system_prompt: kb.system_prompt || '',
            tag_ids: kb.tag_ids || [],
            chunker_type: kb.chunker_type,
            chunk_size: kb.chunk_size,
            chunk_overlap: kb.chunk_overlap,
            embedding_model: kb.embedding_model,
            coalesce_neighbors: kb.coalesce_neighbors || 0,
            reconcile_enabled: kb.reconcile_enabled || false,
            reconcile_interval_seconds: kb.reconcile_interval_seconds,
            min_vector_score: kb.min_vector_score ?? undefined,
            chunking_preset: kb.chunking_preset ?? loadedPreset,
            chunking_preprocess:
              kb.chunking_preprocess != null
                ? kb.chunking_preprocess
                : chunkingPreprocessForPreset(loadedPreset),
          });
          setIsEditing(true);
        } catch (error) {
          toast.error(`Error loading knowledge base: ${getApiErrorMsg(error)}`);
        } finally {
          setIsLoading(false);
        }
      }
    }
    loadKB();
  }, [kbId, docRouterOrgApi]);

  const handleTagChange = (tagIds: string[]) => {
    setCurrentKB({
      ...currentKB,
      tag_ids: tagIds
    });
  };

  const mergeChunkingPreprocess = (patch: Partial<ChunkingPreprocessConfig>) => {
    const cur =
      currentKB.chunking_preprocess ??
      chunkingPreprocessForPreset(currentKB.chunking_preset ?? DEFAULT_CHUNKING_PRESET);
    setCurrentKB({ ...currentKB, chunking_preprocess: { ...cur, ...patch } });
  };

  const saveKB = async () => {
    if (!currentKB.name.trim()) {
      toast.error('Please enter a knowledge base name');
      return;
    }

    if ((currentKB.chunk_overlap ?? 0) >= (currentKB.chunk_size ?? DEFAULT_CHUNK_SIZE)) {
      toast.error('Chunk overlap must be less than chunk size');
      return;
    }

    try {
      setIsLoading(true);
      
      if (isEditing && kbId) {
        const update: KnowledgeBaseUpdate = {
          name: currentKB.name,
          description: currentKB.description,
          system_prompt: currentKB.system_prompt,
          tag_ids: currentKB.tag_ids,
          coalesce_neighbors: currentKB.coalesce_neighbors,
          reconcile_enabled: currentKB.reconcile_enabled,
          reconcile_interval_seconds: currentKB.reconcile_interval_seconds,
          min_vector_score:
            currentKB.min_vector_score === undefined || currentKB.min_vector_score === null
              ? null
              : currentKB.min_vector_score,
          chunking_preset: currentKB.chunking_preset ?? undefined,
          chunking_preprocess: currentKB.chunking_preprocess,
        };
        await docRouterOrgApi.updateKnowledgeBase({
          kbId,
          update,
        });
        toast.success('Knowledge base updated successfully');
      } else {
        // Create new KB
        await docRouterOrgApi.createKnowledgeBase({ kb: currentKB });
        toast.success('Knowledge base created successfully');
      }
      
      router.push(`/orgs/${organizationId}/knowledge-bases`);
    } catch (error) {
      const errorMsg = getApiErrorMsg(error) || 'Error saving knowledge base';
      toast.error('Error: ' + errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    saveKB();
  };

  return (
    <div className="p-2 sm:p-4 max-w-4xl mx-auto">
      <div className="bg-white p-4 sm:p-6 rounded-lg shadow mb-6">
        <div className="flex items-center gap-2 mb-4">
          <h2 className="text-lg sm:text-xl font-bold">
            {isEditing ? 'Edit Knowledge Base' : 'Create Knowledge Base'}
          </h2>
          <InfoTooltip 
            title="About Knowledge Bases"
            content={
              <>
                <p className="mb-2">
                  Knowledge Bases enable semantic search across your documents using vector embeddings.
                </p>
                <ul className="list-disc list-inside space-y-1 mb-2">
                  <li>Documents are automatically indexed into KBs based on their tags.</li>
                  <li>Each KB uses its own embedding model and chunking configuration.</li>
                  <li>KB settings (chunker, chunk size, embedding model) cannot be changed after creation.</li>
                  <li>To change settings, create a new KB with the same tags.</li>
                </ul>
              </>
            }
          />
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-6">
          {/* Name */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
            <label htmlFor="kb-name" className="w-full sm:w-40 text-sm font-medium text-gray-700">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              id="kb-name"
              type="text"
              className="flex-1 p-2 border rounded disabled:bg-gray-100"
              value={currentKB.name}
              onChange={e => setCurrentKB({ ...currentKB, name: e.target.value })}
              placeholder="Knowledge Base Name"
              disabled={isLoading || isEditing}
              required
            />
          </div>

          {/* Description */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
            <label htmlFor="kb-description" className="w-full sm:w-40 text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              id="kb-description"
              className="flex-1 p-2 border rounded disabled:bg-gray-100"
              value={currentKB.description}
              onChange={e => setCurrentKB({ ...currentKB, description: e.target.value })}
              placeholder="Optional description"
              disabled={isLoading}
              rows={3}
            />
          </div>

          {/* System Prompt */}
          <div className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-4">
            <label htmlFor="kb-system-prompt" className="w-full sm:w-40 text-sm font-medium text-gray-700">
              System Prompt
            </label>
            <div className="flex-1">
              <textarea
                id="kb-system-prompt"
                className="flex-1 w-full p-2 border rounded disabled:bg-gray-100 font-mono text-sm"
                value={currentKB.system_prompt || ''}
                onChange={e => setCurrentKB({ ...currentKB, system_prompt: e.target.value })}
                placeholder="Optional instructions prepended to every prompt that uses this knowledge base..."
                disabled={isLoading}
                rows={6}
              />
              <p className="text-xs text-gray-500 mt-1">
                This text is prepended to the prompt content whenever a prompt references this knowledge base.
              </p>
            </div>
          </div>

          {/* Tags */}
          <div className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-4">
            <label className="w-full sm:w-40 text-sm font-medium text-gray-700 pt-2">
              Tags
            </label>
            <div className="flex-1">
              <TagSelector
                availableTags={availableTags}
                selectedTagIds={currentKB.tag_ids || []}
                onChange={handleTagChange}
                disabled={isLoading}
              />
              <p className="text-xs text-gray-500 mt-1">
                Documents with these tags will be automatically indexed into this knowledge base.
              </p>
            </div>
          </div>

          {/* Chunking preprocessing: presets + overrides (re-index to refresh old chunks) */}
          <div className="border-t pt-4 sm:pt-6 mt-4 sm:mt-6 space-y-3 sm:space-y-4">
            <div className="flex items-center gap-2">
              <h3 className="text-base sm:text-lg font-semibold">Chunking preprocessing</h3>
              <InfoTooltip
                title="Chunking preprocessing"
                content={
                  <>
                    <p className="mb-2">
                      Named presets set defaults for OCR markdown, stripping boilerplate lines, and heading
                      breadcrumbs used in embeddings. You can override individual options after selecting a preset.
                    </p>
                    <p>Already-indexed chunks keep prior text until documents are re-indexed into this KB.</p>
                  </>
                }
              />
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
              <label htmlFor="chunking-preset" className="w-full sm:w-40 text-sm font-medium text-gray-700">
                Preset
              </label>
              <select
                id="chunking-preset"
                className="flex-1 p-2 border rounded disabled:bg-gray-100"
                disabled={isLoading}
                value={currentKB.chunking_preset ?? DEFAULT_CHUNKING_PRESET}
                onChange={(e) => {
                  const p = e.target.value as ChunkingPreset;
                  setCurrentKB({
                    ...currentKB,
                    chunking_preset: p,
                    chunking_preprocess: chunkingPreprocessForPreset(p),
                  });
                }}
              >
                {CHUNKING_PRESET_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-4">
              <span className="w-full sm:w-40 text-sm font-medium text-gray-700 pt-1">Options</span>
              <div className="flex-1 space-y-2">
                {(
                  [
                    ['prefer_markdown', 'Prefer per-page OCR markdown (exact page map)'] as const,
                    ['strip_page_numbers', 'Strip digit-only lines (page numbers)'] as const,
                    ['strip_page_breaks', 'Replace horizontal-rule page breaks with blank lines'] as const,
                    ['prepend_heading_path', 'Prepend heading breadcrumb to embeddings only'] as const,
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      disabled={isLoading}
                      checked={
                        (currentKB.chunking_preprocess ??
                          chunkingPreprocessForPreset(
                            currentKB.chunking_preset ?? DEFAULT_CHUNKING_PRESET
                          ))[key]
                      }
                      onChange={(e) => mergeChunkingPreprocess({ [key]: e.target.checked })}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
              <label htmlFor="heading-split-depth" className="w-full sm:w-40 text-sm font-medium text-gray-700">
                Heading split depth
              </label>
              <input
                id="heading-split-depth"
                type="number"
                min={1}
                max={6}
                className="flex-1 p-2 border rounded disabled:bg-gray-100 w-full sm:max-w-xs"
                disabled={isLoading}
                value={
                  (currentKB.chunking_preprocess ??
                    chunkingPreprocessForPreset(
                      currentKB.chunking_preset ?? DEFAULT_CHUNKING_PRESET
                    )).heading_split_depth
                }
                onChange={(e) => {
                  const n = parseInt(e.target.value, 10);
                  if (!Number.isNaN(n)) mergeChunkingPreprocess({ heading_split_depth: Math.min(6, Math.max(1, n)) });
                }}
              />
            </div>
            <div className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-4">
              <label htmlFor="strip-patterns" className="w-full sm:w-40 text-sm font-medium text-gray-700 pt-1">
                Strip regexes
              </label>
              <div className="flex-1">
                <textarea
                  id="strip-patterns"
                  className="w-full p-2 border rounded font-mono text-sm disabled:bg-gray-100"
                  rows={3}
                  disabled={isLoading}
                  placeholder="One regex per line (multiline mode)"
                  value={(
                    currentKB.chunking_preprocess ??
                    chunkingPreprocessForPreset(
                      currentKB.chunking_preset ?? DEFAULT_CHUNKING_PRESET
                    )
                  ).strip_patterns.join('\n')}
                  onChange={(e) =>
                    mergeChunkingPreprocess({
                      strip_patterns: e.target.value
                        .split('\n')
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                />
                <p className="text-xs text-gray-500 mt-1">Applied to extracted text before chunking. Invalid regex will fail at index time.</p>
              </div>
            </div>
          </div>

          {/* Configuration Section - Only editable when creating */}
          {!isEditing && (
            <>
              <div className="border-t pt-4 sm:pt-6 mt-4 sm:mt-6">
                <h3 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">Indexing Configuration</h3>
                <p className="text-sm text-gray-600 mb-3 sm:mb-4">
                  These settings cannot be changed after creation. To use different settings, create a new KB.
                </p>

                {/* Chunker Type */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 mb-3 sm:mb-4">
                  <label htmlFor="chunker-type" className="w-full sm:w-40 text-sm font-medium text-gray-700">
                    Chunker Type
                  </label>
                  <select
                    id="chunker-type"
                    className="flex-1 p-2 border rounded disabled:bg-gray-100"
                    value={currentKB.chunker_type}
                    onChange={e => setCurrentKB({ ...currentKB, chunker_type: e.target.value as ChunkerType })}
                    disabled={isLoading}
                  >
                    {CHUNKER_TYPES.map(type => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                </div>

                {/* Chunk Size */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 mb-3 sm:mb-4">
                  <label htmlFor="chunk-size" className="w-full sm:w-40 text-sm font-medium text-gray-700">
                    Chunk Size (tokens)
                  </label>
                  <div className="flex-1 flex items-center gap-2">
                    <input
                      id="chunk-size"
                      type="number"
                      min={MIN_CHUNK_SIZE}
                      max={MAX_CHUNK_SIZE}
                      className="flex-1 p-2 border rounded disabled:bg-gray-100"
                      value={currentKB.chunk_size ?? DEFAULT_CHUNK_SIZE}
                      onChange={e => setCurrentKB({ ...currentKB, chunk_size: parseInt(e.target.value) || DEFAULT_CHUNK_SIZE })}
                      disabled={isLoading}
                    />
                    <span className="text-sm text-gray-500 whitespace-nowrap">{MIN_CHUNK_SIZE}-{MAX_CHUNK_SIZE}</span>
                  </div>
                </div>

                {/* Chunk Overlap */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 mb-3 sm:mb-4">
                  <label htmlFor="chunk-overlap" className="w-full sm:w-40 text-sm font-medium text-gray-700">
                    Chunk Overlap (tokens)
                  </label>
                  <div className="flex-1 flex items-center gap-2">
                    <input
                      id="chunk-overlap"
                      type="number"
                      min={0}
                      max={(currentKB.chunk_size ?? DEFAULT_CHUNK_SIZE) - 1}
                      className="flex-1 p-2 border rounded disabled:bg-gray-100"
                      value={currentKB.chunk_overlap ?? DEFAULT_CHUNK_OVERLAP}
                      onChange={e => setCurrentKB({ ...currentKB, chunk_overlap: parseInt(e.target.value) || 0 })}
                      disabled={isLoading}
                    />
                    <span className="text-sm text-gray-500 whitespace-nowrap">0-{(currentKB.chunk_size ?? DEFAULT_CHUNK_SIZE) - 1}</span>
                  </div>
                </div>

                {/* Embedding Model */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 mb-3 sm:mb-4">
                  <label htmlFor="embedding-model" className="w-full sm:w-40 text-sm font-medium text-gray-700">
                    Embedding Model
                  </label>
                  <select
                    id="embedding-model"
                    className="flex-1 p-2 border rounded disabled:bg-gray-100"
                    value={currentKB.embedding_model ?? DEFAULT_EMBEDDING_MODEL}
                    onChange={e => setCurrentKB({ ...currentKB, embedding_model: e.target.value })}
                    disabled={isLoading}
                  >
                    {availableEmbeddingModels.length > 0 ? (
                      availableEmbeddingModels.map(model => (
                        <option key={model.litellm_model} value={model.litellm_model}>
                          {model.litellm_model} ({model.dimensions}D)
                        </option>
                      ))
                    ) : (
                      <option value={DEFAULT_EMBEDDING_MODEL}>{DEFAULT_EMBEDDING_MODEL}</option>
                    )}
                  </select>
                </div>
              </div>
            </>
          )}

          {/* Coalesce Neighbors - Editable */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
            <label htmlFor="coalesce-neighbors" className="w-full sm:w-40 text-sm font-medium text-gray-700">
              Coalesce Neighbors
            </label>
            <div className="flex-1 flex items-center gap-2">
              <input
                id="coalesce-neighbors"
                type="number"
                min={0}
                max={MAX_COALESCE_NEIGHBORS}
                className="flex-1 p-2 border rounded disabled:bg-gray-100"
                value={currentKB.coalesce_neighbors ?? DEFAULT_COALESCE_NEIGHBORS}
                onChange={e => setCurrentKB({ ...currentKB, coalesce_neighbors: parseInt(e.target.value) || 0 })}
                disabled={isLoading}
              />
              <span className="text-sm text-gray-500 whitespace-nowrap">0-{MAX_COALESCE_NEIGHBORS}</span>
              <InfoTooltip 
                title="Coalesce Neighbors"
                content="Number of neighboring chunks to include in search results for context. 0 means only return matched chunks."
              />
            </div>
          </div>

          {/* Search & retrieval */}
          <div className="border-t pt-4 space-y-3 sm:space-y-4">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-gray-700">Search &amp; retrieval</h3>
              <InfoTooltip
                title="Retrieval"
                content={
                  <>
                    <p className="mb-2">
                      Searches use hybrid retrieval (lexical + vector via $rankFusion) when the query is non-empty.
                      Keyword vs meaning blend follows per-query heuristics.
                    </p>
                    <p>
                      Minimum vector score applies only when search falls back to vectors only (empty query, or if
                      $rankFusion is unavailable on the cluster).
                    </p>
                  </>
                }
              />
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
              <label htmlFor="min-vector-score" className="w-full sm:w-40 text-sm font-medium text-gray-700">
                Min vector score
              </label>
              <div className="flex-1 flex items-center gap-2">
                <input
                  id="min-vector-score"
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  className="flex-1 p-2 border rounded disabled:bg-gray-100"
                  value={
                    currentKB.min_vector_score === undefined || currentKB.min_vector_score === null
                      ? ''
                      : currentKB.min_vector_score
                  }
                  onChange={(e) => {
                    const v = e.target.value.trim();
                    if (v === '') {
                      setCurrentKB({ ...currentKB, min_vector_score: undefined });
                      return;
                    }
                    const n = parseFloat(v);
                    setCurrentKB({
                      ...currentKB,
                      min_vector_score: Number.isNaN(n) ? undefined : n,
                    });
                  }}
                  disabled={isLoading}
                  placeholder="Optional (0–1 cosine)"
                />
                <InfoTooltip
                  title="Min vector score"
                  content="Only used for vector-only retrieval: empty query, or $rankFusion unavailable. Leave empty for no cutoff."
                />
              </div>
            </div>
          </div>

          {/* Reconciliation Configuration - Editable */}
          <div className="border-t pt-4 space-y-3 sm:space-y-4">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-gray-700">Periodic Reconciliation</h3>
              <InfoTooltip 
                title="Periodic Reconciliation"
                content="Automatically reconcile the knowledge base to fix drift between document tags and indexes. Reconciliation detects missing documents, stale documents, and orphaned vectors."
              />
            </div>
            
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
              <label htmlFor="reconcile-enabled" className="w-full sm:w-40 text-sm font-medium text-gray-700">
                Enable Reconciliation
              </label>
              <input
                id="reconcile-enabled"
                type="checkbox"
                className="w-4 h-4"
                checked={currentKB.reconcile_enabled || false}
                onChange={e => {
                  const enabled = e.target.checked;
                  setCurrentKB({ 
                    ...currentKB, 
                    reconcile_enabled: enabled,
                    reconcile_interval_seconds: enabled && !currentKB.reconcile_interval_seconds ? 60 : currentKB.reconcile_interval_seconds
                  });
                }}
                disabled={isLoading}
              />
            </div>

            {currentKB.reconcile_enabled && (
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                <label htmlFor="reconcile-interval" className="w-full sm:w-40 text-sm font-medium text-gray-700">
                  Interval (seconds)
                </label>
                <div className="flex-1 flex items-center gap-2">
                  <input
                    id="reconcile-interval"
                    type="number"
                    min={60}
                    className="flex-1 p-2 border rounded disabled:bg-gray-100"
                    value={currentKB.reconcile_interval_seconds || 60}
                    onChange={e => setCurrentKB({ 
                      ...currentKB, 
                      reconcile_interval_seconds: parseInt(e.target.value) || undefined 
                    })}
                    disabled={isLoading}
                    required={currentKB.reconcile_enabled}
                  />
                  <span className="text-sm text-gray-500 whitespace-nowrap">Minimum 60 seconds</span>
                </div>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-2 justify-end pt-4 border-t">
            <button
              type="button"
              onClick={() => router.push(`/orgs/${organizationId}/knowledge-bases`)}
              className="w-full sm:w-auto px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="w-full sm:w-auto px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              disabled={isLoading}
            >
              {isEditing ? 'Update Knowledge Base' : 'Create Knowledge Base'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default KnowledgeBaseCreate;
