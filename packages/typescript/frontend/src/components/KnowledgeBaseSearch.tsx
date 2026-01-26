"use client";

import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { KBSearchResult, Tag } from '@docrouter/sdk';
import { toast } from 'react-toastify';
import SearchIcon from '@mui/icons-material/Search';
import FilterListIcon from '@mui/icons-material/FilterList';
import CloseIcon from '@mui/icons-material/Close';
import { Card, CardContent, Typography, Chip, CircularProgress } from '@mui/material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { isColorLight } from '@/utils/colors';

interface KnowledgeBaseSearchProps {
  organizationId: string;
  kbId: string;
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
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [selectedTags, setSelectedTags] = useState<Tag[]>([]);
  const [uploadDateFrom, setUploadDateFrom] = useState('');
  const [uploadDateTo, setUploadDateTo] = useState('');
  const [tagDropdownOpen, setTagDropdownOpen] = useState(false);

  // Load tags and documents for filters
  useEffect(() => {
    const loadFilterData = async () => {
      try {
        // Load tags
        const tagsResponse = await docRouterOrgApi.listTags({ limit: 100 });
        setAvailableTags(tagsResponse.tags);
      } catch (error) {
        console.error('Error loading tags:', error);
        // Tags are optional for filtering, continue without them
      }
      
    };
    loadFilterData();
  }, [docRouterOrgApi, kbId]);

  const buildMetadataFilter = useCallback((): Record<string, unknown> | undefined => {
    if (selectedTags.length > 0) {
      return {
        tag_ids: selectedTags.map(tag => tag.id)
      };
    }
    return undefined;
  }, [selectedTags]);

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
      const errorMsg = getApiErrorMsg(error) || 'Error searching knowledge base';
      toast.error('Error: ' + errorMsg);
      setResults([]);
      setTotalCount(0);
    } finally {
      setIsSearching(false);
    }
  };

  const handleClearFilters = () => {
    setSelectedTags([]);
    setUploadDateFrom('');
    setUploadDateTo('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  const hasActiveFilters = selectedTags.length > 0 || 
    uploadDateFrom !== '' ||
    uploadDateTo !== '';

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Search Knowledge Base</h2>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`px-3 py-1.5 text-sm border rounded-md transition-colors flex items-center gap-2 ${
              hasActiveFilters
                ? 'border-blue-600 text-blue-600 bg-blue-50 hover:bg-blue-100'
                : 'border-gray-300 text-gray-700 hover:bg-gray-50'
            }`}
          >
            <FilterListIcon fontSize="small" />
            Filters {hasActiveFilters && `(${selectedTags.length + (uploadDateFrom ? 1 : 0) + (uploadDateTo ? 1 : 0)})`}
          </button>
        </div>
        
        <div className="space-y-4">
          {/* Search Input */}
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <SearchIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Enter your search query..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={isSearching}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            </div>
            <div className="flex items-center gap-2">
              <div className="relative">
                <label className="absolute -top-2 left-2 px-1 text-xs text-gray-600 bg-white">Top K</label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={topK}
                  onChange={(e) => setTopK(Math.max(1, Math.min(20, parseInt(e.target.value) || 5)))}
                  disabled={isSearching}
                  className="w-24 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
                />
              </div>
              <button
                onClick={handleSearch}
                disabled={isSearching || !query.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isSearching ? (
                  <CircularProgress size={20} color="inherit" />
                ) : (
                  <SearchIcon fontSize="small" />
                )}
                Search
              </button>
            </div>
          </div>

          {/* Filters Panel */}
          {showFilters && (
            <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-4 transition-all duration-300">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-900">Search Filters</h3>
                {hasActiveFilters && (
                  <button
                    onClick={handleClearFilters}
                    className="px-2 py-1 text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1"
                  >
                    <CloseIcon fontSize="small" />
                    Clear All
                  </button>
                )}
              </div>

              {/* Tag Filter */}
              <div className="relative">
                <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Tags</label>
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setTagDropdownOpen(!tagDropdownOpen)}
                    className="w-full px-3 py-2 text-left border border-gray-300 rounded-md bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent flex items-center justify-between"
                  >
                    <span className="text-gray-500">
                      {selectedTags.length > 0 ? `${selectedTags.length} selected` : 'Select tags'}
                    </span>
                    <span className={`transform transition-transform ${tagDropdownOpen ? 'rotate-180' : ''}`}>▼</span>
                  </button>
                  {tagDropdownOpen && (
                    <>
                      <div
                        className="fixed inset-0 z-10"
                        onClick={() => setTagDropdownOpen(false)}
                      />
                      <div className="absolute z-20 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
                        {availableTags.map((tag) => {
                          const isSelected = selectedTags.some(t => t.id === tag.id);
                          return (
                            <label
                              key={tag.id}
                              className="flex items-center px-3 py-2 hover:bg-gray-100 cursor-pointer"
                            >
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedTags([...selectedTags, tag]);
                                  } else {
                                    setSelectedTags(selectedTags.filter(t => t.id !== tag.id));
                                  }
                                }}
                                className="mr-2"
                              />
                              <span>{tag.name}</span>
                            </label>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
                {selectedTags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {selectedTags.map((tag) => {
                      const bgColor = tag.color;
                      const textColor = isColorLight(bgColor) ? 'text-gray-800' : 'text-white';
                      return (
                        <span
                          key={tag.id}
                          className="px-2 py-1 rounded text-xs flex items-center gap-1"
                          style={{ backgroundColor: bgColor, color: textColor }}
                        >
                          {tag.name}
                          <button
                            onClick={() => setSelectedTags(selectedTags.filter(t => t.id !== tag.id))}
                            className="ml-1 hover:opacity-70"
                          >
                            <CloseIcon fontSize="small" />
                          </button>
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Date Range Filters */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Upload Date From</label>
                  <input
                    type="date"
                    value={uploadDateFrom}
                    onChange={(e) => setUploadDateFrom(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Upload Date To</label>
                  <input
                    type="date"
                    value={uploadDateTo}
                    onChange={(e) => setUploadDateTo(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                <Card key={index} className="hover:shadow-md transition-shadow">
                  <CardContent>
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Typography variant="subtitle2" className="font-semibold">
                          {result.source}
                        </Typography>
                        {result.is_matched && (
                          <Chip 
                            label="Matched" 
                            size="small" 
                            color="primary"
                            className="text-xs"
                          />
                        )}
                        {!result.is_matched && (
                          <Chip 
                            label="Context" 
                            size="small" 
                            variant="outlined"
                            className="text-xs"
                          />
                        )}
                      </div>
                      {result.relevance !== undefined && (
                        <Chip 
                          label={`${(result.relevance * 100).toFixed(1)}%`}
                          size="small"
                          className="bg-blue-100 text-blue-800"
                        />
                      )}
                    </div>
                    <div className="markdown-prose">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {result.content}
                      </ReactMarkdown>
                    </div>
                    <div className="mt-2 text-xs text-gray-500">
                      Chunk {result.chunk_index} • Document ID: {result.document_id}
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
