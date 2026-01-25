"use client";

import React, { useState, useMemo } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { KBSearchResult } from '@docrouter/sdk';
import { toast } from 'react-toastify';
import SearchIcon from '@mui/icons-material/Search';
import { TextField, Button, Card, CardContent, Typography, Chip, CircularProgress } from '@mui/material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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

  const handleSearch = async () => {
    if (!query.trim()) {
      toast.error('Please enter a search query');
      return;
    }

    try {
      setIsSearching(true);
      const response = await docRouterOrgApi.searchKnowledgeBase({
        kbId,
        search: {
          query: query.trim(),
          top_k: topK
        }
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

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <h2 className="text-xl font-bold mb-4">Search Knowledge Base</h2>
        
        <div className="space-y-4">
          {/* Search Input */}
          <div className="flex gap-4">
            <TextField
              fullWidth
              variant="outlined"
              placeholder="Enter your search query..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isSearching}
              InputProps={{
                startAdornment: <SearchIcon className="mr-2 text-gray-400" />,
              }}
            />
            <div className="flex items-center gap-2">
              <TextField
                type="number"
                variant="outlined"
                label="Top K"
                value={topK}
                onChange={(e) => setTopK(Math.max(1, Math.min(20, parseInt(e.target.value) || 5)))}
                disabled={isSearching}
                inputProps={{ min: 1, max: 20 }}
                sx={{ width: 100 }}
              />
              <Button
                variant="contained"
                onClick={handleSearch}
                disabled={isSearching || !query.trim()}
                className="bg-blue-600 hover:bg-blue-700"
                startIcon={isSearching ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
              >
                Search
              </Button>
            </div>
          </div>

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
