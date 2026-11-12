"use client";

import { toastActionError } from '@/utils/toastActionError';
import React, { useState, useMemo, useCallback } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { KBSearchResult } from '@docrouter/sdk';
import { toast } from 'sonner';
import { Filter, Loader2, Search, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useOrgAllTags } from '@/api/orgQueries';
import { TagCheckboxList } from '@/components/TagCheckboxList';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

interface KnowledgeBaseSearchProps {
  organizationId: string;
  kbId: string;
}

/** Format fusion / vector relevance for display (not a 0–100% probability). */
function formatRelevanceScore(value: number): string {
  const a = Math.abs(value);
  if (!Number.isFinite(value)) return String(value);
  if (a === 0) return '0';
  if (a >= 0.0001) return value.toFixed(4).replace(/\.?0+$/, '');
  return value.toExponential(2);
}

const KnowledgeBaseSearch: React.FC<KnowledgeBaseSearchProps> = ({ organizationId, kbId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<KBSearchResult[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  
  // Filter states
  const [showFilters, setShowFilters] = useState(false);
  const { data: availableTags = [] } = useOrgAllTags(organizationId);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [uploadDateFrom, setUploadDateFrom] = useState('');
  const [uploadDateTo, setUploadDateTo] = useState('');

  const buildMetadataFilter = useCallback((): Record<string, unknown> | undefined => {
    if (selectedTagIds.length > 0) {
      return {
        tag_ids: selectedTagIds,
      };
    }
    return undefined;
  }, [selectedTagIds]);

  const handleSearch = async () => {
    if (!query.trim()) {
      toast.error('Please enter a search query');
      return;
    }

    try {
      setIsSearching(true);
      const metadataFilter = buildMetadataFilter();
      const searchParams: {
        query: string;
        top_k: number;
        metadata_filter?: Record<string, unknown>;
        upload_date_from?: string;
        upload_date_to?: string;
      } = {
        query: query.trim(),
        top_k: topK
      };
      
      if (metadataFilter) {
        searchParams.metadata_filter = metadataFilter;
      }
      
      if (uploadDateFrom) {
        searchParams.upload_date_from = new Date(uploadDateFrom).toISOString();
      }
      
      if (uploadDateTo) {
        // Set to end of day
        const date = new Date(uploadDateTo);
        date.setHours(23, 59, 59, 999);
        searchParams.upload_date_to = date.toISOString();
      }
      
      const response = await docRouterOrgApi.searchKnowledgeBase({
        kbId,
        search: searchParams
      });
      setResults(response.results);
      setTotalCount(response.total_count);
    } catch (error) {
      toastActionError('Failed to search knowledge base', error);
      setResults([]);
      setTotalCount(0);
    } finally {
      setIsSearching(false);
    }
  };

  const handleClearFilters = () => {
    setSelectedTagIds([]);
    setUploadDateFrom('');
    setUploadDateTo('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  const hasActiveFilters =
    selectedTagIds.length > 0 || uploadDateFrom !== '' || uploadDateTo !== '';

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Search Knowledge Base</h2>
          <Button
            type="button"
            variant={hasActiveFilters ? 'default' : 'outline'}
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="size-4" />
            Filters{' '}
            {hasActiveFilters &&
              `(${selectedTagIds.length + (uploadDateFrom ? 1 : 0) + (uploadDateTo ? 1 : 0)})`}
          </Button>
        </div>
        
        <div className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:gap-4">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Enter your search query..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyPress}
                disabled={isSearching}
                className="h-9 pl-9"
              />
            </div>
            <div className="flex shrink-0 items-end gap-2">
              <div className="flex w-20 flex-col gap-1">
                <label htmlFor="kb-search-top-k" className="text-xs font-medium text-muted-foreground">
                  Top K
                </label>
                <Input
                  id="kb-search-top-k"
                  type="number"
                  min={1}
                  max={20}
                  value={topK}
                  onChange={(e) =>
                    setTopK(Math.max(1, Math.min(20, parseInt(e.target.value, 10) || 5)))
                  }
                  disabled={isSearching}
                  className="h-9 w-20 tabular-nums"
                />
              </div>
              <Button
                type="button"
                className="h-9"
                onClick={handleSearch}
                disabled={isSearching || !query.trim()}
              >
                {isSearching ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
                Search
              </Button>
            </div>
          </div>

          {/* Filters Panel */}
          {showFilters && (
            <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-4 transition-all duration-300">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-900">Search Filters</h3>
                {hasActiveFilters && (
                  <Button type="button" variant="ghost" size="sm" onClick={handleClearFilters}>
                    <X className="size-4" />
                    Clear all
                  </Button>
                )}
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Filter by tags</label>
                <TagCheckboxList
                  tags={availableTags}
                  selectedIds={selectedTagIds}
                  onChange={setSelectedTagIds}
                  disabled={isSearching}
                />
              </div>

              {/* Date Range Filters */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Upload Date From</label>
                  <input
                    type="date"
                    value={uploadDateFrom}
                    onChange={(e) => setUploadDateFrom(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Upload Date To</label>
                  <input
                    type="date"
                    value={uploadDateTo}
                    onChange={(e) => setUploadDateTo(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              </div>

            </div>
          )}

          {/* Results Count */}
          {totalCount > 0 && (
            <div className="text-sm text-gray-600">
              Found {totalCount} result{totalCount !== 1 ? 's' : ''}
            </div>
          )}

          {/* Results */}
          {results.length > 0 && (
            <div className="space-y-4 mt-6">
              {results.map((result, index) => (
                <Card key={index} className="transition-shadow hover:shadow-md">
                  <CardContent className="pt-6">
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold">{result.source}</span>
                        {result.is_matched ? (
                          <Badge variant="default">Matched</Badge>
                        ) : (
                          <Badge variant="outline">Context</Badge>
                        )}
                      </div>
                      {result.relevance != null && (
                        <Badge
                          variant="secondary"
                          title="Fused score from hybrid search (RRF), or vector similarity when vector-only fallback is used"
                        >
                          Relevance: {formatRelevanceScore(result.relevance)}
                        </Badge>
                      )}
                    </div>
                    <div className="markdown-prose">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {result.content}
                      </ReactMarkdown>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      {/* Chunk index */}
                      <span className="inline-flex items-center gap-1 rounded-full bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-700 ring-1 ring-primary-100">
                        <span className="text-primary-400">Chunk Index #</span>
                        {result.chunk_index}
                      </span>
                      {/* Char range */}
                      {result.indexed_text_start != null && result.indexed_text_end != null && (
                        <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium tabular-nums text-slate-600">
                          {result.indexed_text_start.toLocaleString()}–{result.indexed_text_end.toLocaleString()} chars
                        </span>
                      )}
                      {/* Page range */}
                      {result.page_start != null && result.page_end != null && result.page_start > 0 && (
                        <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium tabular-nums text-slate-600">
                          {result.page_start === result.page_end
                            ? `Page ${result.page_start}`
                            : `Pages ${result.page_start}–${result.page_end}`}
                        </span>
                      )}
                      <span className="text-xs text-gray-400">{result.document_id}</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* No Results */}
          {!isSearching && results.length === 0 && query && (
            <div className="text-center py-8 text-gray-500">
              No results found. Try a different query.
            </div>
          )}

          {/* Empty State */}
          {!isSearching && results.length === 0 && !query && (
            <div className="text-center py-8 text-gray-500">
              Enter a search query to find relevant content in the knowledge base.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBaseSearch;
