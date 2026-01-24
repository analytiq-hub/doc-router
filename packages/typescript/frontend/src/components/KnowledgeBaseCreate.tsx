"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { KnowledgeBaseConfig, Tag, ChunkerType } from '@docrouter/sdk';
import { useRouter } from 'next/navigation';
import { toast } from 'react-toastify';
import InfoTooltip from '@/components/InfoTooltip';
import TagSelector from '@/components/TagSelector';

const CHUNKER_TYPES: ChunkerType[] = ['token', 'word', 'sentence', 'recursive'];
const DEFAULT_CHUNK_SIZE = 512;
const DEFAULT_CHUNK_OVERLAP = 128;
const DEFAULT_EMBEDDING_MODEL = 'text-embedding-3-small';
const DEFAULT_COALESCE_NEIGHBORS = 0;
const MIN_CHUNK_SIZE = 50;
const MAX_CHUNK_SIZE = 2000;
const MAX_COALESCE_NEIGHBORS = 5;

const KnowledgeBaseCreate: React.FC<{ organizationId: string; kbId?: string }> = ({ organizationId, kbId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [currentKB, setCurrentKB] = useState<KnowledgeBaseConfig>({
    name: '',
    description: '',
    tag_ids: [],
    chunker_type: 'recursive',
    chunk_size: DEFAULT_CHUNK_SIZE,
    chunk_overlap: DEFAULT_CHUNK_OVERLAP,
    embedding_model: DEFAULT_EMBEDDING_MODEL,
    coalesce_neighbors: DEFAULT_COALESCE_NEIGHBORS
  });
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [isEditing, setIsEditing] = useState(false);

  // Load available tags
  useEffect(() => {
    async function loadTags() {
      try {
        const response = await docRouterOrgApi.listTags({ limit: 1000 });
        setAvailableTags(response.tags);
      } catch (error) {
        console.error('Error loading tags:', error);
      }
    }
    loadTags();
  }, [docRouterOrgApi]);

  // Load KB if editing
  useEffect(() => {
    async function loadKB() {
      if (kbId) {
        setIsLoading(true);
        try {
          const kb = await docRouterOrgApi.getKnowledgeBase({ kbId });
          setCurrentKB({
            name: kb.name,
            description: kb.description || '',
            tag_ids: kb.tag_ids || [],
            chunker_type: kb.chunker_type,
            chunk_size: kb.chunk_size,
            chunk_overlap: kb.chunk_overlap,
            embedding_model: kb.embedding_model,
            coalesce_neighbors: kb.coalesce_neighbors || 0
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
        // Update existing KB (only mutable fields)
        await docRouterOrgApi.updateKnowledgeBase({
          kbId,
          update: {
            name: currentKB.name,
            description: currentKB.description,
            tag_ids: currentKB.tag_ids,
            coalesce_neighbors: currentKB.coalesce_neighbors
          }
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
    <div className="p-4 max-w-4xl mx-auto">
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <div className="hidden md:flex items-center gap-2 mb-4">
          <h2 className="text-xl font-bold">
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
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Name */}
          <div className="flex items-center gap-4">
            <label htmlFor="kb-name" className="w-40 text-sm font-medium text-gray-700">
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
          <div className="flex items-center gap-4">
            <label htmlFor="kb-description" className="w-40 text-sm font-medium text-gray-700">
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

          {/* Tags */}
          <div className="flex items-start gap-4">
            <label className="w-40 text-sm font-medium text-gray-700 pt-2">
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

          {/* Configuration Section - Only editable when creating */}
          {!isEditing && (
            <>
              <div className="border-t pt-6 mt-6">
                <h3 className="text-lg font-semibold mb-4">Indexing Configuration</h3>
                <p className="text-sm text-gray-600 mb-4">
                  These settings cannot be changed after creation. To use different settings, create a new KB.
                </p>

                {/* Chunker Type */}
                <div className="flex items-center gap-4 mb-4">
                  <label htmlFor="chunker-type" className="w-40 text-sm font-medium text-gray-700">
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
                <div className="flex items-center gap-4 mb-4">
                  <label htmlFor="chunk-size" className="w-40 text-sm font-medium text-gray-700">
                    Chunk Size (tokens)
                  </label>
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
                  <span className="text-sm text-gray-500 w-20">{MIN_CHUNK_SIZE}-{MAX_CHUNK_SIZE}</span>
                </div>

                {/* Chunk Overlap */}
                <div className="flex items-center gap-4 mb-4">
                  <label htmlFor="chunk-overlap" className="w-40 text-sm font-medium text-gray-700">
                    Chunk Overlap (tokens)
                  </label>
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
                  <span className="text-sm text-gray-500 w-20">0-{(currentKB.chunk_size ?? DEFAULT_CHUNK_SIZE) - 1}</span>
                </div>

                {/* Embedding Model */}
                <div className="flex items-center gap-4 mb-4">
                  <label htmlFor="embedding-model" className="w-40 text-sm font-medium text-gray-700">
                    Embedding Model
                  </label>
                  <input
                    id="embedding-model"
                    type="text"
                    className="flex-1 p-2 border rounded disabled:bg-gray-100"
                    value={currentKB.embedding_model ?? DEFAULT_EMBEDDING_MODEL}
                    onChange={e => setCurrentKB({ ...currentKB, embedding_model: e.target.value })}
                    placeholder="text-embedding-3-small"
                    disabled={isLoading}
                  />
                </div>
              </div>
            </>
          )}

          {/* Coalesce Neighbors - Editable */}
          <div className="flex items-center gap-4">
            <label htmlFor="coalesce-neighbors" className="w-40 text-sm font-medium text-gray-700">
              Coalesce Neighbors
            </label>
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
            <span className="text-sm text-gray-500 w-20">0-{MAX_COALESCE_NEIGHBORS}</span>
            <InfoTooltip 
              title="Coalesce Neighbors"
              content="Number of neighboring chunks to include in search results for context. 0 means only return matched chunks."
            />
          </div>

          {/* Action Buttons */}
          <div className="flex gap-2 justify-end pt-4 border-t">
            <button
              type="button"
              onClick={() => router.push(`/orgs/${organizationId}/knowledge-bases`)}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
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
