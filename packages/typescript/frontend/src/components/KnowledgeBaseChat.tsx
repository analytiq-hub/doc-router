"use client";

import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { DocRouterOrgApi, getApiErrorMsg } from '@/utils/api';
import { KBChatRequest, LLMMessage, KBChatStreamChunk, KBChatStreamError, Tag } from '@docrouter/sdk';
import { toast } from 'react-toastify';
import SendIcon from '@mui/icons-material/Send';
import ClearIcon from '@mui/icons-material/Clear';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import SearchIcon from '@mui/icons-material/Search';
import FilterListIcon from '@mui/icons-material/FilterList';
import CloseIcon from '@mui/icons-material/Close';
import { CircularProgress } from '@mui/material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { isColorLight } from '@/utils/colors';

interface KnowledgeBaseChatProps {
  organizationId: string;
  kbId: string;
}


interface ToolCallInfo {
  id: string;
  toolName: string;
  arguments: Record<string, unknown>;
  iteration: number;
  resultsCount?: number;
  error?: string;
  status: 'pending' | 'completed' | 'error';
  timestamp: Date;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCallInfo[];
}

const KnowledgeBaseChat: React.FC<KnowledgeBaseChatProps> = ({ organizationId, kbId }) => {
  const docRouterOrgApi = useMemo(() => new DocRouterOrgApi(organizationId), [organizationId]);
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentInput, setCurrentInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('');
  const [currentToolCalls, setCurrentToolCalls] = useState<ToolCallInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const [expandedToolCalls, setExpandedToolCalls] = useState<Set<string>>(new Set());
  
  // Filter states
  const [showFilters, setShowFilters] = useState(false);
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [selectedTags, setSelectedTags] = useState<Tag[]>([]);
  const [uploadDateFrom, setUploadDateFrom] = useState('');
  const [uploadDateTo, setUploadDateTo] = useState('');
  const [tagDropdownOpen, setTagDropdownOpen] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Load available models
  useEffect(() => {
    const loadModels = async () => {
      try {
        const response = await docRouterOrgApi.listLLMModels();
        setAvailableModels(response.models);
        if (response.models.length > 0 && !selectedModel) {
          setSelectedModel(response.models[0]);
        }
      } catch (error) {
        const errorMsg = getApiErrorMsg(error) || 'Error loading models';
        toast.error('Error: ' + errorMsg);
      }
    };
    loadModels();
  }, [docRouterOrgApi, selectedModel]);

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

  const handleClearFilters = () => {
    setSelectedTags([]);
    setUploadDateFrom('');
    setUploadDateTo('');
  };

  const hasActiveFilters = selectedTags.length > 0 || 
    uploadDateFrom !== '' ||
    uploadDateTo !== '';

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentStreamingMessage, currentToolCalls]);

  const handleSend = async () => {
    if (!currentInput.trim() || !selectedModel || isStreaming) return;

    const userMessage: Message = {
      role: 'user',
      content: currentInput.trim()
    };

    setMessages(prev => [...prev, userMessage]);
    setCurrentInput('');
    setError(null);
    setCurrentStreamingMessage('');
    setCurrentToolCalls([]);
    setIsStreaming(true);

    const controller = new AbortController();
    setAbortController(controller);

    try {
      // Build conversation history
      const conversationMessages: LLMMessage[] = messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }));
      conversationMessages.push({
        role: 'user',
        content: userMessage.content
      });

      // Build metadata filter and date filters for the request
      const metadataFilter = buildMetadataFilter();
      const request: KBChatRequest = {
        model: selectedModel,
        messages: conversationMessages,
        temperature: 0.7,
        stream: true,
        metadata_filter: metadataFilter,
        upload_date_from: uploadDateFrom || undefined,
        upload_date_to: uploadDateTo || undefined
      };

      let assistantContent = '';
      const toolCalls: ToolCallInfo[] = [];

      await docRouterOrgApi.runKBChatStream(
        kbId,
        request,
        (chunk: KBChatStreamChunk | KBChatStreamError) => {
          if ('error' in chunk) {
            setError(chunk.error || 'An error occurred');
            setIsStreaming(false);
            return;
          }

          // Handle text chunks
          if (chunk.chunk) {
            assistantContent += chunk.chunk;
            setCurrentStreamingMessage(assistantContent);
          }

          // Handle tool call events
          if (chunk.type === 'tool_call' && chunk.tool_name) {
            const toolCallId = `${chunk.iteration}-${chunk.tool_name}-${Date.now()}`;
            const toolCall: ToolCallInfo = {
              id: toolCallId,
              toolName: chunk.tool_name,
              arguments: chunk.arguments || {},
              iteration: chunk.iteration || 1,
              status: 'pending',
              timestamp: new Date()
            };
            toolCalls.push(toolCall);
            setCurrentToolCalls([...toolCalls]);
          }

          // Handle tool result events
          if (chunk.type === 'tool_result' && chunk.tool_name) {
            // Find the most recent pending tool call for this tool name and iteration
            for (let i = toolCalls.length - 1; i >= 0; i--) {
              if (
                toolCalls[i].toolName === chunk.tool_name &&
                toolCalls[i].iteration === chunk.iteration &&
                toolCalls[i].status === 'pending'
              ) {
                toolCalls[i] = {
                  ...toolCalls[i],
                  resultsCount: chunk.results_count,
                  error: chunk.error,
                  status: chunk.error ? 'error' : 'completed'
                };
                setCurrentToolCalls([...toolCalls]);
                break;
              }
            }
          }

          // Handle done signal
          if (chunk.done) {
            setIsStreaming(false);
            // Add final assistant message with tool calls
            if (assistantContent || toolCalls.length > 0) {
              setMessages(prev => {
                const newMessages = [...prev];
                newMessages.push({
                  role: 'assistant',
                  content: assistantContent,
                  toolCalls: toolCalls.length > 0 ? [...toolCalls] : undefined
                });
                return newMessages;
              });
            }
            setCurrentStreamingMessage('');
            setCurrentToolCalls([]);
          }
        },
        (error) => {
          if (error.name === 'AbortError') {
            setError('Request was cancelled');
          } else {
            setError(error.message);
          }
          setIsStreaming(false);
        },
        controller.signal
      );
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        setError('Request was cancelled');
      } else {
        const errorMsg = getApiErrorMsg(error) || 'An error occurred';
        setError(errorMsg);
        toast.error('Error: ' + errorMsg);
      }
      setIsStreaming(false);
    } finally {
      setAbortController(null);
    }
  };

  const handleCancel = () => {
    if (abortController) {
      abortController.abort();
    }
  };

  const handleClear = () => {
    if (isStreaming) {
      handleCancel();
    }
    setMessages([]);
    setCurrentStreamingMessage('');
    setCurrentToolCalls([]);
    setError(null);
  };

  const toggleToolCallExpansion = (toolCallId: string) => {
    setExpandedToolCalls(prev => {
      const newSet = new Set(prev);
      if (newSet.has(toolCallId)) {
        newSet.delete(toolCallId);
      } else {
        newSet.add(toolCallId);
      }
      return newSet;
    });
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full w-full sm:max-w-6xl sm:mx-auto bg-white sm:rounded-lg sm:shadow-lg">
      {/* Header */}
      <div className="bg-gradient-to-r bg-blue-600 px-3 sm:px-6 py-2 sm:py-4 sm:rounded-t-lg">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-4">
          <h2 className="text-base sm:text-xl font-semibold text-white truncate">Chat with Knowledge Base</h2>
          <div className="flex items-center gap-2 sm:gap-4">
            {availableModels.length > 0 && (
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={isStreaming}
                className="flex-1 sm:flex-none px-2 sm:px-3 py-1 text-xs sm:text-sm bg-white text-gray-800 rounded border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-300"
              >
                {availableModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            )}
            <button
              onClick={() => setShowFilters(!showFilters)}
              disabled={isStreaming}
              className={`text-white hover:text-gray-200 transition-colors p-1 rounded-full hover:bg-white hover:bg-opacity-20 disabled:opacity-50 flex-shrink-0 ${hasActiveFilters ? 'bg-white bg-opacity-30' : ''}`}
              title="Toggle filters"
            >
              <FilterListIcon fontSize="small" className="sm:hidden" />
              <FilterListIcon className="hidden sm:block" />
            </button>
            <button
              onClick={handleClear}
              disabled={isStreaming}
              className="text-white hover:text-gray-200 transition-colors p-1 rounded-full hover:bg-white hover:bg-opacity-20 disabled:opacity-50 flex-shrink-0"
              title="Clear conversation"
            >
              <ClearIcon fontSize="small" className="sm:hidden" />
              <ClearIcon className="hidden sm:block" />
            </button>
          </div>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="border-b border-gray-200 bg-gray-50 p-4 space-y-4 transition-all duration-300">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-900">Search Filters</h3>
            <div className="flex gap-2">
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
          </div>
          <p className="text-xs text-gray-600 mb-3">
            These filters will be suggested to the LLM when searching. The AI can choose to use them in its search tool calls.
          </p>

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

      {/* Messages Area */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-3 sm:p-6 space-y-3 sm:space-y-4 bg-gray-50"
        style={{ minHeight: '300px', maxHeight: 'calc(100vh - 250px)' }}
      >
        {messages.length === 0 && !currentStreamingMessage && (
          <div className="text-center py-8 sm:py-12 text-gray-500 px-4">
            <p className="text-base sm:text-lg mb-2">Start a conversation with your knowledge base</p>
            <p className="text-xs sm:text-sm">Ask questions and the AI will search the knowledge base to provide answers.</p>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] sm:max-w-[80%] rounded-lg px-3 py-2 sm:px-4 sm:py-3 ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-800 border border-gray-200'
              }`}
            >
              {message.role === 'user' ? (
                <div className="whitespace-pre-wrap text-sm sm:text-base">{message.content}</div>
              ) : (
                <div className="markdown-prose">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                </div>
              )}
              
              {/* Tool Calls */}
              {message.toolCalls && message.toolCalls.length > 0 && (
                <div className="mt-2 sm:mt-3 pt-2 sm:pt-3 border-t border-gray-300">
                  <div className="text-xs font-semibold text-gray-600 mb-1 sm:mb-2">Tool Usage:</div>
                  {message.toolCalls.map((toolCall) => (
                    <div key={toolCall.id} className="mb-1 sm:mb-2 text-xs">
                      <button
                        onClick={() => toggleToolCallExpansion(toolCall.id)}
                        className="flex items-center gap-1 text-blue-600 hover:text-blue-800 w-full text-left"
                      >
                        {expandedToolCalls.has(toolCall.id) ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                        <SearchIcon fontSize="small" />
                        <span className="font-medium truncate">
                          {toolCall.toolName} <span className="hidden sm:inline">(Iteration {toolCall.iteration})</span>
                        </span>
                        {toolCall.status === 'pending' && (
                          <CircularProgress size={12} className="ml-2" />
                        )}
                        {toolCall.status === 'completed' && toolCall.resultsCount !== undefined && (
                          <span className="ml-2 text-green-600">✓ {toolCall.resultsCount} results</span>
                        )}
                        {toolCall.status === 'error' && (
                          <span className="ml-2 text-red-600">✗ Error</span>
                        )}
                      </button>
                      {expandedToolCalls.has(toolCall.id) && (
                        <div className="mt-1 ml-4 sm:ml-6 p-2 bg-gray-100 rounded text-xs">
                          <div className="font-medium mb-1">Query:</div>
                          <div className="text-gray-700 mb-2 break-words">
                            {(toolCall.arguments?.query as string) || 'N/A'}
                          </div>
                          {toolCall.arguments?.top_k !== undefined && (
                            <div className="text-gray-600">Top K: {String(toolCall.arguments.top_k)}</div>
                          )}
                          {toolCall.error && (
                            <div className="text-red-600 mt-1 break-words">Error: {toolCall.error}</div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Streaming Message */}
        {currentStreamingMessage && (
          <div className="flex justify-start">
            <div className="max-w-[85%] sm:max-w-[80%] rounded-lg px-3 py-2 sm:px-4 sm:py-3 bg-white text-gray-800 border border-gray-200">
              <div className="markdown-prose">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {currentStreamingMessage}
                </ReactMarkdown>
              </div>
              {isStreaming && (
                <span className="inline-block w-2 h-4 bg-blue-600 ml-1 animate-pulse" />
              )}
            </div>
          </div>
        )}

        {/* Current Tool Calls (during streaming) */}
        {currentToolCalls.length > 0 && (
          <div className="flex justify-start">
            <div className="max-w-[85%] sm:max-w-[80%] rounded-lg px-3 py-2 sm:px-4 sm:py-3 bg-yellow-50 border border-yellow-200">
              <div className="text-xs font-semibold text-gray-700 mb-2">Active Tool Calls:</div>
              {currentToolCalls.map((toolCall) => (
                <div key={toolCall.id} className="mb-2 text-xs">
                  <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
                    <SearchIcon fontSize="small" className="text-blue-600 flex-shrink-0" />
                    <span className="font-medium truncate">{toolCall.toolName}</span>
                    {toolCall.status === 'pending' && (
                      <>
                        <CircularProgress size={12} className="flex-shrink-0" />
                        <span className="text-gray-600 text-xs">Searching...</span>
                      </>
                    )}
                    {toolCall.status === 'completed' && toolCall.resultsCount !== undefined && (
                      <span className="text-green-600 text-xs">✓ {toolCall.resultsCount} results</span>
                    )}
                    {toolCall.status === 'error' && (
                      <span className="text-red-600 text-xs">✗ Error</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="flex justify-center">
            <div className="max-w-[85%] sm:max-w-[80%] rounded-lg px-3 py-2 sm:px-4 sm:py-3 bg-red-50 border border-red-200 text-red-800">
              <div className="flex items-start gap-2">
                <span className="font-medium">Error:</span>
                <span>{error}</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 p-3 sm:p-4 bg-white sm:rounded-b-lg">
        <div className="flex gap-2">
          <textarea
            value={currentInput}
            onChange={(e) => setCurrentInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            disabled={isStreaming || !selectedModel}
            className="flex-1 px-3 sm:px-4 py-2 sm:py-3 text-sm sm:text-base border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none disabled:bg-gray-100 disabled:cursor-not-allowed"
            rows={2}
          />
          <div className="flex flex-col gap-2">
            {isStreaming ? (
              <button
                onClick={handleCancel}
                className="px-4 sm:px-6 py-2 sm:py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium flex items-center justify-center gap-1 sm:gap-2 text-sm sm:text-base"
              >
                <span className="hidden sm:inline">Cancel</span>
                <span className="sm:hidden">✕</span>
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!currentInput.trim() || !selectedModel || isStreaming}
                className="px-4 sm:px-6 py-2 sm:py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium flex items-center justify-center gap-1 sm:gap-2 disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                <SendIcon fontSize="small" className="sm:hidden" />
                <SendIcon className="hidden sm:block" />
                <span className="hidden sm:inline">Send</span>
              </button>
            )}
          </div>
        </div>
        {!selectedModel && availableModels.length === 0 && (
          <div className="text-xs text-gray-500 mt-2">Loading models...</div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeBaseChat;
